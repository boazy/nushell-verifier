import re
from pathlib import Path
from typing import List, Generator, Optional
from .models import ScriptFile, CompatibilityMethod


class NuShellScriptScanner:
    """Scanner for NuShell script files."""

    NUSHELL_SHEBANG_PATTERN = re.compile(r"^#!\s*.*nu(?:shell)?(?:\s|$)")
    VERSION_COMMENT_PATTERN = re.compile(r"^\s*#\s*nushell-compatible-with:\s*([^\s]+)")

    def __init__(self, directories: List[str]):
        """Initialize scanner with directories to scan."""
        self.directories = [Path(d).expanduser() for d in directories]

    def scan_all(self) -> List[ScriptFile]:
        """Scan all directories for NuShell scripts."""
        scripts = []
        for directory in self.directories:
            if directory.exists():
                scripts.extend(self.scan_directory(directory))
        return scripts

    def scan_directory(self, directory: Path) -> List[ScriptFile]:
        """Recursively scan a directory for NuShell scripts."""
        scripts = []
        for file_path in self._find_nushell_files(directory):
            script = self._analyze_script_file(file_path)
            if script:
                scripts.append(script)
        return scripts

    def _find_nushell_files(self, directory: Path) -> Generator[Path, None, None]:
        """Find potential NuShell script files."""
        for file_path in directory.rglob("*"):
            if file_path.is_file() and self._is_nushell_file(file_path):
                yield file_path

    def _is_nushell_file(self, file_path: Path) -> bool:
        """Check if a file is a NuShell script."""
        # Check file extension
        if file_path.suffix == ".nu":
            return True

        # Check for shebang if no extension
        if not file_path.suffix:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    first_line = f.readline().strip()
                    return bool(self.NUSHELL_SHEBANG_PATTERN.match(first_line))
            except (OSError, UnicodeDecodeError):
                return False

        return False

    def _analyze_script_file(self, file_path: Path) -> Optional[ScriptFile]:
        """Analyze a script file to determine compatibility information."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            has_shebang = False
            if lines and self.NUSHELL_SHEBANG_PATTERN.match(lines[0].strip()):
                has_shebang = True

            # Look for version comment in header
            version, method = self._find_compatible_version(file_path, lines)

            return ScriptFile(
                path=file_path,
                compatible_version=version,
                method=method,
                has_shebang=has_shebang
            )

        except (OSError, UnicodeDecodeError):
            return None

    def _find_compatible_version(self, file_path: Path, lines: List[str]) -> tuple[str, CompatibilityMethod]:
        """Find the compatible version using the priority order specified."""
        # 1. Check for version comment in file header
        for i, line in enumerate(lines[:20]):  # Only check first 20 lines
            if line.strip() and not line.strip().startswith("#"):
                break  # Stop at first non-comment line

            match = self.VERSION_COMMENT_PATTERN.match(line)
            if match:
                return match.group(1), CompatibilityMethod.COMMENT_HEADER

        # 2. Check for .compatible-nushell-version file in directory hierarchy
        current_dir = file_path.parent
        for scan_dir in self.directories:
            while current_dir >= scan_dir:
                version_file = current_dir / ".compatible-nushell-version"
                if version_file.exists():
                    try:
                        with open(version_file, "r", encoding="utf-8") as f:
                            version = f.read().strip()
                            if version:
                                return version, CompatibilityMethod.DIRECTORY_FILE
                    except (OSError, UnicodeDecodeError):
                        pass
                current_dir = current_dir.parent

        # 3. Default assumption (6 minor versions behind current)
        return "0.90.0", CompatibilityMethod.DEFAULT_ASSUMPTION  # Will be calculated dynamically