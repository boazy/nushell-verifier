"""
Real-time progress management for script analysis.
"""
import time
from typing import Optional
from pathlib import Path
from alive_progress import alive_bar
from dataclasses import dataclass


@dataclass
class ProgressConfig:
    """Configuration for progress display."""
    enabled: bool = True
    show_tokens: bool = True
    show_phases: bool = True
    update_interval: float = 0.1  # seconds


class ScriptProgressManager:
    """Manages progress display for individual script analysis."""

    def __init__(
        self,
        script_name: str,
        config: Optional[ProgressConfig] = None,
        disable_progress: bool = False
    ):
        """Initialize progress manager for a script.

        Args:
            script_name: Name of the script being analyzed
            config: Progress configuration
            disable_progress: Whether to disable all progress display
        """
        self.script_name = script_name
        self.config = config or ProgressConfig()
        self.disabled = disable_progress or not self.config.enabled

        self._bar = None
        self._current_phase = "Initializing"
        self._token_count = 0
        self._estimated_tokens = None
        self._start_time = None
        self._phase_start_time = None

    def __enter__(self):
        """Enter context manager - start progress display."""
        if not self.disabled:
            self._start_time = time.time()
            self._phase_start_time = self._start_time

            # Create alive_bar with dynamic title
            self._bar = alive_bar(
                title=f"📄 {self.script_name}",
                length=20,
                spinner="classic",
                unknown="stars"
            ).__enter__()

            self.set_phase("Starting analysis")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - clean up progress display."""
        if not self.disabled and self._bar:
            try:
                self._bar.__exit__(exc_type, exc_val, exc_tb)
            except Exception:
                pass  # Ignore cleanup errors

    def set_phase(self, phase: str, estimated_tokens: Optional[int] = None):
        """Set the current processing phase.

        Args:
            phase: Description of current phase
            estimated_tokens: Estimated total tokens for this phase
        """
        if self.disabled:
            return

        self._current_phase = phase
        self._phase_start_time = time.time()
        self._token_count = 0
        self._estimated_tokens = estimated_tokens

        if self._bar and self.config.show_phases:
            # Update the progress bar title with current phase
            self._update_display()

    def update_tokens(self, new_tokens: int, total_estimated: Optional[int] = None):
        """Update token progress.

        Args:
            new_tokens: Number of new tokens processed
            total_estimated: Updated estimate of total tokens
        """
        if self.disabled:
            return

        self._token_count += new_tokens
        if total_estimated is not None:
            self._estimated_tokens = total_estimated

        if self._bar and self.config.show_tokens:
            self._update_display()

    def set_tokens(self, current_tokens: int, total_estimated: Optional[int] = None):
        """Set absolute token count.

        Args:
            current_tokens: Current token count
            total_estimated: Estimated total tokens
        """
        if self.disabled:
            return

        self._token_count = current_tokens
        if total_estimated is not None:
            self._estimated_tokens = total_estimated

        if self._bar and self.config.show_tokens:
            self._update_display()

    def _update_display(self):
        """Update the progress bar display."""
        if not self._bar:
            return

        # Build display text
        parts = []

        if self.config.show_phases:
            parts.append(f"Phase: {self._current_phase}")

        if self.config.show_tokens and self._token_count > 0:
            if self._estimated_tokens:
                percentage = min(100, (self._token_count / self._estimated_tokens) * 100)
                parts.append(f"Tokens: {self._token_count}/{self._estimated_tokens} ({percentage:.0f}%)")
            else:
                parts.append(f"Tokens: {self._token_count}")

        # Calculate processing speed
        if self._phase_start_time and self._token_count > 0:
            elapsed = time.time() - self._phase_start_time
            if elapsed > 0:
                tokens_per_sec = self._token_count / elapsed
                if tokens_per_sec > 1:
                    parts.append(f"{tokens_per_sec:.0f} tok/s")

        # Update bar text
        display_text = " | ".join(parts) if parts else self._current_phase
        self._bar.text(display_text)

        # Update progress if we have token estimates
        if self._estimated_tokens and self._token_count > 0:
            progress = min(1.0, self._token_count / self._estimated_tokens)
            self._bar(progress)
        else:
            # Just spin without progress
            self._bar()

    def complete(self):
        """Mark the current phase as complete."""
        if self.disabled:
            return

        self._current_phase = "Complete"
        if self._bar:
            self._update_display()


class BatchProgressManager:
    """Manages progress display for batch script processing."""

    def __init__(self, total_scripts: int, config: Optional[ProgressConfig] = None):
        """Initialize batch progress manager.

        Args:
            total_scripts: Total number of scripts to process
            config: Progress configuration
        """
        self.total_scripts = total_scripts
        self.config = config or ProgressConfig()
        self.current_script = 0
        self._start_time = time.time()

    def start_script(self, script_name: str) -> ScriptProgressManager:
        """Start processing a new script.

        Args:
            script_name: Name of the script to process

        Returns:
            ScriptProgressManager for the script
        """
        self.current_script += 1

        if not self.config.enabled:
            return ScriptProgressManager(script_name, self.config, disable_progress=True)

        # Add batch context to script name
        if self.total_scripts > 1:
            batch_info = f"[{self.current_script}/{self.total_scripts}]"
            display_name = f"{batch_info} {script_name}"
        else:
            display_name = script_name

        return ScriptProgressManager(display_name, self.config)

    def get_batch_summary(self) -> str:
        """Get summary of batch processing.

        Returns:
            Summary string with timing information
        """
        elapsed = time.time() - self._start_time
        avg_time = elapsed / max(1, self.current_script)

        return (
            f"📊 Processed {self.current_script}/{self.total_scripts} scripts in "
            f"{elapsed:.1f}s (avg: {avg_time:.1f}s per script)"
        )


def estimate_tokens_for_script(script_path: Path) -> int:
    """Estimate the number of tokens needed to analyze a script.

    Args:
        script_path: Path to the script file

    Returns:
        Estimated token count for analysis
    """
    try:
        # Read script to estimate complexity
        with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Basic estimation: ~4 characters per token
        script_tokens = len(content) // 4

        # Analysis overhead: instructions + reasoning
        analysis_overhead = 800

        # Response tokens: depends on complexity
        response_tokens = min(500, script_tokens // 2)

        total_estimate = script_tokens + analysis_overhead + response_tokens

        # Clamp to reasonable bounds
        return max(500, min(3000, total_estimate))

    except (OSError, UnicodeDecodeError):
        # Default estimate if we can't read the file
        return 1000


class StreamingProgressCallback:
    """Callback for LLM streaming progress updates."""

    def __init__(self, progress_manager: ScriptProgressManager):
        """Initialize callback with progress manager.

        Args:
            progress_manager: Progress manager to update
        """
        self.progress_manager = progress_manager
        self.total_tokens = 0
        self.completion_tokens = 0

    def on_token(self, token: str):
        """Called when a new token is received.

        Args:
            token: The new token content
        """
        # Count the token (rough estimation)
        if token and token.strip():
            self.completion_tokens += 1
            self.progress_manager.update_tokens(1)

    def on_usage_update(self, usage_info: dict):
        """Called when usage information is updated.

        Args:
            usage_info: Usage information from LLM response
        """
        if 'total_tokens' in usage_info:
            self.total_tokens = usage_info['total_tokens']

        if 'completion_tokens' in usage_info:
            self.completion_tokens = usage_info['completion_tokens']

        # Update progress with actual token counts
        self.progress_manager.set_tokens(
            self.completion_tokens,
            usage_info.get('total_tokens')
        )