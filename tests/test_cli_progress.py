"""
Tests for CLI integration with progress functionality.
"""
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner
from nushell_verifier.cli import cli


class TestCLIProgress:
    """Test CLI integration with progress system."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runner = CliRunner()

    def teardown_method(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    @patch('nushell_verifier.analyzer.NuShellAnalyzer')
    @patch('nushell_verifier.reporter.Reporter')
    @patch('nushell_verifier.config.load_config')
    def test_no_progress_flag(self, mock_load_config, mock_reporter, mock_analyzer):
        """Test --no-progress flag is passed to analyzer."""
        # Mock config
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        # Mock analyzer
        mock_analyzer_instance = mock_analyzer.return_value
        mock_analyzer_instance.analyze_scripts.return_value = []

        # Mock reporter
        mock_reporter_instance = mock_reporter.return_value

        # Run CLI with --no-progress flag
        result = self.runner.invoke(cli, [
            '--no-progress',
            '--directory', self.temp_dir.name
        ])

        assert result.exit_code == 0

        # Verify analyzer was initialized with disable_progress=True
        mock_analyzer.assert_called_once_with(mock_config, disable_progress=True)

    @patch('nushell_verifier.analyzer.NuShellAnalyzer')
    @patch('nushell_verifier.reporter.Reporter')
    @patch('nushell_verifier.config.load_config')
    def test_progress_enabled_by_default(self, mock_load_config, mock_reporter, mock_analyzer):
        """Test progress is enabled by default."""
        # Mock config
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        # Mock analyzer
        mock_analyzer_instance = mock_analyzer.return_value
        mock_analyzer_instance.analyze_scripts.return_value = []

        # Mock reporter
        mock_reporter_instance = mock_reporter.return_value

        # Run CLI without --no-progress flag
        result = self.runner.invoke(cli, [
            '--directory', self.temp_dir.name
        ])

        assert result.exit_code == 0

        # Verify analyzer was initialized with disable_progress=False
        mock_analyzer.assert_called_once_with(mock_config, disable_progress=False)

    @patch('nushell_verifier.analyzer.NuShellAnalyzer')
    @patch('nushell_verifier.reporter.Reporter')
    @patch('nushell_verifier.config.load_config')
    def test_no_progress_with_other_flags(self, mock_load_config, mock_reporter, mock_analyzer):
        """Test --no-progress works with other CLI flags."""
        # Mock config
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        # Mock analyzer
        mock_analyzer_instance = mock_analyzer.return_value
        mock_analyzer_instance.analyze_scripts.return_value = []

        # Mock reporter
        mock_reporter_instance = mock_reporter.return_value

        # Run CLI with --no-progress and other flags
        result = self.runner.invoke(cli, [
            '--no-progress',
            '--verbose',
            '--no-cache',
            '--version', '0.97.0',
            '--directory', self.temp_dir.name
        ])

        assert result.exit_code == 0

        # Verify flags were processed correctly
        mock_analyzer.assert_called_once_with(mock_config, disable_progress=True)
        mock_reporter.assert_called_once_with(verbose=True)

        # Verify analyze_scripts was called with correct version
        mock_analyzer_instance.analyze_scripts.assert_called_once_with(target_version='0.97.0')

    @patch('nushell_verifier.cache.InstructionCache')
    def test_no_progress_with_cache_commands(self, mock_cache):
        """Test --no-progress doesn't interfere with cache commands."""
        # Mock cache
        mock_cache_instance = mock_cache.return_value
        mock_cache_instance.get_cache_info.return_value = {
            'cache_directory': '/test/cache',
            'exists': False,
            'file_count': 0,
            'total_size_mb': 0,
            'versions': []
        }

        # Test --cache-info with --no-progress
        result = self.runner.invoke(cli, ['--no-progress', '--cache-info'])
        assert result.exit_code == 0
        assert "Cache Information:" in result.output

        # Test --clear-cache with --no-progress
        mock_cache_instance.clear_cache.return_value = 0
        result = self.runner.invoke(cli, ['--no-progress', '--clear-cache'])
        assert result.exit_code == 0
        assert "Cache was already empty" in result.output

    def test_cli_help_includes_no_progress(self):
        """Test that CLI help includes --no-progress option."""
        result = self.runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert '--no-progress' in result.output
        assert 'Disable progress bars and spinners' in result.output

    @patch('nushell_verifier.analyzer.NuShellAnalyzer')
    @patch('nushell_verifier.reporter.Reporter')
    @patch('nushell_verifier.config.load_config')
    def test_exception_handling_with_progress(self, mock_load_config, mock_reporter, mock_analyzer):
        """Test exception handling when progress is enabled/disabled."""
        # Mock config
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        # Mock analyzer to raise exception
        mock_analyzer_instance = mock_analyzer.return_value
        mock_analyzer_instance.analyze_scripts.side_effect = RuntimeError("Test error")

        # Test with progress enabled
        result = self.runner.invoke(cli, ['--directory', self.temp_dir.name])
        assert result.exit_code == 1
        assert "Error: Test error" in result.output

        # Test with progress disabled
        result = self.runner.invoke(cli, ['--no-progress', '--directory', self.temp_dir.name])
        assert result.exit_code == 1
        assert "Error: Test error" in result.output

    @patch('nushell_verifier.analyzer.NuShellAnalyzer')
    @patch('nushell_verifier.reporter.Reporter')
    @patch('nushell_verifier.config.load_config')
    def test_config_overrides_with_progress(self, mock_load_config, mock_reporter, mock_analyzer):
        """Test configuration overrides work with progress options."""
        # Mock config
        mock_config = MagicMock()
        mock_config.scan_directories = ['default_dir']
        mock_config.cache_enabled = True
        mock_load_config.return_value = mock_config

        # Mock analyzer
        mock_analyzer_instance = mock_analyzer.return_value
        mock_analyzer_instance.analyze_scripts.return_value = []

        # Run CLI with overrides and progress disabled
        result = self.runner.invoke(cli, [
            '--no-progress',
            '--no-cache',
            '--directory', self.temp_dir.name,
            '--directory', '/another/dir'
        ])

        assert result.exit_code == 0

        # Verify config was modified correctly
        assert mock_config.scan_directories == [self.temp_dir.name, '/another/dir']
        assert mock_config.cache_enabled is False

        # Verify analyzer was initialized correctly
        mock_analyzer.assert_called_once_with(mock_config, disable_progress=True)

    @patch('nushell_verifier.analyzer.NuShellAnalyzer')
    @patch('nushell_verifier.reporter.Reporter')
    @patch('nushell_verifier.config.load_config')
    def test_progress_flag_type_checking(self, mock_load_config, mock_reporter, mock_analyzer):
        """Test that progress flag is properly typed as boolean."""
        # Mock config
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config

        # Mock analyzer
        mock_analyzer_instance = mock_analyzer.return_value
        mock_analyzer_instance.analyze_scripts.return_value = []

        # Run CLI
        result = self.runner.invoke(cli, ['--no-progress'])
        assert result.exit_code == 0

        # Check that the disable_progress parameter was passed as a boolean
        args, kwargs = mock_analyzer.call_args
        assert 'disable_progress' in kwargs
        assert isinstance(kwargs['disable_progress'], bool)
        assert kwargs['disable_progress'] is True

    def test_no_progress_flag_mutually_exclusive_with_cache_flags(self):
        """Test that --no-progress can be used with cache management flags."""
        # This test ensures --no-progress doesn't conflict with cache commands
        # Cache commands should exit early, so progress setting shouldn't matter

        # Test --no-progress with --cache-info
        with patch('nushell_verifier.cache.InstructionCache') as mock_cache:
            mock_cache_instance = mock_cache.return_value
            mock_cache_instance.get_cache_info.return_value = {
                'cache_directory': '/test',
                'exists': False,
                'file_count': 0,
                'total_size_mb': 0,
                'versions': []
            }

            result = self.runner.invoke(cli, ['--no-progress', '--cache-info'])
            assert result.exit_code == 0

        # Test --no-progress with --clear-cache
        with patch('nushell_verifier.cache.InstructionCache') as mock_cache:
            mock_cache_instance = mock_cache.return_value
            mock_cache_instance.clear_cache.return_value = 0

            result = self.runner.invoke(cli, ['--no-progress', '--clear-cache'])
            assert result.exit_code == 0