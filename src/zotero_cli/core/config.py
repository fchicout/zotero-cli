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
    ncbi_api_key: Optional[str] = None
    storage_path: Optional[str] = None
    database_path: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    embedding_provider: str = "auto"
    embedding_model: Optional[str] = None
    generative_provider: str = "auto"
    generative_model: Optional[str] = None
    huggingface_token: Optional[str] = None
    tts_lang: Optional[str] = None
    tts_voice: Optional[str] = None

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
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", "~")).expanduser()
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
        return base / "zotero-cli" / "config.toml"

    def load(self) -> ZoteroConfig:
        file_config = self._load_from_file()

        # Merge logic: Env > File
        api_key = os.environ.get("ZOTERO_API_KEY") or file_config.get("api_key")
        user_id = os.environ.get("ZOTERO_USER_ID") or file_config.get("user_id")
        group_url = os.environ.get("ZOTERO_TARGET_GROUP") or file_config.get("target_group")

        # Derive library_id/type from group_url or user_id
        library_id = os.environ.get("ZOTERO_LIBRARY_ID") or file_config.get("library_id")
        library_type = os.environ.get("ZOTERO_LIBRARY_TYPE") or file_config.get(
            "library_type", "group"
        )

        # Extra keys
        ss_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or file_config.get(
            "semantic_scholar_api_key"
        )
        ncbi_key = os.environ.get("NCBI_API_KEY") or file_config.get("ncbi_api_key")
        up_email = os.environ.get("UNPAYWALL_EMAIL") or file_config.get("unpaywall_email")
        openai_key = os.environ.get("OPENAI_API_KEY") or file_config.get("openai_api_key")
        gemini_key = os.environ.get("GEMINI_API_KEY") or file_config.get("gemini_api_key")
        emb_provider = os.environ.get("EMBEDDING_PROVIDER") or file_config.get(
            "embedding_provider", "auto"
        )
        emb_model = os.environ.get("EMBEDDING_MODEL") or file_config.get("embedding_model")
        gen_provider = os.environ.get("GENERATIVE_PROVIDER") or file_config.get(
            "generative_provider", "auto"
        )
        gen_model = os.environ.get("GENERATIVE_MODEL") or file_config.get("generative_model")
        hf_token = os.environ.get("HUGGINGFACE_TOKEN") or file_config.get("huggingface_token")
        tts_lang = os.environ.get("TTS_LANG") or file_config.get("tts_lang")
        tts_voice = os.environ.get("TTS_VOICE") or file_config.get("tts_voice")

        storage_path = os.environ.get("ZOTERO_STORAGE_PATH") or file_config.get("storage_path")
        database_path = os.environ.get("ZOTERO_DATABASE_PATH") or file_config.get("database_path")

        return ZoteroConfig(
            api_key=api_key,
            library_id=library_id,
            library_type=library_type,
            target_group_url=group_url,
            user_id=user_id,
            semantic_scholar_api_key=ss_key,
            unpaywall_email=up_email,
            ncbi_api_key=ncbi_key,
            storage_path=storage_path,
            database_path=database_path,
            openai_api_key=openai_key,
            gemini_api_key=gemini_key,
            embedding_provider=emb_provider,
            embedding_model=emb_model,
            generative_provider=gen_provider,
            generative_model=gen_model,
            huggingface_token=hf_token,
            tts_lang=tts_lang,
            tts_voice=tts_voice,
        )

    def _load_from_file(self) -> Dict[str, Any]:
        from typing import cast

        if not self.config_path.exists():
            return {}

        try:
            with open(self.config_path, "rb") as f:
                data = tomllib.load(f)
                # Expecting a [zotero] section
                return cast(Dict[str, Any], data.get("zotero", {}))
        except Exception as e:
            print(f"Warning: Failed to load config file {self.config_path}: {e}")
            return {}


class ConfigManager:
    """
    Handles writing updates to the configuration file.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or ConfigLoader().config_path

    def save_group_context(self, group_id: str):
        """
        Updates the library_id and library_type in the config file to point to a group.
        Preserves other keys.
        """
        self.update_config({"library_id": group_id, "library_type": "group"})

    def update_config(self, updates: Dict[str, Any]):
        """
        Updates the config file with the provided key-value pairs.
        Preserves other keys.
        """
        try:
            import toml
        except ImportError:
            raise RuntimeError("The 'toml' library is required for writing configuration.")

        if not self.config_path.exists():
            # Create a basic structure if it doesn't exist
            data: Dict[str, Any] = {"zotero": {}}
        else:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = toml.load(f)
            except Exception as e:
                # If file exists but is invalid, we might overwrite or error.
                # Better to error to avoid data loss.
                raise RuntimeError(f"Failed to load existing config file: {e}")

        if "zotero" not in data:
            data["zotero"] = {}

        for key, value in updates.items():
            data["zotero"][key] = value

        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            toml.dump(data, f)

        # Invalidate global cache
        reset_config()


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


def get_storage_dir() -> Path:
    """Returns the directory where data (config, db) is stored."""
    path = get_config_path()
    if path:
        return path.parent

    # Fallback to default
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", "~")).expanduser()
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    return base / "zotero-cli"
