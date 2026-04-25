from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.slr.citation_service import CitationService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.mark.unit
def test_citation_service_with_mock_item():
    """
    AUDIT-001: CitationService should be resilient to mocked ZoteroItems.
    Currently fails because it accesses item.raw_data['data'] directly.
    """
    service = CitationService()
    item = MagicMock(spec=ZoteroItem)
    item.extra = "Citation Key: Chicout2026"
    item.raw_data = {"data": {"extra": "Citation Key: Chicout2026"}}

    # This should not raise TypeError
    key = service.resolve_citation_key(item)
    assert key == "Chicout2026"

@pytest.mark.unit
def test_sqlite_gateway_interface_compliance():
    """
    AUDIT-002: SqliteZoteroGateway must implement all abstract methods of ZoteroGateway.
    Currently fails with TypeError on instantiation.
    """
    import os

    from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway

    # Use a dummy path that exists
    dummy_path = "/tmp/dummy.sqlite"
    if not os.path.exists(dummy_path):
        with open(dummy_path, "w") as f:
            f.write("")

    try:
        # If this fails with TypeError, AUDIT-002 is confirmed
        SqliteZoteroGateway(dummy_path)
    except TypeError as e:
        pytest.fail(f"Interface Violation: {e}")
    finally:
        if os.path.exists(dummy_path):
            os.remove(dummy_path)
