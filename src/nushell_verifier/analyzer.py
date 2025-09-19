from typing import List, Optional
from .models import Config, ScriptAnalysis, ScriptFile, ReleaseInfo, CompatibilityMethod
from .scanner import NuShellScriptScanner
from .github_client import GitHubClient
from .llm_client import LLMClient
from .version_manager import VersionManager
from .cache import InstructionCache
from .progress import BatchProgressManager, estimate_tokens_for_script, StreamingProgressCallback


class NuShellAnalyzer:
    """Main analyzer for NuShell script compatibility."""

    def __init__(self, config: Config, disable_progress: bool = False):
        """Initialize analyzer with configuration."""
        self.config = config
        self.disable_progress = disable_progress
        self.scanner = NuShellScriptScanner(config.scan_directories)
        self.github_client = GitHubClient(config.github_token)
        self.llm_client = LLMClient(config)
        self.version_manager = VersionManager()
        self.cache = InstructionCache() if config.cache_enabled else None

        # Show GitHub token status
        if self.github_client.github_token:
            if config.github_token:
                print("Using GitHub token from configuration")
            else:
                print("Using GitHub token from GitHub CLI (gh auth token)")
        else:
            print("Warning: No GitHub token available - API rate limits may apply")

    def analyze_scripts(self, target_version: Optional[str] = None) -> List[ScriptAnalysis]:
        """Analyze all scripts for compatibility with target version."""
        # Get target version (latest if not specified)
        if target_version is None:
            target_version = self.github_client.get_latest_version()

        print(f"Analyzing scripts for compatibility with NuShell {target_version}")

        # Scan for scripts
        scripts = self.scanner.scan_all()
        if not scripts:
            print("No NuShell scripts found in specified directories")
            return []

        print(f"Found {len(scripts)} NuShell script(s)")

        # Update default version assumptions
        self._update_default_versions(scripts, target_version)

        # Determine version range to analyze
        earliest_version = self._find_earliest_version(scripts)
        print(f"Analyzing changes from {earliest_version} to {target_version}")

        # Get releases and blog posts
        releases = self.github_client.get_releases_between(earliest_version, target_version)
        print(f"Processing {len(releases)} release(s)")

        # Convert blog posts to compatibility instructions
        compatibility_instructions = []
        cache_hits = 0
        cache_misses = 0

        for release in releases:
            print(f"Processing release {release.version}...")

            # Check cache first
            cached_instructions = None
            if self.cache:
                cached_instructions = self.cache.get_cached_instructions(
                    release.version,
                    f"{self.config.llm_provider}/{self.config.llm_model}"
                )

            if cached_instructions:
                print("  ✓ Using cached compatibility instructions")
                release.compatibility_instructions = cached_instructions
                compatibility_instructions.append(cached_instructions)
                cache_hits += 1
            else:
                # Cache miss - fetch and process
                cache_misses += 1
                blog_content = self.github_client.fetch_blog_post_content(release)
                if blog_content:
                    print("  Generating compatibility instructions...")
                    instructions = self.llm_client.convert_blog_to_instructions(release, blog_content)
                    release.compatibility_instructions = instructions
                    compatibility_instructions.append(instructions)

                    # Save to cache
                    if self.cache:
                        self.cache.save_instructions(
                            release.version,
                            instructions,
                            f"{self.config.llm_provider}/{self.config.llm_model}"
                        )
                        print("  ✓ Cached instructions for future use")
                else:
                    print(f"  Warning: Could not fetch blog post for {release.version}")

        # Show cache statistics if cache is enabled
        if self.cache and len(releases) > 0:
            print(f"Cache performance: {cache_hits} hits, {cache_misses} misses")

        # Analyze each script with real-time progress
        results = []
        from .progress import ProgressConfig
        progress_config = ProgressConfig(enabled=not self.disable_progress)
        batch_progress = BatchProgressManager(len(scripts), progress_config)

        for script in scripts:
            script_progress = batch_progress.start_script(script.path.name)

            with script_progress:
                script_progress.set_phase("Checking version compatibility")

                # Check if script is already compatible or newer than target version
                if self.version_manager.is_version_same_or_after(script.compatible_version, target_version):
                    script_progress.complete()
                    print(f"⏭️  {script.path.name} - Already compatible (v{script.compatible_version} >= v{target_version})")

                    # Create analysis result for already compatible script
                    analysis = ScriptAnalysis(
                        script=script,
                        target_version=target_version,
                        issues=[],
                        is_compatible=True
                    )
                    results.append(analysis)
                    continue

                # Estimate tokens for this script
                estimated_tokens = estimate_tokens_for_script(script.path)
                script_progress.set_phase("Preparing analysis", estimated_tokens)

                # Get relevant instructions for this script's version range
                script_instructions = self._get_relevant_instructions(
                    script, target_version, releases
                )

                script_progress.set_phase("Analyzing compatibility", estimated_tokens)

                # Create streaming callback for real-time progress
                callback = StreamingProgressCallback(script_progress)

                def token_callback(token: str):
                    """Handle streaming tokens with progress updates."""
                    if token.startswith("__USAGE__"):
                        # Extract usage info if available
                        try:
                            # Handle usage updates if needed
                            pass
                        except Exception:
                            pass
                    else:
                        callback.on_token(token)

                # Analyze script with streaming support
                try:
                    issues = self.llm_client.analyze_script_compatibility_streaming(
                        script, target_version, script_instructions,
                        progress_callback=token_callback
                    )
                except AttributeError:
                    # Fallback to non-streaming if streaming not available
                    issues = self.llm_client.analyze_script_compatibility(
                        script, target_version, script_instructions
                    )

                is_compatible = len(issues) == 0
                analysis = ScriptAnalysis(
                    script=script,
                    target_version=target_version,
                    issues=issues,
                    is_compatible=is_compatible
                )
                results.append(analysis)

                script_progress.complete()

                # Show immediate results for this script
                if is_compatible:
                    print(f"✅ {script.path.name} - Compatible with {target_version}")
                else:
                    print(f"⚠️  {script.path.name} - {len(issues)} issue(s) found")
                    self._display_immediate_script_results(script, issues)

                # Update version comment if compatible
                if is_compatible and script.method != CompatibilityMethod.DIRECTORY_FILE:
                    self._update_script_version_comment(script, target_version)

        # Show batch summary
        print(f"\n{batch_progress.get_batch_summary()}")

        return results

    def _update_default_versions(self, scripts: List[ScriptFile], target_version: str) -> None:
        """Update scripts with default version assumptions."""
        default_version = self.version_manager.calculate_default_version(target_version)

        for script in scripts:
            if script.method == CompatibilityMethod.DEFAULT_ASSUMPTION:
                script.compatible_version = default_version

    def _find_earliest_version(self, scripts: List[ScriptFile]) -> str:
        """Find the earliest compatible version among all scripts."""
        versions = [script.compatible_version for script in scripts]
        return self.version_manager.find_earliest_version(versions)

    def _get_relevant_instructions(
        self, script: ScriptFile, target_version: str, releases: List[ReleaseInfo]
    ) -> List[str]:
        """Get compatibility instructions relevant to the script's version range."""
        relevant_instructions = []

        for release in releases:
            if self.version_manager.is_version_after(release.version, script.compatible_version):
                if release.compatibility_instructions:
                    relevant_instructions.append(release.compatibility_instructions)

        return relevant_instructions

    def _display_immediate_script_results(self, script: ScriptFile, issues: List) -> None:
        """Display compatibility issues for a script immediately after analysis."""
        if not issues:
            return

        print(f"   📋 Issues found in {script.path.name}:")
        for i, issue in enumerate(issues, 1):
            severity_icon = {
                "error": "❌",
                "warning": "⚠️",
                "info": "ℹ️"
            }.get(issue.severity, "•")

            print(f"   {severity_icon} {issue.description}")
            if issue.suggested_fix:
                print(f"      💡 Fix: {issue.suggested_fix}")

        print()  # Add spacing after issues

    def _update_script_version_comment(self, script: ScriptFile, new_version: str) -> None:
        """Update the version comment in a compatible script."""
        try:
            with open(script.path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            updated_lines = self.version_manager.update_version_comment(lines, new_version)

            with open(script.path, "w", encoding="utf-8") as f:
                f.writelines(updated_lines)

            print(f"Updated version comment in {script.path.name} to {new_version}")

        except (OSError, UnicodeDecodeError) as e:
            print(f"Warning: Could not update version comment in {script.path}: {e}")


