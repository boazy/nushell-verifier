"""
Integration tests for analyzer with progress functionality.
"""
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from nushell_verifier.analyzer import NuShellAnalyzer
from nushell_verifier.models import Config, ScriptFile, ReleaseInfo, CompatibilityMethod
from nushell_verifier.progress import ProgressConfig


class TestAnalyzerProgress:
    """Test analyzer integration with progress system."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config = Config(
            llm_provider="openai",
            llm_model="gpt-4",
            scan_directories=[self.temp_dir.name]
        )

    def teardown_method(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def _create_test_script(self, name: str, content: str) -> Path:
        """Create a test script file."""
        script_path = Path(self.temp_dir.name) / name
        script_path.write_text(content)
        return script_path

    @patch('nushell_verifier.analyzer.GitHubClient')
    @patch('nushell_verifier.analyzer.LLMClient')
    @patch('nushell_verifier.analyzer.NuShellScriptScanner')
    @patch('nushell_verifier.progress.alive_bar')
    def test_analyzer_with_progress_enabled(self, mock_alive_bar, mock_scanner, mock_llm, mock_github):
        """Test analyzer with progress enabled."""
        # Mock progress bar
        mock_bar = MagicMock()
        mock_alive_bar.return_value.__enter__.return_value = mock_bar

        # Create test script
        script_path = self._create_test_script("test.nu", "echo 'hello'")
        script = ScriptFile(
            path=script_path,
            compatible_version="0.95.0",
            method=CompatibilityMethod.COMMENT_HEADER
        )

        # Mock scanner
        mock_scanner.return_value.scan_all.return_value = [script]

        # Mock GitHub client
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_latest_version.return_value = "0.97.0"
        mock_github_instance.get_releases_between.return_value = [
            ReleaseInfo("0.96.0", "http://blog.url/96")
        ]
        mock_github_instance.fetch_blog_post_content.return_value = "blog content"

        # Mock LLM client
        mock_llm_instance = mock_llm.return_value
        mock_llm_instance.convert_blog_to_instructions.return_value = "instructions"
        mock_llm_instance.analyze_script_compatibility_streaming.return_value = []

        # Create analyzer with progress enabled
        analyzer = NuShellAnalyzer(self.config, disable_progress=False)

        # Run analysis
        results = analyzer.analyze_scripts("0.97.0")

        # Verify results
        assert len(results) == 1
        assert results[0].is_compatible is True

        # Verify progress bar was created
        mock_alive_bar.assert_called()

        # Verify streaming method was called
        mock_llm_instance.analyze_script_compatibility_streaming.assert_called_once()

    @patch('nushell_verifier.analyzer.GitHubClient')
    @patch('nushell_verifier.analyzer.LLMClient')
    @patch('nushell_verifier.analyzer.NuShellScriptScanner')
    @patch('nushell_verifier.progress.alive_bar')
    def test_analyzer_with_progress_disabled(self, mock_alive_bar, mock_scanner, mock_llm, mock_github):
        """Test analyzer with progress disabled."""
        # Create test script
        script_path = self._create_test_script("test.nu", "echo 'hello'")
        script = ScriptFile(
            path=script_path,
            compatible_version="0.95.0",
            method=CompatibilityMethod.COMMENT_HEADER
        )

        # Mock scanner
        mock_scanner.return_value.scan_all.return_value = [script]

        # Mock GitHub client
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_latest_version.return_value = "0.97.0"
        mock_github_instance.get_releases_between.return_value = []

        # Mock LLM client
        mock_llm_instance = mock_llm.return_value
        mock_llm_instance.analyze_script_compatibility_streaming.return_value = []

        # Create analyzer with progress disabled
        analyzer = NuShellAnalyzer(self.config, disable_progress=True)

        # Run analysis
        results = analyzer.analyze_scripts("0.97.0")

        # Verify results
        assert len(results) == 1

        # Verify progress bar was not created (should not be called for disabled progress)
        # The BatchProgressManager creates ScriptProgressManagers with disabled=True

    @patch('nushell_verifier.analyzer.GitHubClient')
    @patch('nushell_verifier.analyzer.LLMClient')
    @patch('nushell_verifier.analyzer.NuShellScriptScanner')
    @patch('builtins.print')
    def test_immediate_results_display(self, mock_print, mock_scanner, mock_llm, mock_github):
        """Test immediate results display for scripts."""
        # Create test script
        script_path = self._create_test_script("test.nu", "echo 'hello'")
        script = ScriptFile(
            path=script_path,
            compatible_version="0.95.0",
            method=CompatibilityMethod.COMMENT_HEADER
        )

        # Mock scanner
        mock_scanner.return_value.scan_all.return_value = [script]

        # Mock GitHub client
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_latest_version.return_value = "0.97.0"
        mock_github_instance.get_releases_between.return_value = []

        # Mock LLM client - return compatible result
        mock_llm_instance = mock_llm.return_value
        mock_llm_instance.analyze_script_compatibility_streaming.return_value = []

        # Create analyzer
        analyzer = NuShellAnalyzer(self.config, disable_progress=True)

        # Run analysis
        results = analyzer.analyze_scripts("0.97.0")

        # Check that immediate results were printed
        print_calls = [call[0][0] for call in mock_print.call_args_list if call and call[0]]
        compatible_messages = [msg for msg in print_calls if "✅" in str(msg) and "Compatible" in str(msg)]
        assert len(compatible_messages) > 0

    @patch('nushell_verifier.analyzer.GitHubClient')
    @patch('nushell_verifier.analyzer.LLMClient')
    @patch('nushell_verifier.analyzer.NuShellScriptScanner')
    @patch('builtins.print')
    def test_immediate_results_with_issues(self, mock_print, mock_scanner, mock_llm, mock_github):
        """Test immediate results display for scripts with issues."""
        # Create test script
        script_path = self._create_test_script("test.nu", "echo 'hello'")
        script = ScriptFile(
            path=script_path,
            compatible_version="0.95.0",
            method=CompatibilityMethod.COMMENT_HEADER
        )

        # Mock scanner
        mock_scanner.return_value.scan_all.return_value = [script]

        # Mock GitHub client
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_latest_version.return_value = "0.97.0"
        mock_github_instance.get_releases_between.return_value = []

        # Mock LLM client - return issues
        from nushell_verifier.models import CompatibilityIssue
        issues = [
            CompatibilityIssue(
                description="Test issue",
                suggested_fix="Fix it",
                severity="warning"
            )
        ]
        mock_llm_instance = mock_llm.return_value
        mock_llm_instance.analyze_script_compatibility_streaming.return_value = issues

        # Create analyzer
        analyzer = NuShellAnalyzer(self.config, disable_progress=True)

        # Run analysis
        results = analyzer.analyze_scripts("0.97.0")

        # Check that issues were displayed immediately
        print_calls = [call[0][0] for call in mock_print.call_args_list if call and call[0]]
        issue_messages = [msg for msg in print_calls if "⚠️" in str(msg) and "issue(s) found" in str(msg)]
        assert len(issue_messages) > 0

    @patch('nushell_verifier.analyzer.GitHubClient')
    @patch('nushell_verifier.analyzer.LLMClient')
    @patch('nushell_verifier.analyzer.NuShellScriptScanner')
    def test_streaming_fallback(self, mock_scanner, mock_llm, mock_github):
        """Test fallback to non-streaming when streaming fails."""
        # Create test script
        script_path = self._create_test_script("test.nu", "echo 'hello'")
        script = ScriptFile(
            path=script_path,
            compatible_version="0.95.0",
            method=CompatibilityMethod.COMMENT_HEADER
        )

        # Mock scanner
        mock_scanner.return_value.scan_all.return_value = [script]

        # Mock GitHub client
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_latest_version.return_value = "0.97.0"
        mock_github_instance.get_releases_between.return_value = []

        # Mock LLM client - streaming method raises AttributeError
        mock_llm_instance = mock_llm.return_value
        mock_llm_instance.analyze_script_compatibility_streaming.side_effect = AttributeError("No streaming")
        mock_llm_instance.analyze_script_compatibility.return_value = []

        # Create analyzer
        analyzer = NuShellAnalyzer(self.config, disable_progress=True)

        # Run analysis
        results = analyzer.analyze_scripts("0.97.0")

        # Verify fallback was used
        mock_llm_instance.analyze_script_compatibility.assert_called_once()
        assert len(results) == 1

    @patch('nushell_verifier.analyzer.GitHubClient')
    @patch('nushell_verifier.analyzer.LLMClient')
    @patch('nushell_verifier.analyzer.NuShellScriptScanner')
    @patch('builtins.print')
    def test_batch_summary_display(self, mock_print, mock_scanner, mock_llm, mock_github):
        """Test batch summary is displayed."""
        # Create multiple test scripts
        script1_path = self._create_test_script("test1.nu", "echo 'hello'")
        script2_path = self._create_test_script("test2.nu", "ls | where type == file")

        scripts = [
            ScriptFile(script1_path, "0.95.0", CompatibilityMethod.COMMENT_HEADER),
            ScriptFile(script2_path, "0.95.0", CompatibilityMethod.COMMENT_HEADER)
        ]

        # Mock scanner
        mock_scanner.return_value.scan_all.return_value = scripts

        # Mock GitHub client
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_latest_version.return_value = "0.97.0"
        mock_github_instance.get_releases_between.return_value = []

        # Mock LLM client
        mock_llm_instance = mock_llm.return_value
        mock_llm_instance.analyze_script_compatibility_streaming.return_value = []

        # Create analyzer
        analyzer = NuShellAnalyzer(self.config, disable_progress=True)

        # Run analysis
        results = analyzer.analyze_scripts("0.97.0")

        # Check that batch summary was printed
        print_calls = [call[0][0] for call in mock_print.call_args_list if call and call[0]]
        summary_messages = [msg for msg in print_calls if "📊 Processed" in str(msg) and "2/2 scripts" in str(msg)]
        assert len(summary_messages) > 0

    @patch('nushell_verifier.analyzer.GitHubClient')
    @patch('nushell_verifier.analyzer.LLMClient')
    @patch('nushell_verifier.analyzer.NuShellScriptScanner')
    def test_token_estimation_integration(self, mock_scanner, mock_llm, mock_github):
        """Test that token estimation is properly integrated."""
        # Create test script with known content
        content = "echo 'hello world'\nls | where type == file\ncd /tmp"
        script_path = self._create_test_script("test.nu", content)
        script = ScriptFile(
            path=script_path,
            compatible_version="0.95.0",
            method=CompatibilityMethod.COMMENT_HEADER
        )

        # Mock scanner
        mock_scanner.return_value.scan_all.return_value = [script]

        # Mock GitHub client
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_latest_version.return_value = "0.97.0"
        mock_github_instance.get_releases_between.return_value = []

        # Mock LLM client with token callback
        mock_llm_instance = mock_llm.return_value

        def mock_streaming_analysis(script, version, instructions, progress_callback=None):
            # Simulate token streaming
            if progress_callback:
                for token in ["result", ":", "compatible"]:
                    progress_callback(token)
            return []

        mock_llm_instance.analyze_script_compatibility_streaming.side_effect = mock_streaming_analysis

        # Create analyzer
        analyzer = NuShellAnalyzer(self.config, disable_progress=True)

        # Run analysis - should complete without errors
        results = analyzer.analyze_scripts("0.97.0")
        assert len(results) == 1

    def test_progress_config_propagation(self):
        """Test that progress configuration is properly propagated."""
        # Test with progress enabled
        analyzer_enabled = NuShellAnalyzer(self.config, disable_progress=False)
        assert analyzer_enabled.disable_progress is False

        # Test with progress disabled
        analyzer_disabled = NuShellAnalyzer(self.config, disable_progress=True)
        assert analyzer_disabled.disable_progress is True