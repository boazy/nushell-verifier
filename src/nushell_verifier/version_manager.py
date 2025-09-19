import re
from typing import List, Tuple


class VersionManager:
    """Manager for version-related operations."""

    VERSION_COMMENT_PATTERN = re.compile(r"^\s*#\s*nushell-compatible-with:\s*([^\s]+)")

    def calculate_default_version(self, current_version: str) -> str:
        """Calculate default version (6 minor versions behind current)."""
        try:
            parts = current_version.lstrip("v").split(".")
            major = int(parts[0])
            minor = int(parts[1])

            # Subtract 6 minor versions
            new_minor = max(0, minor - 6)
            return f"{major}.{new_minor}.0"

        except (ValueError, IndexError):
            # Fallback if version parsing fails
            return "0.90.0"

    def find_earliest_version(self, versions: List[str]) -> str:
        """Find the earliest version from a list of versions."""
        if not versions:
            return "0.90.0"

        def version_tuple(v: str) -> Tuple[int, ...]:
            try:
                return tuple(map(int, v.lstrip("v").split(".")))
            except ValueError:
                return (0, 0, 0)

        return min(versions, key=version_tuple)

    def is_version_after(self, version: str, reference: str) -> bool:
        """Check if version is after (newer than) reference version."""
        def version_tuple(v: str) -> Tuple[int, ...]:
            try:
                return tuple(map(int, v.lstrip("v").split(".")))
            except ValueError:
                return (0, 0, 0)

        return version_tuple(version) > version_tuple(reference)

    def is_version_same_or_after(self, version: str, reference: str) -> bool:
        """Check if version is same or after (newer than or equal to) reference version."""
        def version_tuple(v: str) -> Tuple[int, ...]:
            try:
                return tuple(map(int, v.lstrip("v").split(".")))
            except ValueError:
                return (0, 0, 0)

        return version_tuple(version) >= version_tuple(reference)

    def update_version_comment(self, lines: List[str], new_version: str) -> List[str]:
        """Update or add version comment in script lines."""
        new_comment = f"# nushell-compatible-with: {new_version}\n"
        updated_lines = lines.copy()

        # Look for existing version comment in header
        existing_comment_line = None

        for i, line in enumerate(lines):
            if self.VERSION_COMMENT_PATTERN.match(line):
                existing_comment_line = i
                break

            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                break

        if existing_comment_line is not None:
            # Replace existing comment
            updated_lines[existing_comment_line] = new_comment
        else:
            # Add new comment
            insert_position = 0

            # If there's a shebang, insert after it (with blank line)
            if lines and lines[0].strip().startswith("#!"):
                insert_position = 1
                if len(lines) > 1 and lines[1].strip() == "":
                    insert_position = 2
                else:
                    # Add blank line after shebang
                    updated_lines.insert(1, "\n")
                    insert_position = 2

            # Insert the version comment
            updated_lines.insert(insert_position, new_comment)

            # Add blank line after version comment if next line isn't blank
            if (insert_position + 1 < len(updated_lines) and
                updated_lines[insert_position + 1].strip() != ""):
                updated_lines.insert(insert_position + 1, "\n")

        return updated_lines