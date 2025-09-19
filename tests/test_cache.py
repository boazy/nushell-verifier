"""
Tests for the instruction caching functionality.
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from nushell_verifier.cache import InstructionCache


class TestInstructionCache:
    """Test the InstructionCache class."""

    def setup_method(self):
        """Set up test environment with temporary cache directory."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp_dir.name)

        # Mock the cache directory to use our temp directory
        with patch('nushell_verifier.cache.get_cache_path', return_value=self.cache_dir):
            self.cache = InstructionCache()

    def teardown_method(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()

    def test_cache_directory_creation(self):
        """Test that cache directory is created properly."""
        # Instructions directory should not exist initially
        assert not self.cache.instructions_dir.exists()

        # Save instructions should create the directory
        self.cache.save_instructions("0.107.0", "test instructions", "gpt-4")

        assert self.cache.instructions_dir.exists()
        assert self.cache.instructions_dir.is_dir()

    def test_save_and_get_instructions(self):
        """Test saving and retrieving cached instructions."""
        version = "0.107.0"
        instructions = "Breaking changes:\n1. Command X changed\n2. Feature Y removed"
        model = "gpt-4"

        # Save instructions
        self.cache.save_instructions(version, instructions, model)

        # Retrieve instructions
        cached = self.cache.get_cached_instructions(version, model)

        assert cached == instructions

    def test_cache_miss_scenarios(self):
        """Test various cache miss scenarios."""
        version = "0.107.0"
        instructions = "test instructions"
        model = "gpt-4"

        # Save with gpt-4
        self.cache.save_instructions(version, instructions, model)

        # Miss: different version
        assert self.cache.get_cached_instructions("0.106.0", model) is None

        # Miss: different model
        assert self.cache.get_cached_instructions(version, "claude-3") is None

        # Miss: non-existent version
        assert self.cache.get_cached_instructions("0.999.0", model) is None

    def test_cache_file_format(self):
        """Test that cache files are saved in correct JSON format."""
        version = "0.107.0"
        instructions = "test instructions"
        model = "gpt-4"

        self.cache.save_instructions(version, instructions, model)

        safe_model = model.replace("/", "_")
        cache_file = self.cache.instructions_dir / f"{version}_{safe_model}.json"
        assert cache_file.exists()

        with open(cache_file, "r") as f:
            data = json.load(f)

        assert data["version"] == version
        assert data["instructions"] == instructions
        assert data["llm_model"] == model
        assert "created_at" in data
        assert "+00:00" in data["created_at"]  # UTC timezone indicator

    def test_corrupted_cache_handling(self):
        """Test handling of corrupted cache files."""
        version = "0.107.0"
        model = "gpt-4"
        cache_file = self.cache.instructions_dir
        cache_file.mkdir(parents=True, exist_ok=True)
        safe_model = model.replace("/", "_")
        cache_file = cache_file / f"{version}_{safe_model}.json"

        # Create corrupted JSON file
        with open(cache_file, "w") as f:
            f.write("{ invalid json")

        # Should return None for corrupted file
        result = self.cache.get_cached_instructions(version, model)
        assert result is None

    def test_cache_info_empty(self):
        """Test cache info when cache is empty."""
        info = self.cache.get_cache_info()

        assert info["exists"] is False
        assert info["file_count"] == 0
        assert info["total_size_bytes"] == 0
        assert info["versions"] == []
        assert "cache_directory" in info

    def test_cache_info_with_data(self):
        """Test cache info with cached data."""
        # Add some test data
        versions = ["0.105.0", "0.106.0", "0.107.0"]
        for version in versions:
            self.cache.save_instructions(version, f"instructions for {version}", "gpt-4")

        info = self.cache.get_cache_info()

        assert info["exists"] is True
        assert info["file_count"] == 3
        assert info["total_size_bytes"] > 0
        assert info["total_size_mb"] >= 0  # Small files might round to 0
        assert set(info["versions"]) == set(versions)
        assert info["cache_directory"] == str(self.cache.instructions_dir)

    def test_clear_cache_empty(self):
        """Test clearing empty cache."""
        removed_count = self.cache.clear_cache()
        assert removed_count == 0

    def test_clear_cache_with_data(self):
        """Test clearing cache with data."""
        # Add some test data
        versions = ["0.105.0", "0.106.0", "0.107.0"]
        for version in versions:
            self.cache.save_instructions(version, f"instructions for {version}", "gpt-4")

        # Verify files exist
        for version in versions:
            cache_file = self.cache.instructions_dir / f"{version}_gpt-4.json"
            assert cache_file.exists()

        # Clear cache
        removed_count = self.cache.clear_cache()
        assert removed_count == 3

        # Verify files are gone
        for version in versions:
            cache_file = self.cache.instructions_dir / f"{version}_gpt-4.json"
            assert not cache_file.exists()

        # Directory should be cleaned up too
        assert not self.cache.instructions_dir.exists()

    def test_validate_cache_entry_valid(self):
        """Test validation of valid cache entries."""
        version = "0.107.0"
        instructions = "test instructions"
        model = "gpt-4"

        self.cache.save_instructions(version, instructions, model)

        assert self.cache.validate_cache_entry(version, model) is True

    def test_validate_cache_entry_invalid(self):
        """Test validation of invalid cache entries."""
        version = "0.107.0"
        model = "gpt-4"

        # Non-existent file
        assert self.cache.validate_cache_entry(version, model) is False

        # Create invalid cache file
        self.cache.instructions_dir.mkdir(parents=True, exist_ok=True)
        safe_model = model.replace("/", "_")
        cache_file = self.cache.instructions_dir / f"{version}_{safe_model}.json"

        # Missing required fields
        with open(cache_file, "w") as f:
            json.dump({"version": version}, f)

        assert self.cache.validate_cache_entry(version, model) is False

        # Wrong version in file
        with open(cache_file, "w") as f:
            json.dump({
                "version": "0.106.0",  # Different from filename
                "instructions": "test",
                "created_at": "2025-01-01T00:00:00Z",
                "llm_model": "gpt-4"
            }, f)

        assert self.cache.validate_cache_entry(version, model) is False

    def test_model_change_invalidation(self):
        """Test that changing LLM model invalidates cache."""
        version = "0.107.0"
        instructions = "test instructions"

        # Save with gpt-4
        self.cache.save_instructions(version, instructions, "gpt-4")

        # Try to get with different model
        assert self.cache.get_cached_instructions(version, "claude-3") is None

        # Should still work with same model
        assert self.cache.get_cached_instructions(version, "gpt-4") == instructions

    def test_concurrent_access(self):
        """Test that cache handles concurrent-like access patterns."""
        version = "0.107.0"
        instructions = "test instructions"
        model = "gpt-4"

        # Simulate multiple saves (shouldn't cause issues)
        for i in range(5):
            self.cache.save_instructions(version, f"{instructions} v{i}", model)

        # Should have the last saved version
        cached = self.cache.get_cached_instructions(version, model)
        assert "v4" in cached

    def test_unicode_handling(self):
        """Test that cache handles Unicode content correctly."""
        version = "0.107.0"
        instructions = "Unicode test: 中文, 🚀, émojis"
        model = "gpt-4"

        self.cache.save_instructions(version, instructions, model)
        cached = self.cache.get_cached_instructions(version, model)

        assert cached == instructions

    def test_large_instructions(self):
        """Test cache with large instruction content."""
        version = "0.107.0"
        # Create a large instruction set
        instructions = "Breaking changes:\n" + "\n".join([
            f"- Change {i}: Some detailed description of breaking change {i}"
            for i in range(1000)
        ])
        model = "gpt-4"

        self.cache.save_instructions(version, instructions, model)
        cached = self.cache.get_cached_instructions(version, model)

        assert cached == instructions
        assert len(cached) > 10000  # Should be quite large