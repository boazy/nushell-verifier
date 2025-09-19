"""
Unit tests for blog path extraction to prevent regression.
"""
from nushell_verifier.github_client import GitHubClient


def test_blog_path_extraction():
    """Test that blog path extraction works correctly."""
    client = GitHubClient()

    # Test cases based on real URLs
    test_cases = [
        (
            "https://www.nushell.sh/blog/2025-09-02-nushell_0_107_0.html",
            "blog/2025-09-02-nushell_0_107_0.md"
        ),
        (
            "https://www.nushell.sh/blog/2025-07-23-nushell_0_106_0.html",
            "blog/2025-07-23-nushell_0_106_0.md"
        ),
        (
            "https://www.nushell.sh/blog/2023-10-10-nushell_0_85_0.html",
            "blog/2023-10-10-nushell_0_85_0.md"
        )
    ]

    for blog_url, expected_path in test_cases:
        result = client._extract_blog_path(blog_url)
        assert result == expected_path, f"URL {blog_url} should map to {expected_path}, got {result}"


def test_blog_path_extraction_invalid_urls():
    """Test blog path extraction with invalid URLs."""
    client = GitHubClient()

    invalid_urls = [
        "https://example.com/blog/invalid.html",
        "https://www.nushell.sh/docs/something.html",
        "not-a-url",
        None,
        ""
    ]

    for invalid_url in invalid_urls:
        result = client._extract_blog_path(invalid_url)
        assert result is None, f"Invalid URL {invalid_url} should return None, got {result}"


def test_blog_url_pattern_in_release_body():
    """Test that the blog URL pattern correctly matches release bodies."""
    client = GitHubClient()

    # Example release body content
    release_body = """
    This release brings several exciting features...

    For more details, see the [full blog post](https://www.nushell.sh/blog/2025-09-02-nushell_0_107_0.html).

    Thanks to all contributors!
    """

    extracted_url = client._extract_blog_url(release_body)
    assert extracted_url == "https://www.nushell.sh/blog/2025-09-02-nushell_0_107_0.html"


def test_blog_url_pattern_no_match():
    """Test blog URL extraction when no URL is present."""
    client = GitHubClient()

    release_body = """
    This release brings several features but has no blog post link.
    """

    extracted_url = client._extract_blog_url(release_body)
    assert extracted_url is None