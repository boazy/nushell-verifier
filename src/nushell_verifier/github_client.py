import re
import subprocess
import httpx
from typing import List, Optional
from .models import ReleaseInfo


class GitHubClient:
    """Client for fetching NuShell releases and blog posts from GitHub."""

    def __init__(self, github_token: Optional[str] = None):
        """Initialize GitHub client with optional token for higher rate limits."""
        self.github_token = github_token or self._get_gh_cli_token()
        self.base_url = "https://api.github.com"
        self.blog_repo = "nushell/nushell.github.io"
        self.nushell_repo = "nushell/nushell"

    def _get_gh_cli_token(self) -> Optional[str]:
        """Try to get GitHub token from GitHub CLI if available."""
        try:
            # Check if gh CLI is available
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                token = result.stdout.strip()
                if token:
                    return token
        except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
            # gh CLI not available or not authenticated
            pass

        return None

    def get_latest_version(self) -> str:
        """Get the latest NuShell version from GitHub releases."""
        releases = self._get_releases(limit=1)
        if not releases:
            raise RuntimeError("Could not fetch latest NuShell version")
        return releases[0].version

    def get_releases_between(self, start_version: str, end_version: str) -> List[ReleaseInfo]:
        """Get all non-patch releases between two versions."""
        all_releases = self._get_releases()

        # Filter releases between versions (excluding patch releases)
        filtered_releases = []
        for release in all_releases:
            if self._is_version_between(release.version, start_version, end_version):
                if not self._is_patch_release(release.version):
                    filtered_releases.append(release)

        return filtered_releases

    def fetch_blog_post_content(self, release: ReleaseInfo) -> Optional[str]:
        """Fetch blog post content for a release."""
        if not release.blog_post_url:
            return None

        # Extract blog post path from URL
        blog_path = self._extract_blog_path(release.blog_post_url)
        if not blog_path:
            return None

        return self._fetch_file_content(self.blog_repo, blog_path)

    def _get_releases(self, limit: Optional[int] = None) -> List[ReleaseInfo]:
        """Fetch releases from GitHub API."""
        headers = {}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"

        params = {"per_page": limit or 100}

        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/repos/{self.nushell_repo}/releases",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()

                releases = []
                for release_data in response.json():
                    if release_data.get("draft") or release_data.get("prerelease"):
                        continue

                    version = release_data["tag_name"]
                    blog_url = self._extract_blog_url(release_data.get("body", ""))

                    releases.append(ReleaseInfo(
                        version=version,
                        blog_post_url=blog_url
                    ))

                return releases

        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to fetch releases: {e}")

    def _extract_blog_url(self, release_body: str) -> Optional[str]:
        """Extract blog post URL from release body."""
        # Look for blog post links in release notes
        blog_pattern = re.compile(r"https://www\.nushell\.sh/blog/[\w\-/]+\.html")
        match = blog_pattern.search(release_body)
        return match.group(0) if match else None

    def _extract_blog_path(self, blog_url: str) -> Optional[str]:
        """Extract file path from blog URL."""
        if not blog_url:
            return None

        # Convert URL to file path in the blog repository
        # https://www.nushell.sh/blog/2023-10-10-nushell_0_85_0.html
        # -> blog/2023-10-10-nushell_0_85_0.md
        pattern = re.compile(r"https://www\.nushell\.sh/blog/(.+)\.html")
        match = pattern.search(blog_url)
        if match:
            return f"blog/{match.group(1)}.md"
        return None

    def _fetch_file_content(self, repo: str, file_path: str) -> Optional[str]:
        """Fetch file content from GitHub repository."""
        headers = {}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"

        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/repos/{repo}/contents/{file_path}",
                    headers=headers
                )
                response.raise_for_status()

                content_data = response.json()
                if content_data.get("encoding") == "base64":
                    import base64
                    return base64.b64decode(content_data["content"]).decode("utf-8")

        except httpx.HTTPError:
            pass  # File might not exist

        return None

    def _is_version_between(self, version: str, start: str, end: str) -> bool:
        """Check if version is between start and end versions."""
        def version_tuple(v: str) -> tuple:
            return tuple(map(int, v.lstrip("v").split(".")))

        try:
            v_tuple = version_tuple(version)
            start_tuple = version_tuple(start)
            end_tuple = version_tuple(end)
            return start_tuple <= v_tuple <= end_tuple
        except ValueError:
            return False

    def _is_patch_release(self, version: str) -> bool:
        """Check if version is a patch release (x.y.z where z > 0)."""
        try:
            parts = version.lstrip("v").split(".")
            return len(parts) >= 3 and int(parts[2]) > 0
        except (ValueError, IndexError):
            return False