from unittest.mock import Mock

import pytest

from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.services.duplicate_service import DuplicateFinder
from zotero_cli.core.zotero_item import ZoteroItem


@pytest.fixture
def mock_gateway():
    return Mock(spec=ZoteroGateway)

@pytest.fixture
def finder(mock_gateway):
    return DuplicateFinder(mock_gateway)

def create_zotero_item(key, title=None, doi=None):
    raw_item = {
        'key': key,
        'data': {
            'version': 1,
            'itemType': 'journalArticle',
            'title': title,
            'DOI': doi,
        }
    }
    return ZoteroItem.from_raw_zotero_item(raw_item)

def test_find_duplicates_no_duplicates(finder, mock_gateway):
    item1 = create_zotero_item("KEY1", "Unique Title 1", "10.1/1")
    item2 = create_zotero_item("KEY2", "Unique Title 2", "10.1/2")
    mock_gateway.get_items_in_collection.side_effect = [
        iter([item1]),
        iter([item2])
    ]
    mock_gateway.get_collection.return_value = {"key": "ID_A"}

    duplicates = finder.find_duplicates(["ID_A", "ID_B"])
    assert len(duplicates) == 0

def test_find_duplicates_by_doi(finder, mock_gateway):
    item1 = create_zotero_item("KEY1", "Title A", "10.1/DUPLICATE")
    item2 = create_zotero_item("KEY2", "Title B", "10.1/DUPLICATE")
    item3 = create_zotero_item("KEY3", "Another Title", "10.1/UNIQUE")

    mock_gateway.get_items_in_collection.side_effect = [
        iter([item1, item3]),
        iter([item2])
    ]
    mock_gateway.get_collection.return_value = {"key": "ID_A"}

    duplicates = finder.find_duplicates(["ID_A", "ID_B"])
    assert len(duplicates) == 1
    assert duplicates[0]['doi'] == "10.1/DUPLICATE"
    assert set(duplicates[0]['keys']) == {"KEY1", "KEY2"}

def test_find_duplicates_by_title(finder, mock_gateway):
    item1 = create_zotero_item("KEY1", "Duplicate Title", None)
    item2 = create_zotero_item("KEY2", "Duplicate Title", None)
    item3 = create_zotero_item("KEY3", "Unique Title", None)

    mock_gateway.get_items_in_collection.side_effect = [
        iter([item1, item3]),
        iter([item2])
    ]
    mock_gateway.get_collection.return_value = {"key": "ID_A"}

    duplicates = finder.find_duplicates(["ID_A", "ID_B"])
    assert len(duplicates) == 1
    assert duplicates[0]['title'] == "Duplicate Title"
    assert set(duplicates[0]['keys']) == {"KEY1", "KEY2"}

def test_find_duplicates_mixed_identifiers(finder, mock_gateway):
    item_doi_1 = create_zotero_item("KEY_DOI_1", "Original Title", "10.1/MIXED")
    item_doi_2 = create_zotero_item("KEY_DOI_2", "Modified Title", "10.1/MIXED")
    item_title_1 = create_zotero_item("KEY_TITLE_1", "Common Title", None)
    item_title_2 = create_zotero_item("KEY_TITLE_2", "Common Title", None)
    item_unique = create_zotero_item("KEY_UNIQUE", "One Of A Kind", "10.1/UNIQUE_ID")

    mock_gateway.get_items_in_collection.side_effect = [
        iter([item_doi_1, item_title_1, item_unique]),
        iter([item_doi_2, item_title_2])
    ]
    mock_gateway.get_collection.return_value = {"key": "ID_A"}

    duplicates = finder.find_duplicates(["ID_A", "ID_B"])
    assert len(duplicates) == 2

    doi_group = next(g for g in duplicates if g['doi'] == "10.1/MIXED")
    assert set(doi_group['keys']) == {"KEY_DOI_1", "KEY_DOI_2"}

    title_group = next(g for g in duplicates if g['title'] == "Common Title")
    assert set(title_group['keys']) == {"KEY_TITLE_1", "KEY_TITLE_2"}

def test_find_duplicates_with_missing_collection(finder, mock_gateway):
    item1 = create_zotero_item("KEY1", "Title 1", "10.1/1")
    mock_gateway.get_items_in_collection.side_effect = [
        iter([item1]),
        iter([])
    ]
    mock_gateway.get_collection.side_effect = [{"key": "A"}, None]

    duplicates = finder.find_duplicates(["A", "MISSING"])
    assert len(duplicates) == 0

@pytest.mark.parametrize("input_doi, expected", [
    ("10.123/ABC", "10.123/abc"),
    (" 10.123/ABC ", "10.123/abc"),
])
def test_normalization_doi(finder, input_doi, expected):
    assert finder._normalize_doi(input_doi) == expected

@pytest.mark.parametrize("input_title, expected", [
    ("A Title. With Punctuation!", "a title with punctuation"),
    ("  Another  Title  ", "another title"),
    ("Résumé paper", "resume paper"),
])
def test_normalization_title(finder, input_title, expected):
    assert finder._normalize_title(input_title) == expected
