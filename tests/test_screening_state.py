import pytest
import os
import csv
from zotero_cli.core.services.screening_state import ScreeningStateService
from zotero_cli.core.zotero_item import ZoteroItem
from unittest.mock import MagicMock

def test_screening_state_loading(tmp_path):
    state_file = tmp_path / "screening_state.csv"
    # Create dummy state
    with open(state_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['Timestamp', 'Key', 'Decision', 'Code', 'Persona', 'Phase'])
        writer.writeheader()
        writer.writerow({'Timestamp': 'now', 'Key': 'K1', 'Decision': 'INCLUDE', 'Code': 'IC1', 'Persona': 'P1', 'Phase': 'T'})
    
    service = ScreeningStateService(str(state_file))
    assert service.is_screened('K1')
    assert not service.is_screened('K2')

def test_screening_state_record(tmp_path):
    state_file = tmp_path / "screening_state.csv"
    service = ScreeningStateService(str(state_file))
    
    service.record_decision('K2', 'EXCLUDE', 'EC1', 'P2', 'F')
    
    assert service.is_screened('K2')
    
    with open(state_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]['Key'] == 'K2'
        assert rows[0]['Decision'] == 'EXCLUDE'

def test_screening_state_filter(tmp_path):
    state_file = tmp_path / "screening_state.csv"
    service = ScreeningStateService(str(state_file))
    service.screened_keys.add('K1')
    
    item1 = MagicMock(spec=ZoteroItem)
    item1.key = 'K1'
    item2 = MagicMock(spec=ZoteroItem)
    item2.key = 'K2'
    
    pending = service.filter_pending([item1, item2])
    assert len(pending) == 1
    assert pending[0].key == 'K2'
