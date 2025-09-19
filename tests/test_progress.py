"""
Tests for progress management functionality.
"""
import tempfile
import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from nushell_verifier.progress import (
    ProgressConfig,
    ScriptProgressManager,
    BatchProgressManager,
    estimate_tokens_for_script,
    StreamingProgressCallback
)


class TestProgressConfig:
    """Test progress configuration."""

    def test_default_config(self):
        """Test default progress configuration."""
        config = ProgressConfig()
        assert config.enabled is True
        assert config.show_tokens is True
        assert config.show_phases is True
        assert config.update_interval == 0.1

    def test_custom_config(self):
        """Test custom progress configuration."""
        config = ProgressConfig(
            enabled=False,
            show_tokens=False,
            show_phases=False,
            update_interval=0.5
        )
        assert config.enabled is False
        assert config.show_tokens is False
        assert config.show_phases is False
        assert config.update_interval == 0.5


class TestScriptProgressManager:
    """Test script progress manager."""

    def test_init_enabled(self):
        """Test progress manager initialization when enabled."""
        manager = ScriptProgressManager("test_script.nu")
        assert manager.script_name == "test_script.nu"
        assert manager.config.enabled is True
        assert manager.disabled is False

    def test_init_disabled(self):
        """Test progress manager initialization when disabled."""
        manager = ScriptProgressManager("test_script.nu", disable_progress=True)
        assert manager.disabled is True

    def test_init_disabled_via_config(self):
        """Test progress manager disabled via config."""
        config = ProgressConfig(enabled=False)
        manager = ScriptProgressManager("test_script.nu", config=config)
        assert manager.disabled is True

    @patch('nushell_verifier.progress.alive_bar')
    def test_context_manager_enabled(self, mock_alive_bar):
        """Test context manager when progress is enabled."""
        mock_bar = MagicMock()
        mock_alive_bar.return_value.__enter__.return_value = mock_bar

        manager = ScriptProgressManager("test_script.nu")

        with manager:
            assert manager._bar is not None

        # Verify bar was created and cleaned up
        mock_alive_bar.assert_called_once()
        mock_bar.__exit__.assert_called_once()

    def test_context_manager_disabled(self):
        """Test context manager when progress is disabled."""
        manager = ScriptProgressManager("test_script.nu", disable_progress=True)

        with manager:
            assert manager._bar is None

    @patch('nushell_verifier.progress.alive_bar')
    def test_set_phase(self, mock_alive_bar):
        """Test setting phases."""
        mock_bar = MagicMock()
        mock_alive_bar.return_value.__enter__.return_value = mock_bar

        manager = ScriptProgressManager("test_script.nu")

        with manager:
            manager.set_phase("Testing phase", estimated_tokens=100)
            assert manager._current_phase == "Testing phase"
            assert manager._estimated_tokens == 100

    @patch('nushell_verifier.progress.alive_bar')
    def test_update_tokens(self, mock_alive_bar):
        """Test token updates."""
        mock_bar = MagicMock()
        mock_alive_bar.return_value.__enter__.return_value = mock_bar

        manager = ScriptProgressManager("test_script.nu")

        with manager:
            manager.update_tokens(10)
            assert manager._token_count == 10

            manager.update_tokens(5, total_estimated=50)
            assert manager._token_count == 15
            assert manager._estimated_tokens == 50

    @patch('nushell_verifier.progress.alive_bar')
    def test_set_tokens(self, mock_alive_bar):
        """Test setting absolute token count."""
        mock_bar = MagicMock()
        mock_alive_bar.return_value.__enter__.return_value = mock_bar

        manager = ScriptProgressManager("test_script.nu")

        with manager:
            manager.set_tokens(25, total_estimated=100)
            assert manager._token_count == 25
            assert manager._estimated_tokens == 100

    def test_disabled_operations(self):
        """Test that operations on disabled manager don't crash."""
        manager = ScriptProgressManager("test_script.nu", disable_progress=True)

        with manager:
            # These should not crash
            manager.set_phase("Test phase")
            manager.update_tokens(10)
            manager.set_tokens(20)
            manager.complete()


class TestBatchProgressManager:
    """Test batch progress manager."""

    def test_init(self):
        """Test batch progress manager initialization."""
        manager = BatchProgressManager(5)
        assert manager.total_scripts == 5
        assert manager.current_script == 0

    def test_start_script_single(self):
        """Test starting script analysis for single script."""
        manager = BatchProgressManager(1)
        script_manager = manager.start_script("test.nu")

        assert manager.current_script == 1
        assert script_manager.script_name == "test.nu"

    def test_start_script_batch(self):
        """Test starting script analysis for batch."""
        manager = BatchProgressManager(3)

        script_manager1 = manager.start_script("test1.nu")
        assert script_manager1.script_name == "[1/3] test1.nu"

        script_manager2 = manager.start_script("test2.nu")
        assert script_manager2.script_name == "[2/3] test2.nu"

    def test_start_script_disabled(self):
        """Test starting script with progress disabled."""
        config = ProgressConfig(enabled=False)
        manager = BatchProgressManager(2, config)

        script_manager = manager.start_script("test.nu")
        assert script_manager.disabled is True

    def test_get_batch_summary(self):
        """Test batch summary generation."""
        manager = BatchProgressManager(2)
        manager.start_script("test1.nu")
        manager.start_script("test2.nu")

        summary = manager.get_batch_summary()
        assert "Processed 2/2 scripts" in summary
        assert "avg:" in summary


class TestEstimateTokens:
    """Test token estimation functionality."""

    def test_estimate_tokens_for_script(self):
        """Test token estimation for a script file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nu', delete=False) as f:
            f.write("echo 'Hello, world!'\nls | where type == file")
            f.flush()

            try:
                estimate = estimate_tokens_for_script(Path(f.name))
                assert isinstance(estimate, int)
                assert 500 <= estimate <= 3000  # Within expected bounds
            finally:
                Path(f.name).unlink()

    def test_estimate_tokens_missing_file(self):
        """Test token estimation for missing file."""
        estimate = estimate_tokens_for_script(Path("/nonexistent/file.nu"))
        assert estimate == 1000  # Default estimate

    def test_estimate_tokens_empty_file(self):
        """Test token estimation for empty file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nu', delete=False) as f:
            f.write("")
            f.flush()

            try:
                estimate = estimate_tokens_for_script(Path(f.name))
                assert estimate >= 500  # Minimum estimate
            finally:
                Path(f.name).unlink()

    def test_estimate_tokens_large_file(self):
        """Test token estimation for large file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nu', delete=False) as f:
            # Write a large script
            content = "echo 'test'\n" * 1000
            f.write(content)
            f.flush()

            try:
                estimate = estimate_tokens_for_script(Path(f.name))
                assert estimate == 3000  # Clamped to maximum
            finally:
                Path(f.name).unlink()


class TestStreamingProgressCallback:
    """Test streaming progress callback."""

    def test_init(self):
        """Test callback initialization."""
        manager = ScriptProgressManager("test.nu", disable_progress=True)
        callback = StreamingProgressCallback(manager)

        assert callback.progress_manager is manager
        assert callback.total_tokens == 0
        assert callback.completion_tokens == 0

    def test_on_token(self):
        """Test token callback."""
        manager = ScriptProgressManager("test.nu", disable_progress=True)
        callback = StreamingProgressCallback(manager)

        callback.on_token("hello")
        assert callback.completion_tokens == 1

        callback.on_token("world")
        assert callback.completion_tokens == 2

        # Empty tokens shouldn't count
        callback.on_token("")
        callback.on_token("   ")
        assert callback.completion_tokens == 2

    def test_on_usage_update(self):
        """Test usage information callback."""
        manager = ScriptProgressManager("test.nu", disable_progress=True)
        callback = StreamingProgressCallback(manager)

        usage_info = {
            "total_tokens": 150,
            "completion_tokens": 50,
            "prompt_tokens": 100
        }

        callback.on_usage_update(usage_info)
        assert callback.total_tokens == 150
        assert callback.completion_tokens == 50

    def test_on_usage_update_partial(self):
        """Test usage update with partial information."""
        manager = ScriptProgressManager("test.nu", disable_progress=True)
        callback = StreamingProgressCallback(manager)

        # Update only total tokens
        callback.on_usage_update({"total_tokens": 100})
        assert callback.total_tokens == 100
        assert callback.completion_tokens == 0

        # Update only completion tokens
        callback.on_usage_update({"completion_tokens": 25})
        assert callback.total_tokens == 100
        assert callback.completion_tokens == 25


class TestProgressIntegration:
    """Integration tests for progress functionality."""

    @patch('nushell_verifier.progress.alive_bar')
    def test_full_progress_cycle(self, mock_alive_bar):
        """Test complete progress cycle."""
        mock_bar = MagicMock()
        mock_alive_bar.return_value.__enter__.return_value = mock_bar

        # Create batch manager
        batch_manager = BatchProgressManager(2)

        # Process first script
        script1 = batch_manager.start_script("script1.nu")
        with script1:
            script1.set_phase("Analysis", 100)
            script1.update_tokens(25)
            script1.update_tokens(25)
            script1.complete()

        # Process second script
        script2 = batch_manager.start_script("script2.nu")
        with script2:
            script2.set_phase("Analysis", 80)
            script2.set_tokens(80, 80)  # Complete
            script2.complete()

        # Get summary
        summary = batch_manager.get_batch_summary()
        assert "2/2 scripts" in summary

    def test_progress_with_streaming_callback(self):
        """Test progress integration with streaming callback."""
        manager = ScriptProgressManager("test.nu", disable_progress=True)
        callback = StreamingProgressCallback(manager)

        # Simulate streaming tokens
        tokens = ["def", " test", " [", "]", " {", " echo", " 'hello'", " }"]
        for token in tokens:
            callback.on_token(token)

        assert callback.completion_tokens == len(tokens)

        # Simulate final usage update
        callback.on_usage_update({
            "total_tokens": 120,
            "completion_tokens": len(tokens),
            "prompt_tokens": 120 - len(tokens)
        })

        assert callback.total_tokens == 120

    def test_disabled_progress_integration(self):
        """Test that disabled progress doesn't interfere with functionality."""
        config = ProgressConfig(enabled=False)
        batch_manager = BatchProgressManager(1, config)

        script_manager = batch_manager.start_script("test.nu")
        assert script_manager.disabled is True

        # All operations should work without errors
        with script_manager:
            script_manager.set_phase("Test")
            script_manager.update_tokens(10)
            script_manager.complete()

        summary = batch_manager.get_batch_summary()
        assert "1/1 scripts" in summary