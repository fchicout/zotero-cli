import os
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
    assert hasattr(orchestrator, 'get_promotion_path'), "SLROrchestrator is missing get_promotion_path"

@pytest.mark.unit
def test_sqlite_gateway_interface_completeness():
    """
    VALERIUS-002: SqliteZoteroGateway must implement all abstract methods of ZoteroGateway.
    """
    dummy_db = "/tmp/audit.sqlite"
    if not os.path.exists(dummy_db):
        with open(dummy_db, "w") as f:
            f.write("")

    try:
        # If this fails with TypeError, it means abstract methods are missing
        SqliteZoteroGateway(dummy_db)
    except TypeError as e:
        pytest.fail(f"SqliteZoteroGateway is incomplete: {e}")
    finally:
        if os.path.exists(dummy_db):
            os.remove(dummy_db)
