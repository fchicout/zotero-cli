import csv
import io
import json
from unittest.mock import MagicMock

import pytest

from zotero_cli.core.services.lookup_service import LookupService
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return MagicMock()

@pytest.fixture
def lookup_service(mock_gateway):
    return LookupService(mock_gateway)

def test_lookup_items_table(lookup_service, mock_gateway):
    keys = ["ITEM1", "ITEM2"]

    item1 = ZoteroItem(key="ITEM1", version=1, item_type="journalArticle", title="Paper 1", arxiv_id="2401.00001", date="2024")
    item2 = ZoteroItem(key="ITEM2", version=1, item_type="journalArticle", title="Paper 2", arxiv_id="2401.00002", date="2024")

    mock_gateway.get_item.side_effect = [item1, item2]

    output = lookup_service.lookup_items(keys, fields=["key", "title", "arxiv_id"], output_format="table")

    assert "| key | title | arxiv_id |" in output
    assert "| --- | --- | --- |" in output
    assert "| ITEM1 | Paper 1 | 2401.00001 |" in output
    assert "| ITEM2 | Paper 2 | 2401.00002 |" in output

def test_lookup_items_csv(lookup_service, mock_gateway):
    keys = ["ITEM1"]
    item1 = ZoteroItem(key="ITEM1", version=1, item_type="journalArticle", title="Paper 1")
    mock_gateway.get_item.return_value = item1

    output = lookup_service.lookup_items(keys, fields=["key", "title"], output_format="csv")

    reader = csv.DictReader(io.StringIO(output))
    rows = list(reader)

    assert len(rows) == 1
    assert rows[0]["key"] == "ITEM1"
    assert rows[0]["title"] == "Paper 1"

def test_lookup_items_json(lookup_service, mock_gateway):
    keys = ["ITEM1"]
    item1 = ZoteroItem(key="ITEM1", version=1, item_type="journalArticle", title="Paper 1")
    mock_gateway.get_item.return_value = item1

    output = lookup_service.lookup_items(keys, fields=["key", "title"], output_format="json")

    data = json.loads(output)
    assert len(data) == 1
    assert data[0]["key"] == "ITEM1"
    assert data[0]["title"] == "Paper 1"

def test_lookup_items_missing(lookup_service, mock_gateway):
    keys = ["MISSING"]
    mock_gateway.get_item.return_value = None

    output = lookup_service.lookup_items(keys, fields=["key", "title"], output_format="table")

    assert "| MISSING | ERROR: Item not found |" in output

def test_lookup_items_clean_fields(lookup_service, mock_gateway):
    keys = ["DIRTY"]
    item1 = ZoteroItem(key="DIRTY", version=1, item_type="journalArticle", title="Paper | With | Pipes")
    mock_gateway.get_item.return_value = item1

    output = lookup_service.lookup_items(keys, fields=["title"], output_format="table")

    assert "| Paper - With - Pipes |" in output
