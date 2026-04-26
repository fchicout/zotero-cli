import pytest
from zotero_cli.cli.presenters.rag_presenter import HumanPresenter, JsonPresenter, ContextPresenter
from zotero_cli.core.models import SearchResult
from zotero_cli.core.zotero_item import ZoteroItem
from unittest.mock import MagicMock

@pytest.fixture
def sample_results():
    item = MagicMock(spec=ZoteroItem)
    item.title = "Paper A"
    item.version = 1
    item.tags = ["tag1"]
    
    return [
        SearchResult(
            item_key="K1",
            text="Snippet content",
            score=0.9,
            metadata={"citation_key": "Auth2024", "qa_score": 5.0, "phase_folder": "1-T&A"},
            item=item
        )
    ]

def test_human_presenter(sample_results, capsys):
    presenter = HumanPresenter()
    presenter.present(sample_results)
    out = capsys.readouterr().out
    assert "Auth2024" in out
    assert "Snippet content" in out

def test_json_presenter(sample_results, capsys):
    presenter = JsonPresenter()
    presenter.present(sample_results)
    out = capsys.readouterr().out
    assert '"item_key": "K1"' in out
    assert '"relevance_score": 0.9' in out

def test_context_presenter(sample_results, capsys):
    presenter = ContextPresenter()
    presenter.present(sample_results)
    out = capsys.readouterr().out
    assert "[CITED_EVIDENCE_START]" in out
    assert "CITATION_KEY: Auth2024" in out
    assert "QUALITY_SCORE: 5.0" in out
    assert "TEXT: Snippet content" in out
