import json
from unittest.mock import Mock, patch

import pytest

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.audit_service import AuditService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return Mock(spec=ZoteroGateway)


@pytest.fixture
def audit_service(mock_gateway):
    return AuditService(mock_gateway)


def test_get_citations_recursive(audit_service, tmp_path):
    main_tex = tmp_path / "main.tex"
    sub_tex = tmp_path / "sub.tex"
    nested_tex = tmp_path / "nested.tex"

    main_tex.write_text("\\cite{KEY1, KEY2}\n\\input{sub}\n% \\cite{COMMENTED}")
    sub_tex.write_text("\\cite{KEY3}\n\\include{nested}")
    nested_tex.write_text("\\cite{KEY4}")

    citations = audit_service._get_citations_recursive(main_tex)

    assert citations == {"KEY1", "KEY2", "KEY3", "KEY4"}


def test_audit_manuscript(audit_service, mock_gateway, tmp_path):
    main_tex = tmp_path / "main.tex"
    main_tex.write_text("\\cite{KEY1, KEY2, KEY3}")

    item1 = ZoteroItem.from_raw_zotero_item({
        "key": "KEY1",
        "data": {"title": "Paper 1"}
    })
    # item2 will be missing
    item3 = ZoteroItem.from_raw_zotero_item({
        "key": "KEY3",
        "data": {"title": "Paper 3"}
    })

    def get_item_mock(key):
        if key == "KEY1":
            return item1
        if key == "KEY3":
            return item3
        return None

    mock_gateway.get_item.side_effect = get_item_mock

    # Mock children for SDB note check
    mock_gateway.get_item_children.side_effect = lambda k: [
        {
            "data": {
                "itemType": "note",
                "note": '{"audit_version": "1.2", "persona": "Orion", "phase": "title_abstract", "decision": "accepted"}'
            }
        }
    ] if k == "KEY1" else []

    with patch("zotero_cli.core.utils.sdb_parser.parse_sdb_note") as mock_parse:
        mock_parse.side_effect = lambda n: json.loads(n) if "audit_version" in n else None

        report = audit_service.audit_manuscript(main_tex)

    assert report["total_citations"] == 3
    assert report["items"]["KEY1"]["exists"] is True
    assert report["items"]["KEY1"]["screened"] is True
    assert report["items"]["KEY1"]["decision"] == "accepted"

    assert report["items"]["KEY2"]["exists"] is False

    assert report["items"]["KEY3"]["exists"] is True
    assert report["items"]["KEY3"]["screened"] is False
