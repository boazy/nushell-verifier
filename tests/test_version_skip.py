"""
Tests for skipping scripts that are already compatible with target version.
"""
import tempfile
from pathlib import Path
from unittest.mock import patch
from nushell_verifier.analyzer import NuShellAnalyzer
from nushell_verifier.models import Config, ScriptFile, CompatibilityMethod
from nushell_verifier.version_manager import VersionManager


class TestVersionSkipping:
    """Test that scripts already compatible are skipped."""

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

    def test_is_version_same_or_after(self):
        """Test version comparison method."""
        vm = VersionManager()

        # Same version
        assert vm.is_version_same_or_after("0.97.0", "0.97.0") is True

        # Script is newer than target
        assert vm.is_version_same_or_after("0.98.0", "0.97.0") is True
        assert vm.is_version_same_or_after("1.0.0", "0.97.0") is True
        assert vm.is_version_same_or_after("0.97.1", "0.97.0") is True

        # Script is older than target
        assert vm.is_version_same_or_after("0.96.0", "0.97.0") is False
        assert vm.is_version_same_or_after("0.95.0", "0.97.0") is False

        # Handle version strings with 'v' prefix
        assert vm.is_version_same_or_after("v0.97.0", "0.97.0") is True
        assert vm.is_version_same_or_after("0.97.0", "v0.97.0") is True

    @patch('nushell_verifier.analyzer.GitHubClient')
    @patch('nushell_verifier.analyzer.LLMClient')
    @patch('nushell_verifier.analyzer.NuShellScriptScanner')
    @patch('builtins.print')
    def test_skip_compatible_script_same_version(self, mock_print, mock_scanner, mock_llm, mock_github):
        """Test skipping script with same version as target."""
        # Create test script
        script_path = Path(self.temp_dir.name) / "test.nu"
        script_path.write_text("echo 'hello'")

        script = ScriptFile(
            path=script_path,
            compatible_version="0.97.0",  # Same as target
            method=CompatibilityMethod.COMMENT_HEADER
        )

        # Mock scanner
        mock_scanner.return_value.scan_all.return_value = [script]

        # Mock GitHub client
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_latest_version.return_value = "0.97.0"
        mock_github_instance.get_releases_between.return_value = []

        # Create analyzer
        analyzer = NuShellAnalyzer(self.config, disable_progress=True)

        # Run analysis
        results = analyzer.analyze_scripts("0.97.0")

        # Verify script was skipped
        assert len(results) == 1
        assert results[0].is_compatible
        assert len(results[0].issues) == 0

        # Verify LLM was not called for analysis
        mock_llm.return_value.analyze_script_compatibility_streaming.assert_not_called()
        mock_llm.return_value.analyze_script_compatibility.assert_not_called()

        # Verify skip message was printed
        print_calls = [call[0][0] for call in mock_print.call_args_list if call and call[0]]
        skip_messages = [msg for msg in print_calls if "⏭️" in str(msg) and "Already compatible" in str(msg)]
        assert len(skip_messages) > 0

    @patch('nushell_verifier.analyzer.GitHubClient')
    @patch('nushell_verifier.analyzer.LLMClient')
    @patch('nushell_verifier.analyzer.NuShellScriptScanner')
    @patch('builtins.print')
    def test_skip_compatible_script_newer_version(self, mock_print, mock_scanner, mock_llm, mock_github):
        """Test skipping script with newer version than target."""
        # Create test script
        script_path = Path(self.temp_dir.name) / "test.nu"
        script_path.write_text("echo 'hello'")

        script = ScriptFile(
            path=script_path,
            compatible_version="0.98.0",  # Newer than target
            method=CompatibilityMethod.COMMENT_HEADER
        )

        # Mock scanner
        mock_scanner.return_value.scan_all.return_value = [script]

        # Mock GitHub client
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_latest_version.return_value = "0.97.0"
        mock_github_instance.get_releases_between.return_value = []

        # Create analyzer
        analyzer = NuShellAnalyzer(self.config, disable_progress=True)

        # Run analysis
        results = analyzer.analyze_scripts("0.97.0")

        # Verify script was skipped
        assert len(results) == 1
        assert results[0].is_compatible

        # Verify skip message shows correct versions
        print_calls = [call[0][0] for call in mock_print.call_args_list if call and call[0]]
        skip_messages = [msg for msg in print_calls if "v0.98.0 >= v0.97.0" in str(msg)]
        assert len(skip_messages) > 0

    @patch('nushell_verifier.analyzer.GitHubClient')
    @patch('nushell_verifier.analyzer.LLMClient')
    @patch('nushell_verifier.analyzer.NuShellScriptScanner')
    @patch('builtins.print')
    def test_analyze_older_script(self, mock_print, mock_scanner, mock_llm, mock_github):
        """Test that scripts with older versions are still analyzed."""
        # Create test script
        script_path = Path(self.temp_dir.name) / "test.nu"
        script_path.write_text("echo 'hello'")

        script = ScriptFile(
            path=script_path,
            compatible_version="0.95.0",  # Older than target
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

        # Create analyzer
        analyzer = NuShellAnalyzer(self.config, disable_progress=True)

        # Run analysis
        results = analyzer.analyze_scripts("0.97.0")

        # Verify script was analyzed (not skipped)
        assert len(results) == 1

        # Verify LLM was called for analysis
        mock_llm_instance.analyze_script_compatibility_streaming.assert_called_once()

        # Verify no skip message was printed
        print_calls = [call[0][0] for call in mock_print.call_args_list if call and call[0]]
        skip_messages = [msg for msg in print_calls if "⏭️" in str(msg)]
        assert len(skip_messages) == 0

    @patch('nushell_verifier.analyzer.GitHubClient')
    @patch('nushell_verifier.analyzer.LLMClient')
    @patch('nushell_verifier.analyzer.NuShellScriptScanner')
    @patch('builtins.print')
    def test_mixed_script_versions(self, mock_print, mock_scanner, mock_llm, mock_github):
        """Test mix of scripts - some skipped, some analyzed."""
        # Create test scripts
        script1_path = Path(self.temp_dir.name) / "old.nu"
        script1_path.write_text("echo 'old script'")
        script1 = ScriptFile(script1_path, "0.95.0", CompatibilityMethod.COMMENT_HEADER)

        script2_path = Path(self.temp_dir.name) / "current.nu"
        script2_path.write_text("echo 'current script'")
        script2 = ScriptFile(script2_path, "0.97.0", CompatibilityMethod.COMMENT_HEADER)

        script3_path = Path(self.temp_dir.name) / "newer.nu"
        script3_path.write_text("echo 'newer script'")
        script3 = ScriptFile(script3_path, "0.98.0", CompatibilityMethod.COMMENT_HEADER)

        scripts = [script1, script2, script3]

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

        # Verify all scripts have results
        assert len(results) == 3

        # Verify LLM was called only once (for the old script)
        assert mock_llm_instance.analyze_script_compatibility_streaming.call_count == 1

        # Verify skip messages for compatible scripts
        print_calls = [call[0][0] for call in mock_print.call_args_list if call and call[0]]
        skip_messages = [msg for msg in print_calls if "⏭️" in str(msg) and "Already compatible" in str(msg)]
        assert len(skip_messages) == 2  # current.nu and newer.nu should be skipped

    def test_version_comparison_edge_cases(self):
        """Test edge cases in version comparison."""
        vm = VersionManager()

        # Test with different version formats
        assert vm.is_version_same_or_after("0.97", "0.97.0") is False  # Different formats
        assert vm.is_version_same_or_after("0.97.0.1", "0.97.0") is True  # More components

        # Test with malformed versions (should handle gracefully)
        assert vm.is_version_same_or_after("invalid", "0.97.0") is False
        assert vm.is_version_same_or_after("0.97.0", "invalid") is True  # Valid >= invalid(0.0.0)

    @patch('nushell_verifier.analyzer.GitHubClient')
    @patch('nushell_verifier.analyzer.LLMClient')
    @patch('nushell_verifier.analyzer.NuShellScriptScanner')
    def test_skip_with_progress_disabled(self, mock_scanner, mock_llm, mock_github):
        """Test skipping works correctly with progress disabled."""
        # Create test script that should be skipped
        script_path = Path(self.temp_dir.name) / "test.nu"
        script_path.write_text("echo 'hello'")

        script = ScriptFile(
            path=script_path,
            compatible_version="0.97.0",
            method=CompatibilityMethod.COMMENT_HEADER
        )

        # Mock scanner
        mock_scanner.return_value.scan_all.return_value = [script]

        # Mock GitHub client
        mock_github_instance = mock_github.return_value
        mock_github_instance.get_latest_version.return_value = "0.97.0"
        mock_github_instance.get_releases_between.return_value = []

        # Create analyzer with progress disabled
        analyzer = NuShellAnalyzer(self.config, disable_progress=True)

        # Run analysis - should complete without errors
        results = analyzer.analyze_scripts("0.97.0")

        # Verify script was skipped properly
        assert len(results) == 1
        assert results[0].is_compatible