import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

@dataclass(frozen=True)
class ZoteroConfig:
    api_key: Optional[str] = None
    library_id: Optional[str] = None
    library_type: str = "group"
    target_group_url: Optional[str] = None
    user_id: Optional[str] = None
    semantic_scholar_api_key: Optional[str] = None
    unpaywall_email: Optional[str] = None

    def is_valid(self) -> bool:
        return bool(self.api_key and self.library_id)

class ConfigLoader:
    """
    Responsible for loading configuration with the following precedence:
    1. Environment Variables (Highest)
    2. config.toml
    3. Default values (Lowest)

    CLI flags are handled at the CLI layer and override this.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self._get_default_config_path()

    def _get_default_config_path(self) -> Path:
        if os.name == 'nt':
            base = Path(os.environ.get('APPDATA', '~')).expanduser()
        else:
            base = Path(os.environ.get('XDG_CONFIG_HOME', '~/.config')).expanduser()
        return base / "zotero-cli" / "config.toml"

    def load(self) -> ZoteroConfig:
        file_config = self._load_from_file()

        # Merge logic: Env > File
        api_key = os.environ.get("ZOTERO_API_KEY") or file_config.get("api_key")
        user_id = os.environ.get("ZOTERO_USER_ID") or file_config.get("user_id")
        group_url = os.environ.get("ZOTERO_TARGET_GROUP") or file_config.get("target_group")

        # Derive library_id/type from group_url or user_id
        library_id = os.environ.get("ZOTERO_LIBRARY_ID") or file_config.get("library_id")
        library_type = os.environ.get("ZOTERO_LIBRARY_TYPE") or file_config.get("library_type", "group")

        # Extra keys
        ss_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or file_config.get("semantic_scholar_api_key")
        up_email = os.environ.get("UNPAYWALL_EMAIL") or file_config.get("unpaywall_email")

        return ZoteroConfig(
            api_key=api_key,
            library_id=library_id,
            library_type=library_type,
            target_group_url=group_url,
            user_id=user_id,
            semantic_scholar_api_key=ss_key,
            unpaywall_email=up_email
        )

    def _load_from_file(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {}

        try:
            with open(self.config_path, "rb") as f:
                data = tomllib.load(f)
                # Expecting a [zotero] section
                return data.get("zotero", {})
        except Exception as e:
            print(f"Warning: Failed to load config file {self.config_path}: {e}")
            return {}

# --- Global Config State ---

_GLOBAL_CONFIG: Optional[ZoteroConfig] = None
_GLOBAL_CONFIG_PATH: Optional[Path] = None

def reset_config():
    """Reset global config cache (mainly for testing)."""
    global _GLOBAL_CONFIG, _GLOBAL_CONFIG_PATH
    _GLOBAL_CONFIG = None
    _GLOBAL_CONFIG_PATH = None

def get_config(config_path: Optional[str] = None) -> ZoteroConfig:
    """Helper to get singleton configuration."""
    global _GLOBAL_CONFIG, _GLOBAL_CONFIG_PATH
    if _GLOBAL_CONFIG is None or config_path:
        path = Path(config_path) if config_path else None
        loader = ConfigLoader(config_path=path)
        _GLOBAL_CONFIG = loader.load()
        _GLOBAL_CONFIG_PATH = loader.config_path
    return _GLOBAL_CONFIG

def get_config_path() -> Optional[Path]:
    return _GLOBAL_CONFIG_PATH
