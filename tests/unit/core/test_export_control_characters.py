"""Issue #592 (GHSA-3r38-p632-f79q): files written by the exporters carry no terminal
control characters, whatever a shared library or a metadata source put in a field."""

import re
from pathlib import Path
from typing import Any
from unittest.mock import create_autospec

import pytest

from zotero_cli.core.interfaces import (
    AttachmentRepository,
    CollectionRepository,
    ItemRepository,
    NoteRepository,
    RisGateway,
)
from zotero_cli.core.models import ResearchPaper
from zotero_cli.core.services.attachment_service import AttachmentService
from zotero_cli.core.services.export_service import ExportService
from zotero_cli.core.services.metadata_aggregator import MetadataAggregatorService
from zotero_cli.core.zotero_item import ZoteroItem
from zotero_cli.infra.bibtex_lib import BibtexLibGateway
from zotero_cli.infra.bxc_formatter import BxcBibliographyFormatter
from zotero_cli.infra.ris_lib import RisLibGateway

ESC, BEL = chr(27), chr(7)
# Everything below 0x20 except tab, newline and carriage return; DEL and the C1 range.
FORBIDDEN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f‪-‮⁦-⁩]")


def _evil(text: str) -> str:
    return f"{text} {ESC}]52;c;QUJD{BEL} {ESC}[31mred{ESC}[0m"


def _paper() -> ResearchPaper:
    return ResearchPaper(
        title=_evil("Müller 日本語 title"),
        abstract=_evil("An abstract"),
        key="K1",
        authors=[_evil("Ada Lovelace"), "Grace Hopper"],
        publication=_evil("Journal"),
        year="2020",
        doi=_evil("10.1/x"),
        url="https://example.org/" + ESC + "x",
        arxiv_id=_evil("2001.00001"),
        extra=_evil("Extra"),
    )


def test_without_controls_cleans_every_text_field_and_keeps_the_rest():
    paper = _paper().without_controls()

    for value in (paper.title, paper.abstract, paper.publication, paper.doi, paper.url):
        assert not FORBIDDEN.search(value or "")
        assert ESC not in (value or "")
    assert not any(FORBIDDEN.search(a) for a in paper.authors)
    assert paper.title.startswith("Müller 日本語 title")
    assert paper.authors[1] == "Grace Hopper"
    assert paper.year == "2020"
    assert paper.key == "K1"


def test_without_controls_does_not_change_the_original():
    original = _paper()

    original.without_controls()

    assert ESC in original.title


@pytest.mark.parametrize("gateway", [BibtexLibGateway, RisLibGateway])
def test_bibtex_and_ris_output_has_no_control_characters(gateway):
    text = gateway().serialize([_paper()])

    assert not FORBIDDEN.search(text)
    assert ESC not in text
    assert BEL not in text
    assert "Müller 日本語 title" in text


def _export_service() -> ExportService:
    return ExportService(
        create_autospec(CollectionRepository, instance=True),
        BibtexLibGateway(),
        create_autospec(RisGateway, instance=True),
        BxcBibliographyFormatter(offline=True),
    )


def _item() -> ZoteroItem:
    return ZoteroItem(
        key="K1",
        version=1,
        item_type="journalArticle",
        title=_evil("A title"),
        authors=["Ada Lovelace"],
        date="2020",
        doi="10.1/x",
        raw_data={"data": {"publicationTitle": _evil("Journal")}},
    )


def test_item_export_to_bibtex_and_bibliography_has_no_control_characters():
    service = _export_service()

    bibtex = service.serialize_bibtex([_item()])
    bibliography = service.serialize_bibliography([_item()], "apa", "plain")

    for text in (bibtex, bibliography):
        assert not FORBIDDEN.search(text)
        assert "A title" in text


def test_markdown_export_strips_controls_and_turns_a_form_feed_into_a_blank_line(tmp_path: Path):
    service = AttachmentService(
        create_autospec(ItemRepository, instance=True),
        create_autospec(CollectionRepository, instance=True),
        create_autospec(AttachmentRepository, instance=True),
        create_autospec(NoteRepository, instance=True),
        create_autospec(MetadataAggregatorService, instance=True),
    )
    page_break = chr(12)
    text = f"page one {ESC}]8;;http://evil{BEL}link{page_break}page two"
    service.get_fulltext = lambda *args, **kwargs: text  # type: ignore[method-assign]

    outcome = service._export_item_markdown(_item(), tmp_path, "PDF1")

    written = next(tmp_path.glob("K1_*.md")).read_text(encoding="utf-8")
    assert outcome == "success"
    assert not FORBIDDEN.search(written)
    assert "page one" in written
    assert "\n\npage two" in written


def test_a_new_text_field_on_the_paper_cannot_skip_the_cleaning():
    """`without_controls` lists the fields by name: this fails when someone adds a text
    field to `ResearchPaper` and forgets it there."""
    import dataclasses

    text_fields = [
        f.name
        for f in dataclasses.fields(ResearchPaper)
        if "str" in str(f.type) and "int" not in str(f.type)
    ]
    evil: dict[str, Any] = {
        name: ([_evil("x")] if "List" in str(f.type) else _evil("x"))
        for f in dataclasses.fields(ResearchPaper)
        for name in [f.name]
        if name in text_fields
    }

    cleaned = dataclasses.replace(_paper(), **evil).without_controls()

    for name in text_fields:
        value = getattr(cleaned, name)
        flat = value if isinstance(value, list) else [value]
        assert not any(ESC in v for v in flat), name
