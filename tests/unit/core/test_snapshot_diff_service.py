from zotero_cli.core.services.slr.snapshot import SnapshotDiffService


def test_detect_shifts():
    service = SnapshotDiffService()

    old_snap = [
        {"key": "K1", "title": "T1", "collections": ["A"]},
        {"key": "K2", "title": "T2", "collections": ["A", "B"]},
        {"key": "K3", "title": "T3", "collections": ["C"]},
    ]
    new_snap = [
        {"key": "K1", "title": "T1", "collections": ["A", "B"]},  # Shifted
        {"key": "K2", "title": "T2", "collections": ["A", "B"]},  # Stable
        {"key": "K4", "title": "T4", "collections": ["D"]},  # Added
    ]

    shifts = service.detect_shifts(old_snap, new_snap)

    assert len(shifts) == 3
    keys = [s["key"] for s in shifts]
    assert "K1" in keys  # Changed
    assert "K4" in keys  # Added
    assert "K3" in keys  # Deleted
