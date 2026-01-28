import os
import toml
from unittest.mock import patch, mock_open
from pathlib import Path
from zotero_cli.core.config import ConfigManager, ConfigLoader

def test_config_manager_save_group_context(tmp_path):
    config_file = tmp_path / "config.toml"
    
    # Create initial config
    initial_data = {
        "zotero": {
            "api_key": "secret",
            "library_id": "old_lib",
            "library_type": "user",
            "user_id": "123"
        }
    }
    with open(config_file, "w") as f:
        toml.dump(initial_data, f)
        
    with patch("zotero_cli.core.config.ConfigLoader") as MockLoader:
        MockLoader.return_value.config_path = config_file
        
        manager = ConfigManager(config_path=config_file)
        manager.save_group_context("999")
        
        with open(config_file, "r") as f:
            new_data = toml.load(f)
            
        assert new_data["zotero"]["library_id"] == "999"
        assert new_data["zotero"]["library_type"] == "group"
        assert new_data["zotero"]["api_key"] == "secret" # Preserved

def test_config_manager_file_not_found():
    manager = ConfigManager(config_path=Path("/non/existent/path.toml"))
    try:
        manager.save_group_context("123")
        assert False, "Should raise FileNotFoundError"
    except FileNotFoundError:
        pass
    except Exception as e:
        assert False, f"Raised wrong exception: {e}"
