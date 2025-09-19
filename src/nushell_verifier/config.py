import os
import toml
from pathlib import Path
from typing import Optional
from .models import Config


def get_config_path() -> Path:
    """Get XDG-compliant configuration directory."""
    config_dir = os.getenv("XDG_CONFIG_HOME")
    if config_dir:
        return Path(config_dir) / "nushell-verifier"
    else:
        return Path.home() / ".config" / "nushell-verifier"


def get_cache_path() -> Path:
    """Get XDG-compliant cache directory."""
    cache_dir = os.getenv("XDG_CACHE_HOME")
    if cache_dir:
        return Path(cache_dir) / "nushell-verifier"
    else:
        return Path.home() / ".cache" / "nushell-verifier"


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load configuration from TOML file."""
    if config_path is None:
        config_path = get_config_path() / "config.toml"

    if not config_path.exists():
        return Config()

    try:
        with open(config_path, "r") as f:
            config_data = toml.load(f)

        return Config(
            llm_provider=config_data.get("llm_provider", "openai"),
            llm_model=config_data.get("llm_model", "gpt-4"),
            api_key=config_data.get("api_key"),
            github_token=config_data.get("github_token"),
            scan_directories=config_data.get("scan_directories", ["~/dots/bin", "~/dots/config/nushell"]),
            temperature=config_data.get("temperature"),
            llm_params=config_data.get("llm_params", {}),
            cache_enabled=config_data.get("cache_enabled", True)
        )
    except Exception as e:
        raise RuntimeError(f"Failed to load config from {config_path}: {e}")


def create_default_config() -> None:
    """Create a default configuration file."""
    config_dir = get_config_path()
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = config_dir / "config.toml"
    if config_path.exists():
        return

    default_config = {
        "llm_provider": "openai",
        "llm_model": "gpt-4",
        "api_key": "",
        "github_token": "",
        "scan_directories": ["~/dots/bin", "~/dots/config/nushell"],
        "temperature": 0.1,
        "llm_params": {}
    }

    with open(config_path, "w") as f:
        toml.dump(default_config, f)

    print(f"Created default configuration at {config_path}")
    print("Please edit the configuration file to add your API keys.")