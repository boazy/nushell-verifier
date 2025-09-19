from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, List


class CompatibilityMethod(Enum):
    COMMENT_HEADER = "comment_header"
    DIRECTORY_FILE = "directory_file"
    DEFAULT_ASSUMPTION = "default_assumption"


@dataclass
class ScriptFile:
    path: Path
    compatible_version: str
    method: CompatibilityMethod
    has_shebang: bool = False


@dataclass
class CompatibilityIssue:
    description: str
    suggested_fix: Optional[str] = None
    severity: str = "warning"


@dataclass
class ScriptAnalysis:
    script: ScriptFile
    target_version: str
    issues: List[CompatibilityIssue]
    is_compatible: bool


@dataclass
class ReleaseInfo:
    version: str
    blog_post_url: Optional[str]
    blog_post_content: Optional[str] = None
    compatibility_instructions: Optional[str] = None


@dataclass
class Config:
    llm_provider: str = "openai"
    llm_model: str = "gpt-4"
    api_key: Optional[str] = None
    github_token: Optional[str] = None
    scan_directories: List[str] = None
    temperature: Optional[float] = None
    llm_params: Optional[dict] = None
    cache_enabled: bool = True

    def __post_init__(self):
        if self.scan_directories is None:
            self.scan_directories = ["~/dots/bin", "~/dots/config/nushell"]
        if self.llm_params is None:
            self.llm_params = {}