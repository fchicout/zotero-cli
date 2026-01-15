import unittest
from unittest.mock import MagicMock
from zotero_cli.core.services.sync_service import SyncService
from zotero_cli.core.zotero_item import ZoteroItem

class TestSyncService(unittest.TestCase):
    def setUp(self):
        self.gateway = MagicMock()
        self.service = SyncService(self.gateway)

    def test_recover_state_from_notes_success(self):
        # Mock Collection ID
        self.gateway.get_collection_id_by_name.return_value = "ColID"
        
        # Mock Items
        item1 = ZoteroItem(key="K1", title="Paper A", version=1, item_type="journalArticle")
        item2 = ZoteroItem(key="K2", title="Paper B", version=1, item_type="journalArticle")
        self.gateway.get_items_in_collection.return_value = [item1, item2]
        
        # Mock Children (Notes)
        # Item 1 has a valid screening note
        note_content = 'Pre-text <pre>{"decision": "approve", "reason": "Relevant", "criteria": ["IC1"], "timestamp": "2024-01-01", "action": "screening_decision"}</pre>'
        self.gateway.get_item_children.side_effect = [
            [{'data': {'itemType': 'note', 'note': f"screening_decision: {note_content}"}}], # Item 1
            [] # Item 2 (No notes)
        ]
        
        from unittest.mock import patch, mock_open
        with patch("builtins.open", mock_open()) as mock_file:
            success = self.service.recover_state_from_notes("Test Col", "dummy.csv")
            
            self.assertTrue(success)
            # Verify file write
            mock_file.assert_called_with("dummy.csv", 'w', newline='', encoding='utf-8')
            handle = mock_file()
            # Check header
            handle.write.assert_any_call("key,title,decision,reason,criteria,timestamp\r\n")
            # Check row
            handle.write.assert_any_call("K1,Paper A,approve,Relevant,IC1,2024-01-01\r\n")

    def test_extract_screening_data_valid(self):
        item = ZoteroItem(key="K1", title="T", version=1, item_type="journalArticle")
        json_str = '{"decision": "reject", "reason": "Old", "criteria": ["EC2"], "action": "screening_decision"}'
        note = f'Some text screening_decision: ```json\n{json_str}\n```'
        
        self.gateway.get_item_children.return_value = [
            {'data': {'itemType': 'note', 'note': note}}
        ]
        
        data = self.service._extract_screening_data(item)
        self.assertEqual(data['decision'], 'reject')
        self.assertEqual(data['criteria'], ['EC2'])

    def test_extract_screening_data_none(self):
        item = ZoteroItem(key="K1", title="T", version=1, item_type="journalArticle")
        self.gateway.get_item_children.return_value = [{'data': {'itemType': 'attachment'}}]
        
        data = self.service._extract_screening_data(item)
        self.assertIsNone(data)

if __name__ == '__main__':
    unittest.main()