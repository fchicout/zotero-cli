import pytest

from zotero_cli.core.config import ZoteroConfig


@pytest.fixture
def mock_config() -> ZoteroConfig:
    """
    A minimal, valid ZoteroConfig for tests that just need *a* config to
    pass to a factory/service under test - not for tests exercising
    ZoteroConfig's own field-resolution logic itself (see
    test_config.py), which needs specific, deliberately-varied field
    combinations per case and shouldn't be forced through a shared
    default (Issue #254).

    ZoteroConfig is a frozen dataclass - override specific fields with
    `dataclasses.replace(mock_config, field=value)` rather than
    reconstructing one from scratch.
    """
    return ZoteroConfig(
        api_key="test_key",
        library_id="123",
        library_type="user",
        database_path="test.sqlite",
    )
