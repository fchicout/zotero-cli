from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.slr.orchestrator import SLROrchestrator
from zotero_cli.infra.sqlite_repo import SqliteZoteroGateway


@pytest.mark.unit
def test_orchestrator_missing_methods():
    """
    VALERIUS-001: SLROrchestrator must implement get_promotion_path.
    """
    orchestrator = SLROrchestrator(MagicMock())
    assert hasattr(orchestrator, "get_promotion_path"), (
        "SLROrchestrator is missing get_promotion_path"
    )


@pytest.mark.unit
def test_sqlite_gateway_interface_completeness(tmp_path):
    """
    VALERIUS-002: SqliteZoteroGateway must implement all abstract methods of ZoteroGateway.
    """
    dummy_db = tmp_path / "audit.sqlite"
    dummy_db.write_text("")

    # A TypeError here (abstract methods missing) fails the test on its own.
    SqliteZoteroGateway(str(dummy_db))
