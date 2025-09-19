import pytest
from nushell_verifier.version_manager import VersionManager


def test_calculate_default_version():
    """Test default version calculation."""
    vm = VersionManager()

    # Test normal case
    assert vm.calculate_default_version("0.96.0") == "0.90.0"
    assert vm.calculate_default_version("1.5.0") == "1.0.0"

    # Test edge case where minor would go negative
    assert vm.calculate_default_version("0.3.0") == "0.0.0"


def test_find_earliest_version():
    """Test finding earliest version from list."""
    vm = VersionManager()

    versions = ["0.95.0", "0.90.0", "0.92.0"]
    assert vm.find_earliest_version(versions) == "0.90.0"

    # Test empty list
    assert vm.find_earliest_version([]) == "0.90.0"


def test_is_version_after():
    """Test version comparison."""
    vm = VersionManager()

    assert vm.is_version_after("0.95.0", "0.90.0") == True
    assert vm.is_version_after("0.90.0", "0.95.0") == False
    assert vm.is_version_after("0.95.0", "0.95.0") == False
    assert vm.is_version_after("1.0.0", "0.99.0") == True


def test_is_version_same_or_after():
    """Test version same-or-after comparison."""
    vm = VersionManager()

    # Same version
    assert vm.is_version_same_or_after("0.95.0", "0.95.0") == True

    # Newer version
    assert vm.is_version_same_or_after("0.96.0", "0.95.0") == True
    assert vm.is_version_same_or_after("1.0.0", "0.99.0") == True

    # Older version
    assert vm.is_version_same_or_after("0.94.0", "0.95.0") == False
    assert vm.is_version_same_or_after("0.99.0", "1.0.0") == False

    # With v prefix
    assert vm.is_version_same_or_after("v0.95.0", "0.95.0") == True
    assert vm.is_version_same_or_after("0.95.0", "v0.95.0") == True


def test_update_version_comment():
    """Test version comment updating."""
    vm = VersionManager()

    # Test adding new comment after shebang
    lines = [
        "#!/usr/bin/env nu\n",
        "\n",
        "echo 'hello'\n"
    ]
    result = vm.update_version_comment(lines, "0.95.0")
    assert "# nushell-compatible-with: 0.95.0\n" in result

    # Test replacing existing comment
    lines = [
        "#!/usr/bin/env nu\n",
        "# nushell-compatible-with: 0.90.0\n",
        "echo 'hello'\n"
    ]
    result = vm.update_version_comment(lines, "0.95.0")
    assert "# nushell-compatible-with: 0.95.0\n" in result
    assert "# nushell-compatible-with: 0.90.0\n" not in result