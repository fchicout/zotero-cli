from unittest.mock import patch

import pytest

from zotero_cli.core.config import ZoteroConfig
from zotero_cli.infra.resolver_factory import ResolverFactory


@pytest.fixture
def storage_dir(tmp_path):
    with patch("zotero_cli.infra.resolver_factory.get_storage_dir", return_value=tmp_path):
        yield tmp_path


def test_get_snowball_graph_service_no_config_uses_legacy_global_path(storage_dir):
    """Issue #228: config=None keeps the pre-#228 global-singleton path,
    for backward compatibility with any caller with no library context."""
    service = ResolverFactory.get_snowball_graph_service()
    assert service.storage_path == storage_dir / "discovery_graph.json"


def test_get_snowball_graph_service_scopes_by_library_id(storage_dir):
    """Issue #228: two configs with different library_ids must resolve to
    two separate storage files, not the shared global one."""
    config_a = ZoteroConfig(api_key="k", library_id="AAA", library_type="group")
    config_b = ZoteroConfig(api_key="k", library_id="BBB", library_type="group")

    service_a = ResolverFactory.get_snowball_graph_service(config_a)
    service_b = ResolverFactory.get_snowball_graph_service(config_b)

    assert service_a.storage_path == storage_dir / "discovery_graph_AAA.json"
    assert service_b.storage_path == storage_dir / "discovery_graph_BBB.json"
    assert service_a.storage_path != service_b.storage_path


def test_get_snowball_graph_service_falls_back_to_user_id(storage_dir):
    config = ZoteroConfig(api_key="k", library_id=None, library_type="user", user_id="U1")
    service = ResolverFactory.get_snowball_graph_service(config)
    assert service.storage_path == storage_dir / "discovery_graph_U1.json"


def test_get_snowball_graph_service_migrates_legacy_file_once(storage_dir):
    """Issue #228: the first library scoped after upgrading inherits any
    pre-#228 unscoped graph rather than appearing to have silently lost
    it - copied into its own scoped file, not left pointing at the shared
    legacy path, so a second library correctly gets a fresh file too."""
    legacy_path = storage_dir / "discovery_graph.json"
    legacy_content = (
        '{"directed": true, "multigraph": false, "graph": {}, '
        '"nodes": [{"id": "10.1/seed"}], "edges": []}'
    )
    legacy_path.write_text(legacy_content)

    config_a = ZoteroConfig(api_key="k", library_id="AAA", library_type="group")
    service_a = ResolverFactory.get_snowball_graph_service(config_a)
    scoped_path_a = storage_dir / "discovery_graph_AAA.json"
    assert service_a.storage_path == scoped_path_a
    assert "10.1/seed" in service_a.graph

    config_b = ZoteroConfig(api_key="k", library_id="BBB", library_type="group")
    service_b = ResolverFactory.get_snowball_graph_service(config_b)
    assert service_b.storage_path == storage_dir / "discovery_graph_BBB.json"
    assert service_b.storage_path != legacy_path
    assert "10.1/seed" not in service_b.graph
