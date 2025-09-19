import click
import litellm
from pathlib import Path
from typing import List, Optional


@click.group(invoke_without_command=True)
@click.option(
    "--version", "-v",
    help="NuShell version to check compatibility against (defaults to latest)"
)
@click.option(
    "--directory", "-d", "directories",
    multiple=True,
    help="Directory to scan for NuShell scripts (can be repeated)"
)
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file"
)
@click.option(
    "--verbose", "-V",
    is_flag=True,
    help="Enable verbose output"
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Bypass cache and fetch fresh data"
)
@click.option(
    "--no-progress",
    is_flag=True,
    help="Disable progress bars and spinners"
)
@click.option(
    "--debug",
    is_flag=True,
    help="Debug mode"
)
@click.option(
    "--help", "-h",
    is_flag=True,
    help="Show this message and exit"
)
@click.pass_context
def cli(
    ctx,
    version: Optional[str],
    directories: List[str],
    config: Optional[Path],
    verbose: bool,
    no_cache: bool,
    no_progress: bool,
    debug: bool,
    help: bool
):
    """NuShell script compatibility verifier.

    Scans NuShell scripts and checks their compatibility with specified or latest NuShell version.
    """
    if help:
        click.echo(ctx.get_help())
        ctx.exit()

    # If no subcommand is invoked, run the main analysis
    if ctx.invoked_subcommand is None:
        from .config import load_config
        from .analyzer import NuShellAnalyzer
        from .reporter import Reporter

        if debug:
            litellm._turn_on_debug()

        # Load configuration
        cfg = load_config(config)

        # Override config with CLI options
        if directories:
            cfg.scan_directories = list(directories)
        if no_cache:
            cfg.cache_enabled = False

        # Initialize analyzer and reporter
        analyzer = NuShellAnalyzer(cfg, disable_progress=no_progress)
        reporter = Reporter(verbose=verbose)

        try:
            # Run analysis
            results = analyzer.analyze_scripts(target_version=version)

            # Generate report
            reporter.generate_report(results)

        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            raise click.Abort()


@cli.group()
def cache():
    """Manage cache operations."""
    pass


@cache.command("info")
@click.option(
    "--short", "-s",
    is_flag=True,
    help="Show short summary (default is detailed view)"
)
def cache_info(short):
    """Show cache information."""
    from .cache import InstructionCache

    cache = InstructionCache()

    if short:
        # Show short summary (original behavior)
        info = cache.get_cache_info()
        click.echo("Cache Information:")
        click.echo(f"  Directory: {info['cache_directory']}")
        click.echo(f"  Exists: {info['exists']}")
        click.echo(f"  Files: {info['file_count']}")
        if info['exists']:
            click.echo(f"  Total size: {info['total_size_mb']} MB")
            if info['versions']:
                click.echo(f"  Cached versions: {', '.join(info['versions'])}")
            else:
                click.echo("  No cached versions")
    else:
        # Show detailed view with rich formatting
        _show_detailed_cache_info(cache)


def _show_detailed_cache_info(cache):
    """Show detailed cache information with rich formatting."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from datetime import datetime

    console = Console()
    detailed_info = cache.get_detailed_cache_info()

    if not detailed_info['exists'] or not detailed_info['entries']:
        console.print(Panel(
            "[yellow]Cache is empty or does not exist[/yellow]",
            title="[bold blue]Cache Information[/bold blue]",
            border_style="blue"
        ))
        console.print(f"[dim]Directory: {detailed_info['cache_directory']}[/dim]")
        return

    # Header
    console.print(Panel(
        f"[green]Found {len(detailed_info['entries'])} cached version(s)[/green]",
        title="[bold blue]Cache Information[/bold blue]",
        border_style="blue"
    ))
    console.print(f"[dim]Directory: {detailed_info['cache_directory']}[/dim]\n")

    # Show each version
    for entry in detailed_info['entries']:
        version = entry['version']
        model = entry['llm_model']
        created_at = entry['created_at']
        instructions = entry['instructions']
        file_size = entry['file_size_bytes']

        # Format creation date
        try:
            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except (ValueError, TypeError):
            formatted_date = created_at

        # Create version panel
        version_info = Table.grid(padding=(0, 2))
        version_info.add_column(style="cyan", no_wrap=True)
        version_info.add_column()

        version_info.add_row("Model:", f"[yellow]{model}[/yellow]")
        version_info.add_row("Created:", f"[dim]{formatted_date}[/dim]")
        version_info.add_row("Size:", f"[dim]{file_size:,} bytes[/dim]")

        console.print(Panel(
            version_info,
            title=f"[bold green]Version {version}[/bold green]",
            border_style="green",
            padding=(1, 2)
        ))

        # Show instructions (full content)
        if instructions:
            # Clean up instructions for display
            clean_instructions = instructions.strip()

            console.print(Panel(
                clean_instructions,
                title="[bold yellow]Compatibility Instructions[/bold yellow]",
                border_style="yellow",
                padding=(1, 2)
            ))

        console.print()  # Empty line between versions


@cache.command("clean")
def cache_clean():
    """Clear all cached compatibility instructions."""
    from .cache import InstructionCache

    cache = InstructionCache()
    removed_count = cache.clear_cache()
    if removed_count > 0:
        click.echo(f"Cleared {removed_count} cached compatibility instruction(s)")
    else:
        click.echo("Cache was already empty")


@cache.command("add")
@click.argument("versions", nargs=-1, required=True)
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file"
)
def cache_add(versions, config):
    """Prepare compatibility instructions for specific versions."""
    from .config import load_config
    from .analyzer import NuShellAnalyzer
    from .github_client import GitHubClient

    # Load configuration
    cfg = load_config(config)

    # Validate that we can use the cache
    if not cfg.cache_enabled:
        click.echo("Error: Cache is disabled in configuration", err=True)
        raise click.Abort()

    # Initialize components
    github_client = GitHubClient(cfg.github_token)

    # Show GitHub token status
    if github_client.github_token:
        if cfg.github_token:
            click.echo("Using GitHub token from configuration")
        else:
            click.echo("Using GitHub token from GitHub CLI (gh auth token)")
    else:
        click.echo("Warning: No GitHub token available - API rate limits may apply")

    click.echo(f"Preparing compatibility instructions for {len(versions)} version(s): {', '.join(versions)}")

    try:
        # Create a minimal analyzer to reuse the instruction preparation logic
        analyzer = NuShellAnalyzer(cfg, disable_progress=False)

        # Prepare instructions for each version
        for version in versions:
            _prepare_instructions_for_version(analyzer, version)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


def _prepare_instructions_for_version(analyzer, version):
    """Prepare compatibility instructions for a specific version."""
    from .models import ReleaseInfo

    click.echo(f"\nProcessing version {version}...")

    # Check if already cached
    if analyzer.cache:
        cached_instructions = analyzer.cache.get_cached_instructions(
            version,
            f"{analyzer.config.llm_provider}/{analyzer.config.llm_model}"
        )
        if cached_instructions:
            click.echo("  ✓ Instructions already cached")
            return

    # Create a ReleaseInfo object for this version
    # We need to determine the blog URL - let's try to get it from GitHub
    try:
        # Get all releases to find the blog URL for this version
        all_releases = analyzer.github_client.get_all_releases()
        release_info = None

        for release in all_releases:
            if release.version == version:
                release_info = release
                break

        if not release_info:
            # If we can't find it in releases, create a basic one and try to derive the blog URL
            blog_url = f"https://www.nushell.sh/blog/{version.replace('.', '_')}.html"
            release_info = ReleaseInfo(version, blog_url)
            click.echo(f"  Using inferred blog URL: {blog_url}")

        # Fetch blog content
        click.echo("  Fetching blog content...")
        blog_content = analyzer.github_client.fetch_blog_post_content(release_info)

        if not blog_content:
            click.echo(f"  ✗ Could not fetch blog content for version {version}")
            return

        # Generate instructions
        click.echo("  Generating compatibility instructions...")
        instructions = analyzer.llm_client.convert_blog_to_instructions(release_info, blog_content)

        # Save to cache
        if analyzer.cache:
            analyzer.cache.save_instructions(
                version,
                instructions,
                f"{analyzer.config.llm_provider}/{analyzer.config.llm_model}"
            )
            click.echo("  ✓ Instructions generated and cached")
        else:
            click.echo("  ✓ Instructions generated (cache disabled)")

    except Exception as e:
        click.echo(f"  ✗ Failed to process version {version}: {e}")


if __name__ == "__main__":
    cli()
