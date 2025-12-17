import unittest
from unittest.mock import Mock, call
from paper2zotero.core.interfaces import ZoteroGateway
from paper2zotero.core.zotero_item import ZoteroItem
from paper2zotero.core.services.tag_service import TagService

class TestTagService(unittest.TestCase):
    def setUp(self):
        self.mock_gateway = Mock(spec=ZoteroGateway)
        self.service = TagService(self.mock_gateway)

    def _create_item(self, key, tags):
        return ZoteroItem(key=key, version=1, item_type="journalArticle", tags=tags)

    def test_list_tags(self):
        self.mock_gateway.get_tags.return_value = ["tag1", "tag2"]
        tags = self.service.list_tags()
        self.assertEqual(tags, ["tag1", "tag2"])

    def test_add_tags_to_item(self):
        item = self._create_item("KEY1", ["existing"])
        self.mock_gateway.update_item_metadata.return_value = True
        
        result = self.service.add_tags_to_item("KEY1", item, ["new"])
        
        self.assertTrue(result)
        # Check payload format
        expected_tags = [{"tag": "existing"}, {"tag": "new"}] # Order might vary due to set
        
        # Verify call args
        args = self.mock_gateway.update_item_metadata.call_args
        self.assertEqual(args[0][0], "KEY1")
        self.assertEqual(args[0][1], 1)
        self.assertIn("tags", args[0][2])
        # Compare tags list ignoring order
        call_tags = args[0][2]["tags"]
        self.assertEqual(len(call_tags), 2)
        tag_strings = {t['tag'] for t in call_tags}
        self.assertEqual(tag_strings, {"existing", "new"})

    def test_remove_tags_from_item(self):
        item = self._create_item("KEY1", ["keep", "remove"])
        self.mock_gateway.update_item_metadata.return_value = True
        
        result = self.service.remove_tags_from_item("KEY1", item, ["remove"])
        
        self.assertTrue(result)
        args = self.mock_gateway.update_item_metadata.call_args
        call_tags = args[0][2]["tags"]
        self.assertEqual(len(call_tags), 1)
        self.assertEqual(call_tags[0]["tag"], "keep")

    def test_rename_tag(self):
        item1 = self._create_item("KEY1", ["old", "other"])
        item2 = self._create_item("KEY2", ["old"])
        self.mock_gateway.get_items_by_tag.return_value = iter([item1, item2])
        self.mock_gateway.update_item_metadata.return_value = True
        
        count = self.service.rename_tag("old", "new")
        
        self.assertEqual(count, 2)
        self.assertEqual(self.mock_gateway.update_item_metadata.call_count, 2)
        
        # Verify item1 update
        call1 = self.mock_gateway.update_item_metadata.call_args_list[0]
        tags1 = {t['tag'] for t in call1[0][2]["tags"]}
        self.assertEqual(tags1, {"new", "other"})

    def test_delete_tag(self):
        item1 = self._create_item("KEY1", ["delete_me", "stay"])
        self.mock_gateway.get_items_by_tag.return_value = iter([item1])
        self.mock_gateway.update_item_metadata.return_value = True
        
        count = self.service.delete_tag("delete_me")
        
        self.assertEqual(count, 1)
        call1 = self.mock_gateway.update_item_metadata.call_args_list[0]
        tags1 = {t['tag'] for t in call1[0][2]["tags"]}
        self.assertEqual(tags1, {"stay"})

if __name__ == '__main__':
    unittest.main()
