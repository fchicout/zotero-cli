import pytest
from zotero_cli.core.services.purge_service import PurgeService
from zotero_cli.infra.factory import GatewayFactory

@pytest.fixture
def purge_service():
    # Uses real gateway but we'll use a specific test collection
    gateway = GatewayFactory.get_zotero_gateway()
    return PurgeService(gateway)

@pytest.mark.e2e
def test_purge_logic_integration_e2e(purge_service):
    """
    High-fidelity verification of PurgeService logic against real gateway structure.
    We test dry_run=True to avoid unintended side effects in the real library 
    during this verification phase, while still hitting the full gateway stack.
    """
    # 1. Test Attachment Discovery (Dry Run)
    # Using a known parent item or searching for one
    from zotero_cli.core.models import ZoteroQuery
    import itertools
    
    # LIMIT SCOPE: Only take first 5 items to avoid freezing on large libraries
    items = list(itertools.islice(purge_service.gateway.search_items(ZoteroQuery()), 5))
    if not items:
        pytest.skip("No items in library to test purge discovery.")
    
    keys = [item.key for item in items]
    
    # Verify discovery logic doesn't crash with real data
    # SAFETY: Explicitly passing dry_run=True
    stats = purge_service.purge_attachments(keys, dry_run=True)
    assert "skipped" in stats
    assert stats["deleted"] == 0, "SAFETY VETO: E2E test attempted a real deletion!"
    assert stats["errors"] == 0

    # 2. Test Note Discovery with SDB filter (Dry Run)
    stats_notes = purge_service.purge_notes(keys, sdb_only=True, dry_run=True)
    assert "skipped" in stats_notes
    assert stats_notes["deleted"] == 0, "SAFETY VETO: E2E test attempted a real deletion!"
    assert stats_notes["errors"] == 0

    # 3. Test Tag Discovery (Dry Run)
    stats_tags = purge_service.purge_tags(keys, dry_run=True)
    assert "skipped" in stats_tags
    assert stats_tags["deleted"] == 0, "SAFETY VETO: E2E test attempted a real deletion!"
    assert stats_tags["errors"] == 0

@pytest.mark.e2e
def test_purge_offline_veto_e2e(purge_service):
    """Verify that the Offline Veto is enforced even in E2E context."""
    # Force an offline gateway
    offline_gateway = GatewayFactory.get_zotero_gateway()
    # Mocking the name since we can't easily swap the whole factory in this run
    offline_gateway.__class__.__name__ = "SqliteZoteroGateway"
    
    service = PurgeService(offline_gateway)
    with pytest.raises(RuntimeError, match="Offline Veto"):
        service.purge_attachments(["K1"])
