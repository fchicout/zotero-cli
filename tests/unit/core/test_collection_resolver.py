"""Issue #381: a collection name that matches several collections must not
silently resolve to the first one."""

import sys
from unittest.mock import patch

import pytest

from zotero_cli.core.exceptions import AmbiguousCollectionError
from zotero_cli.core.utils.collection_resolver import resolve_collection_key

COLLECTIONS = [
    {"key": "SRC1", "data": {"name": "Source A", "parentCollection": False}},
    {"key": "SRC2", "data": {"name": "Source B", "parentCollection": False}},
    {"key": "FT1", "data": {"name": "2-full_text", "parentCollection": "SRC1"}},
    {"key": "FT2", "data": {"name": "2-full_text", "parentCollection": "SRC2"}},
    {"key": "INC", "data": {"name": "Included", "parentCollection": False}},
]


def test_key_resolves_to_itself():
    assert resolve_collection_key(COLLECTIONS, "FT2") == "FT2"


def test_unique_name_and_case_insensitive_name():
    assert resolve_collection_key(COLLECTIONS, "Included") == "INC"
    assert resolve_collection_key(COLLECTIONS, "included") == "INC"


def test_unknown_name_is_none():
    assert resolve_collection_key(COLLECTIONS, "Nope") is None
    assert resolve_collection_key(COLLECTIONS, "") is None


def test_ambiguous_name_raises_with_every_candidate_and_its_path():
    with pytest.raises(AmbiguousCollectionError) as exc:
        resolve_collection_key(COLLECTIONS, "2-full_text")
    assert exc.value.candidates == [
        ("FT1", "Source A / 2-full_text"),
        ("FT2", "Source B / 2-full_text"),
    ]
    assert "FT1" in str(exc.value) and "FT2" in str(exc.value)


def test_exact_name_wins_over_case_insensitive_duplicates():
    cols = COLLECTIONS + [{"key": "INC2", "data": {"name": "INCLUDED", "parentCollection": False}}]
    assert resolve_collection_key(cols, "Included") == "INC"
    with pytest.raises(AmbiguousCollectionError):
        resolve_collection_key(cols, "included")


def test_both_gateways_use_the_resolver():
    from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway
    from zotero_cli.infra.zotero_api import ZoteroAPIClient

    for gateway_cls in (ZoteroAPIClient, SqliteZoteroGateway):
        gateway = gateway_cls.__new__(gateway_cls)
        with patch.object(gateway_cls, "get_all_collections", return_value=COLLECTIONS):
            with pytest.raises(AmbiguousCollectionError):
                gateway.get_collection_id_by_name("2-full_text")
            assert gateway.get_collection_id_by_name("FT1") == "FT1"


def test_cli_reports_ambiguity_with_exit_2_and_no_traceback(capsys):
    from zotero_cli.cli.main import main

    error = AmbiguousCollectionError("2-full_text", [("FT1", "Source A / 2-full_text")])
    argv = ["zotero-cli", "collection", "clean", "--collection", "2-full_text"]
    with (
        patch.object(sys, "argv", argv),
        patch("zotero_cli.cli.main.get_config"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_zotero_gateway"),
        patch("zotero_cli.infra.factory.GatewayFactory.get_collection_service") as factory,
    ):
        factory.return_value.plan_clean.side_effect = error
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "FT1" in err and "Traceback" not in err
