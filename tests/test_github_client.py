import pytest
from unittest.mock import patch, MagicMock
from nushell_verifier.github_client import GitHubClient


def test_github_client_with_provided_token():
    """Test GitHubClient with explicitly provided token."""
    client = GitHubClient("explicit_token")
    assert client.github_token == "explicit_token"


@patch('subprocess.run')
def test_github_client_with_gh_cli_token(mock_run):
    """Test GitHubClient auto-detecting GitHub CLI token."""
    # Mock successful gh CLI call
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "gh_cli_token_123\n"
    mock_run.return_value = mock_result

    client = GitHubClient()
    assert client.github_token == "gh_cli_token_123"

    # Verify the command was called correctly
    mock_run.assert_called_once_with(
        ["gh", "auth", "token"],
        capture_output=True,
        text=True,
        timeout=5
    )


@patch('subprocess.run')
def test_github_client_no_gh_cli(mock_run):
    """Test GitHubClient when GitHub CLI is not available."""
    # Mock gh CLI not found
    mock_run.side_effect = FileNotFoundError()

    client = GitHubClient()
    assert client.github_token is None


@patch('subprocess.run')
def test_github_client_gh_cli_not_authenticated(mock_run):
    """Test GitHubClient when GitHub CLI is not authenticated."""
    # Mock gh CLI returning non-zero exit code
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_run.return_value = mock_result

    client = GitHubClient()
    assert client.github_token is None


@patch('subprocess.run')
def test_github_client_gh_cli_timeout(mock_run):
    """Test GitHubClient handling timeout from GitHub CLI."""
    # Mock timeout
    mock_run.side_effect = subprocess.TimeoutExpired("gh", 5)

    client = GitHubClient()
    assert client.github_token is None


def test_github_client_explicit_token_takes_precedence():
    """Test that explicit token takes precedence over GitHub CLI."""
    with patch('subprocess.run') as mock_run:
        # Mock successful gh CLI call
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "gh_cli_token_123\n"
        mock_run.return_value = mock_result

        client = GitHubClient("explicit_token")
        assert client.github_token == "explicit_token"

        # GitHub CLI should not be called when explicit token is provided
        mock_run.assert_not_called()


# Import here to avoid circular imports at module level
import subprocess