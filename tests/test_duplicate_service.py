import pytest
from unittest.mock import Mock
from zotero_cli.core.interfaces import ZoteroGateway
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.core.services.duplicate_service import DuplicateFinder

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
    mock_gateway.get_collection_id_by_name.side_effect = \
        lambda name: "ID_COL_A" if name == "Collection A" else ("ID_COL_B" if name == "Collection B" else None)
    
    item1 = create_zotero_item("KEY1", "Unique Title 1", "10.1/1")
    item2 = create_zotero_item("KEY2", "Unique Title 2", "10.1/2")
    mock_gateway.get_items_in_collection.side_effect = [
        iter([item1]), # Collection A
        iter([item2])  # Collection B
    ]
    
    duplicates = finder.find_duplicates(["Collection A", "Collection B"])
    assert len(duplicates) == 0

def test_find_duplicates_by_doi(finder, mock_gateway):
    mock_gateway.get_collection_id_by_name.side_effect = \
        lambda name: "ID_COL_A" if name == "Collection A" else ("ID_COL_B" if name == "Collection B" else None)
    
    item1 = create_zotero_item("KEY1", "Title A", "10.1/DUPLICATE")
    item2 = create_zotero_item("KEY2", "Title B", "10.1/DUPLICATE")
    item3 = create_zotero_item("KEY3", "Another Title", "10.1/UNIQUE")
    
    mock_gateway.get_items_in_collection.side_effect = [
        iter([item1, item3]), # Collection A
        iter([item2])          # Collection B
    ]

    duplicates = finder.find_duplicates(["Collection A", "Collection B"])
    assert len(duplicates) == 1
    assert duplicates[0].identifier_key == "DOI: 10.1/duplicate"
    # Order should be preserved from the sequence of collection processing and items retrieval
    assert duplicates[0].items == [item1, item2]

def test_find_duplicates_by_title(finder, mock_gateway):
    mock_gateway.get_collection_id_by_name.side_effect = \
        lambda name: "ID_COL_A" if name == "Collection A" else ("ID_COL_B" if name == "Collection B" else None)
    
    item1 = create_zotero_item("KEY1", "Duplicate Title", None)
    item2 = create_zotero_item("KEY2", "Duplicate Title", None)
    item3 = create_zotero_item("KEY3", "Unique Title", None)

    mock_gateway.get_items_in_collection.side_effect = [
        iter([item1, item3]),
        iter([item2])
    ]
    
    duplicates = finder.find_duplicates(["Collection A", "Collection B"])
    assert len(duplicates) == 1
    assert duplicates[0].identifier_key == "TITLE: duplicate title"
    assert duplicates[0].items == [item1, item2]

def test_find_duplicates_mixed_identifiers(finder, mock_gateway):
    mock_gateway.get_collection_id_by_name.side_effect = \
        lambda name: "ID_COL_A" if name == "Collection A" else ("ID_COL_B" if name == "Collection B" else None)
    
    item_doi_1 = create_zotero_item("KEY_DOI_1", "Original Title", "10.1/MIXED")
    item_doi_2 = create_zotero_item("KEY_DOI_2", "Modified Title", "10.1/MIXED")
    item_title_1 = create_zotero_item("KEY_TITLE_1", "Common Title", None)
    item_title_2 = create_zotero_item("KEY_TITLE_2", "Common Title", None)
    item_unique = create_zotero_item("KEY_UNIQUE", "One Of A Kind", "10.1/UNIQUE_ID")

    mock_gateway.get_items_in_collection.side_effect = [
        iter([item_doi_1, item_title_1, item_unique]),
        iter([item_doi_2, item_title_2])
    ]

    duplicates = finder.find_duplicates(["Collection A", "Collection B"])
    assert len(duplicates) == 2
    
    doi_group = next(g for g in duplicates if g.identifier_key == "DOI: 10.1/mixed")
    assert doi_group.items == [item_doi_1, item_doi_2]

    title_group = next(g for g in duplicates if g.identifier_key == "TITLE: common title")
    assert title_group.items == [item_title_1, item_title_2]

def test_find_duplicates_with_missing_collection(finder, mock_gateway):
    mock_gateway.get_collection_id_by_name.side_effect = \
        lambda name: "ID_COL_A" if name == "Collection A" else None
    
    item1 = create_zotero_item("KEY1", "Title 1", "10.1/1")
    mock_gateway.get_items_in_collection.side_effect = [
        iter([item1]),
        iter([])
    ]
    
    duplicates = finder.find_duplicates(["Collection A", "Non Existent Collection"])
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