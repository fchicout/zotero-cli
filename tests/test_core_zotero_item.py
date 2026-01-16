from zotero_cli.core.zotero_item import ZoteroItem


def test_from_raw_zotero_item_full_data():
    raw_item = {
        'key': 'ABC123DEF456',
        'data': {
            'version': 123,
            'itemType': 'journalArticle',
            'title': 'Test Article Title',
            'abstractNote': 'This is a test abstract.',
            'DOI': '10.1234/test.article',
            'extra': 'Some other info\narXiv: 2301.00001v2',
            'url': 'http://example.com/test',
            'collections': ['COL1', 'COL2']
        }
    }
    item = ZoteroItem.from_raw_zotero_item(raw_item)
    assert item.key == 'ABC123DEF456'
    assert item.version == 123
    assert item.item_type == 'journalArticle'
    assert item.title == 'Test Article Title'
    assert item.abstract == 'This is a test abstract.'
    assert item.doi == '10.1234/test.article'
    assert item.arxiv_id == '2301.00001v2'
    assert item.url == 'http://example.com/test'
    assert item.collections == ['COL1', 'COL2']
    assert item.has_pdf is False

def test_from_raw_zotero_item_minimal_data():
    raw_item = {
        'key': 'XYZ789',
        'data': {
            'version': 1,
            'itemType': 'book',
            'title': 'Minimal Book',
            'collections': []
        }
    }
    item = ZoteroItem.from_raw_zotero_item(raw_item)
    assert item.key == 'XYZ789'
    assert item.version == 1
    assert item.item_type == 'book'
    assert item.title == 'Minimal Book'
    assert item.abstract is None
    assert item.doi is None
    assert item.arxiv_id is None
    assert item.url is None
    assert item.collections == []
    assert item.has_pdf is False

def test_from_raw_zotero_item_arxiv_from_url():
    raw_item = {
        'key': 'ARXIV123',
        'data': {
            'version': 5,
            'itemType': 'preprint',
            'title': 'arXiv Paper from URL',
            'url': 'https://arxiv.org/abs/2403.12345'
        }
    }
    item = ZoteroItem.from_raw_zotero_item(raw_item)
    assert item.arxiv_id == '2403.12345'

def test_has_identifier():
    item_with_doi = ZoteroItem.from_raw_zotero_item({
        'key': 'A', 'data': {'DOI': '1.2/3', 'version':1, 'itemType': 'journalArticle'}
    })
    assert item_with_doi.has_identifier() is True

    item_with_arxiv = ZoteroItem.from_raw_zotero_item({
        'key': 'B', 'data': {'extra': 'arXiv: 1234.5678', 'version':1, 'itemType': 'journalArticle'}
    })
    assert item_with_arxiv.has_identifier() is True

    item_without_id = ZoteroItem.from_raw_zotero_item({
        'key': 'C', 'data': {'title': 'No ID', 'version':1, 'itemType': 'journalArticle'}
    })
    assert item_without_id.has_identifier() is False
