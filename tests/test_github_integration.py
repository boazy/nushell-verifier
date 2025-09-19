"""
Integration tests for GitHub client - these make real API calls.
Run with: pytest tests/test_github_integration.py -s -v
"""
import pytest
from nushell_verifier.github_client import GitHubClient


class TestGitHubIntegration:
    """Integration tests that make real GitHub API calls."""

    def setup_method(self):
        """Set up client for each test."""
        self.client = GitHubClient()  # Will auto-detect GitHub CLI token if available

    def test_get_latest_version_real(self):
        """Test fetching the actual latest NuShell version."""
        version = self.client.get_latest_version()

        print(f"Latest version: {version}")
        assert version.startswith(("0.", "1."))  # Should be a version like 0.107.0
        assert "." in version

    def test_get_releases_real(self):
        """Test fetching real releases."""
        releases = self.client._get_releases(limit=5)

        print(f"Found {len(releases)} releases:")
        for release in releases[:3]:
            print(f"  - {release.version}: {release.blog_post_url}")

        assert len(releases) > 0
        assert all(r.version for r in releases)

    def test_release_blog_url_extraction(self):
        """Test blog URL extraction from real release bodies."""
        releases = self.client._get_releases(limit=10)

        releases_with_blogs = [r for r in releases if r.blog_post_url]
        releases_without_blogs = [r for r in releases if not r.blog_post_url]

        print(f"Releases with blog URLs: {len(releases_with_blogs)}")
        print(f"Releases without blog URLs: {len(releases_without_blogs)}")

        if releases_with_blogs:
            print("Sample blog URLs:")
            for release in releases_with_blogs[:3]:
                print(f"  - {release.version}: {release.blog_post_url}")

        if releases_without_blogs:
            print("Releases missing blog URLs:")
            for release in releases_without_blogs[:5]:
                print(f"  - {release.version}")

    def test_blog_post_fetching_real(self):
        """Test fetching actual blog posts."""
        releases = self.client._get_releases(limit=10)

        # Find a release with a blog URL
        test_release = None
        for release in releases:
            if release.blog_post_url:
                test_release = release
                break

        if not test_release:
            pytest.skip("No releases with blog URLs found")

        print(f"Testing blog post fetch for {test_release.version}")
        print(f"Blog URL: {test_release.blog_post_url}")

        # Test the blog path extraction
        blog_path = self.client._extract_blog_path(test_release.blog_post_url)
        print(f"Extracted blog path: {blog_path}")

        # Test fetching the actual content
        content = self.client.fetch_blog_post_content(test_release)

        if content:
            print(f"Blog post content length: {len(content)}")
            print(f"First 200 chars: {content[:200]}...")
            assert len(content) > 100  # Should have substantial content
        else:
            print("❌ Failed to fetch blog post content")
            # Let's debug why it failed
            if blog_path:
                print(f"Trying to fetch directly: {blog_path}")
                direct_content = self.client._fetch_file_content(self.client.blog_repo, blog_path)
                print(f"Direct fetch result: {direct_content is not None}")

    def test_version_range_releases(self):
        """Test fetching releases in a specific version range."""
        start_version = "0.105.0"
        end_version = "0.107.0"

        releases = self.client.get_releases_between(start_version, end_version)

        print(f"Releases between {start_version} and {end_version}:")
        for release in releases:
            print(f"  - {release.version}: blog_url={release.blog_post_url is not None}")

        assert len(releases) > 0

        # Test if we can fetch blog posts for any of these
        successful_fetches = 0
        for release in releases:
            content = self.client.fetch_blog_post_content(release)
            if content:
                successful_fetches += 1
                print(f"✅ Successfully fetched blog for {release.version}")
            else:
                print(f"❌ Failed to fetch blog for {release.version}")

        print(f"Successfully fetched {successful_fetches}/{len(releases)} blog posts")

    def test_debug_specific_release(self):
        """Debug a specific recent release to understand the issue."""
        # Let's debug 0.106.0 specifically
        releases = self.client._get_releases()
        target_release = None

        for release in releases:
            if release.version == "0.106.0":
                target_release = release
                break

        if not target_release:
            pytest.skip("Release 0.106.0 not found")

        print(f"Debugging release {target_release.version}")
        print(f"Blog URL: {target_release.blog_post_url}")

        if target_release.blog_post_url:
            # Test URL pattern
            import re
            pattern = re.compile(r"https://www\.nushell\.sh/blog/(.+)\.html")
            match = pattern.search(target_release.blog_post_url)
            if match:
                print(f"URL pattern matches: {match.group(1)}")
                blog_path = f"blog/_posts/{match.group(1)}.md"
                print(f"Expected blog path: {blog_path}")

                # Try to fetch it
                content = self.client._fetch_file_content(self.client.blog_repo, blog_path)
                print(f"Fetch result: {content is not None}")
                if content:
                    print(f"Content length: {len(content)}")
                else:
                    # Try different paths
                    alt_paths = [
                        f"blog/{match.group(1)}.md",
                        f"_posts/{match.group(1)}.md",
                        f"{match.group(1)}.md"
                    ]
                    for alt_path in alt_paths:
                        print(f"Trying alternative path: {alt_path}")
                        alt_content = self.client._fetch_file_content(self.client.blog_repo, alt_path)
                        if alt_content:
                            print(f"✅ Found content at: {alt_path}")
                            break
                    else:
                        print("❌ No alternative paths worked")