import sys
from unittest.mock import Mock, patch

import pytest

from zotero_cli.cli.main import main


@pytest.fixture
def mock_gateway():
    with patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway") as mock_get:
        yield mock_get.return_value


@pytest.fixture
def env_vars(monkeypatch):
    monkeypatch.setenv("ZOTERO_API_KEY", "test_key")
    monkeypatch.setenv("ZOTERO_USER_ID", "12345")
    monkeypatch.setenv("ZOTERO_TARGET_GROUP", "https://zotero.org/groups/123/name")


def test_list_items_sdb_filter_excluded(mock_gateway, env_vars, capsys):
    # Setup mock items
    item_inc = Mock()
    item_inc.key = "INC1"
    item_inc.title = "Included Paper"
    item_inc.tags = ["rsl:include"]

    item_exc = Mock()
    item_exc.key = "EXC1"
    item_exc.title = "Excluded Paper"
    item_exc.tags = ["rsl:exclude:EC1"]

    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    mock_gateway.get_items_in_collection.return_value = iter([item_inc, item_exc])

    # Mock SDB Service results
    from typing import Any, Dict

    with patch(
        "zotero_cli.core.services.sdb.sdb_service.SDBService.inspect_item_sdb"
    ) as mock_inspect:
        # For item_inc, it shouldn't even be called because of tag filtering if we implement it strictly,
        # but let's assume it might be or we want to be safe.
        def mock_inspect_impl(key: str) -> list[Dict[str, Any]]:
            if key == "INC1":
                return [{"decision": "accepted", "persona": "P1", "phase": "title_abstract"}]
            else:
                return [
                    {
                        "decision": "rejected",
                        "reason_code": ["EC1"],
                        "persona": "P2",
                        "phase": "title_abstract",
                    }
                ]

        mock_inspect.side_effect = mock_inspect_impl

        test_args = ["zotero-cli", "list", "items", "--collection", "MyCol", "--excluded"]
        with patch.object(sys, "argv", test_args):
            main()

    out = capsys.readouterr().out

    # Check headers
    assert "Decision" in out
    assert "Criteria" in out
    assert "Persona" in out

    # Check content
    assert "Excluded Paper" in out
    assert "rejected" in out
    assert "EC1" in out
    assert "P2" in out

    # Ensure included paper is NOT there
    assert "Included Paper" not in out


def test_list_items_sdb_filter_no_results(mock_gateway, env_vars, capsys):
    item_inc = Mock()
    item_inc.key = "INC1"
    item_inc.title = "Included Paper"
    item_inc.tags = ["rsl:include"]

    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    mock_gateway.get_items_in_collection.return_value = iter([item_inc])

    with patch(
        "zotero_cli.core.services.sdb.sdb_service.SDBService.inspect_item_sdb"
    ) as mock_inspect:
        mock_inspect.return_value = [{"decision": "accepted"}]

        test_args = ["zotero-cli", "list", "items", "--collection", "MyCol", "--excluded"]
        with patch.object(sys, "argv", test_args):
            main()

    out = capsys.readouterr().out
    assert "No items found matching criteria" in out


def test_list_items_missing_collection(mock_gateway, env_vars, capsys):
    test_args = ["zotero-cli", "list", "items"]
    with patch.object(sys, "argv", test_args):
        # We don't raise error, we print it
        main()
    out = capsys.readouterr().out
    assert "Error: --collection required" in out


def test_list_items_sdb_filter_criteria_and_persona(mock_gateway, env_vars, capsys):
    item = Mock()
    item.key = "K1"
    item.title = "Target Paper"
    item.tags = ["rsl:exclude:EC4"]

    mock_gateway.get_collection_id_by_name.return_value = "COL1"
    mock_gateway.get_items_in_collection.return_value = iter([item])

    with patch(
        "zotero_cli.core.services.sdb.sdb_service.SDBService.inspect_item_sdb"
    ) as mock_inspect:
        mock_inspect.return_value = [
            {
                "decision": "rejected",
                "reason_code": ["EC4"],
                "persona": "Dr. Silas",
                "phase": "title_abstract",
            }
        ]

        test_args = [
            "zotero-cli",
            "list",
            "items",
            "--collection",
            "MyCol",
            "--criteria",
            "EC4",
            "--persona",
            "Dr. Silas",
        ]
        with patch.object(sys, "argv", test_args):
            main()

    out = capsys.readouterr().out
    assert "Target Paper" in out
    assert "Dr. Silas" in out
    assert "EC4" in out


def test_list_groups(mock_gateway, env_vars, capsys):
    mock_gateway.get_user_groups.return_value = [{"id": 123, "data": {"name": "Group Alpha"}}]

    test_args = ["zotero-cli", "list", "groups"]
    with patch.object(sys, "argv", test_args):
        main()

    out = capsys.readouterr().out
    assert "Group Alpha" in out
    assert "123" in out
