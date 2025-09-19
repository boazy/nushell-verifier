import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from .config import get_cache_path


class InstructionCache:
    """Cache manager for compatibility instructions."""

    def __init__(self):
        """Initialize cache manager."""
        self.cache_dir = get_cache_path()
        self.instructions_dir = self.cache_dir / "instructions"

    def get_cached_instructions(self, version: str, llm_model: str) -> Optional[str]:
        """Get cached compatibility instructions for a version and LLM model.

        Args:
            version: The NuShell version (e.g., "0.107.0")
            llm_model: The LLM model used (e.g., "gpt-4")

        Returns:
            Cached instructions if available and valid, None otherwise
        """
        # Create safe filename from model name
        safe_model = llm_model.replace("/", "_")
        cache_file = self.instructions_dir / f"{version}_{safe_model}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            # Validate cache structure
            required_fields = ["version", "instructions", "created_at", "llm_model"]
            if not all(field in cache_data for field in required_fields):
                return None

            # Check if the cached entry was created with the same LLM model
            if cache_data["llm_model"] != llm_model:
                return None

            # Validate version matches
            if cache_data["version"] != version:
                return None

            return cache_data["instructions"]

        except (json.JSONDecodeError, OSError, KeyError):
            # Cache file is corrupted or unreadable, ignore it
            return None

    def save_instructions(self, version: str, instructions: str, llm_model: str) -> None:
        """Save compatibility instructions to cache.

        Args:
            version: The NuShell version
            instructions: The compatibility instructions
            llm_model: The LLM model used to generate instructions
        """
        # Ensure cache directory exists
        self.instructions_dir.mkdir(parents=True, exist_ok=True)

        cache_data = {
            "version": version,
            "instructions": instructions,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "llm_model": llm_model
        }

        # Create safe filename from model name
        safe_model = llm_model.replace("/", "_")
        cache_file = self.instructions_dir / f"{version}_{safe_model}.json"

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            # Failed to write cache, but don't crash the application
            print(f"Warning: Could not save cache for {version}: {e}")

    def clear_cache(self) -> int:
        """Clear all cached instructions.

        Returns:
            Number of cache files removed
        """
        if not self.instructions_dir.exists():
            return 0

        removed_count = 0
        try:
            for cache_file in self.instructions_dir.glob("*.json"):
                cache_file.unlink()
                removed_count += 1

            # Remove directory if empty
            if not any(self.instructions_dir.iterdir()):
                self.instructions_dir.rmdir()

            # Remove parent cache directory if empty
            if not any(self.cache_dir.iterdir()):
                self.cache_dir.rmdir()

        except OSError as e:
            print(f"Warning: Could not completely clear cache: {e}")

        return removed_count

    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about the cache.

        Returns:
            Dictionary with cache statistics and directory path
        """
        if not self.instructions_dir.exists():
            return {
                "cache_directory": str(self.instructions_dir),
                "exists": False,
                "file_count": 0,
                "total_size_bytes": 0,
                "versions": []
            }

        cache_files = list(self.instructions_dir.glob("*.json"))
        total_size = 0
        versions = []

        for cache_file in cache_files:
            try:
                stat = cache_file.stat()
                total_size += stat.st_size

                # Extract version from filename (format: version_model.json)
                filename_parts = cache_file.stem.split("_", 1)
                if len(filename_parts) >= 1:
                    version = filename_parts[0]
                    if version not in versions:  # Avoid duplicates
                        versions.append(version)
            except OSError:
                pass

        return {
            "cache_directory": str(self.instructions_dir),
            "exists": True,
            "file_count": len(cache_files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "versions": sorted(versions)
        }

    def validate_cache_entry(self, version: str, llm_model: str = "gpt-4") -> bool:
        """Validate that a cache entry is well-formed.

        Args:
            version: The version to validate
            llm_model: The LLM model to validate for

        Returns:
            True if cache entry is valid, False otherwise
        """
        # Create safe filename from model name
        safe_model = llm_model.replace("/", "_")
        cache_file = self.instructions_dir / f"{version}_{safe_model}.json"

        if not cache_file.exists():
            return False

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            # Check required fields
            required_fields = ["version", "instructions", "created_at", "llm_model"]
            if not all(field in cache_data for field in required_fields):
                return False

            # Validate data types
            if not isinstance(cache_data["instructions"], str):
                return False

            if not isinstance(cache_data["version"], str):
                return False

            if not isinstance(cache_data["llm_model"], str):
                return False

            # Validate that version in file matches filename
            if cache_data["version"] != version:
                return False

            return True

        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            return False