from pathlib import Path
from unittest.mock import patch

import pytest
from bibtexparser.library import Library
from bibtexparser.model import Entry, Field

from zotero_cli.core.exceptions import ImportParseError
from zotero_cli.core.models import ResearchPaper
from zotero_cli.infra.bibtex_lib import BibtexLibGateway

# Real-shaped exports from three common sources, per Issue #360's explicit
# request for round-trip coverage against IEEE/Springer/Zotero output.
IEEE_EXPORT = """\
@ARTICLE{9145966,
  author={Smith, Alan B. and Chen, Wei},
  journal={IEEE Transactions on Software Engineering},
  title={A Survey of {Software} Engineering Practices},
  year={2020},
  volume={46},
  number={7},
  pages={701-718},
  doi={10.1109/TSE.2020.1234567}}
"""

SPRINGER_EXPORT = """\
@Article{Garcia2019,
author={Garcia, Maria and Kumar, Raj},
title={Machine Learning for Code Review},
journal={Empirical Software Engineering},
year={2019},
volume={24},
pages={2145--2178},
doi={10.1007/s10664-019-09701-1}
}
"""

ZOTERO_EXPORT = """\
@string{jss = "Journal of Systems and Software"}

@article{doe_zotero_export_2021,
	title = {Zotero {Export} {Test}},
	volume = {172},
	doi = {10.1016/j.jss.2020.110860},
	journal = jss,
	author = {Doe, Jane},
	year = {2021},
}
"""


def _entry(key: str, entry_type: str = "article", **field_values: str) -> Entry:
    return Entry(
        entry_type=entry_type,
        key=key,
        fields=[Field(key=k, value=v) for k, v in field_values.items()],
    )


@patch("zotero_cli.infra.bibtex_lib.bibtexparser.parse_file")
def test_parse_file_success(mock_parse_file):
    library = Library()
    library.add(
        _entry(
            "doe2023",
            title="{My Paper}",
            author="Doe, John and Smith, Jane",
            year="2023",
            journal="Journal of AI",
            doi="10.1000/1",
            abstract="Abstract here",
        )
    )
    library.add(
        _entry(
            "another",
            title="Another Paper",
            author="Single Author",
            eprint="2301.00001",
            archivePrefix="arXiv",
        )
    )
    mock_parse_file.return_value = library

    gateway = BibtexLibGateway()
    papers = list(gateway.parse_file("test.bib"))

    assert len(papers) == 2

    assert isinstance(papers[0], ResearchPaper)
    assert papers[0].title == "My Paper"
    assert papers[0].authors == ["Doe, John", "Smith, Jane"]
    assert papers[0].year == "2023"
    assert papers[0].publication == "Journal of AI"
    assert papers[0].doi == "10.1000/1"

    assert isinstance(papers[1], ResearchPaper)
    assert papers[1].authors == ["Single Author"]
    assert papers[1].arxiv_id == "2301.00001"


@patch("zotero_cli.infra.bibtex_lib.bibtexparser.parse_file")
def test_parse_file_error_is_logged(mock_parse_file, caplog):
    """Regression test for Issue #293: a BibTeX parse failure must be
    logged (not just printed), so it's diagnosable from logs alone in an
    unattended context."""
    mock_parse_file.side_effect = ValueError("malformed entry")

    gateway = BibtexLibGateway()
    with caplog.at_level("ERROR"), pytest.raises(ImportParseError, match="malformed entry"):
        list(gateway.parse_file("bad.bib"))
    assert any("bad.bib" in r.message for r in caplog.records)


def _parse(tmp_path: Path, content: str) -> list[ResearchPaper]:
    bib_file = tmp_path / "export.bib"
    bib_file.write_text(content, encoding="utf-8")
    return list(BibtexLibGateway().parse_file(str(bib_file)))


def test_round_trip_ieee_export(tmp_path):
    papers = _parse(tmp_path, IEEE_EXPORT)
    assert len(papers) == 1
    paper = papers[0]
    assert paper.title == "A Survey of Software Engineering Practices"
    assert paper.authors == ["Smith, Alan B.", "Chen, Wei"]
    assert paper.publication == "IEEE Transactions on Software Engineering"
    assert paper.year == "2020"
    assert paper.doi == "10.1109/TSE.2020.1234567"


def test_round_trip_springer_export(tmp_path):
    papers = _parse(tmp_path, SPRINGER_EXPORT)
    assert len(papers) == 1
    paper = papers[0]
    assert paper.title == "Machine Learning for Code Review"
    assert paper.authors == ["Garcia, Maria", "Kumar, Raj"]
    assert paper.publication == "Empirical Software Engineering"
    assert paper.year == "2019"
    assert paper.doi == "10.1007/s10664-019-09701-1"


def test_round_trip_zotero_export_resolves_string_macro(tmp_path):
    """Zotero exports commonly use @string macros for journal names; these
    must resolve to their literal value, not the macro key itself."""
    papers = _parse(tmp_path, ZOTERO_EXPORT)
    assert len(papers) == 1
    paper = papers[0]
    assert paper.title == "Zotero Export Test"
    assert paper.authors == ["Doe, Jane"]
    assert paper.publication == "Journal of Systems and Software"
    assert paper.year == "2021"
    assert paper.doi == "10.1016/j.jss.2020.110860"


def test_write_then_parse_round_trip_preserves_fields(tmp_path):
    """Writing a paper out and reading it back must reproduce every field,
    verifying serialize()/parse_file() stay symmetric under the 2.x API."""
    original = ResearchPaper(
        title="Round Trip Verification",
        abstract="",
        authors=["Ada Lovelace", "Grace Hopper"],
        publication="Journal of Historical Computing",
        year="1950",
        doi="10.1000/roundtrip",
        url="https://example.org/paper",
        arxiv_id="1234.56789",
        key="lovelace1950",
    )

    gateway = BibtexLibGateway()
    out_file = tmp_path / "roundtrip.bib"
    assert gateway.write_file(str(out_file), [original])

    (reparsed,) = list(gateway.parse_file(str(out_file)))
    assert reparsed.title == original.title
    assert reparsed.authors == original.authors
    assert reparsed.publication == original.publication
    assert reparsed.year == original.year
    assert reparsed.doi == original.doi
    assert reparsed.url == original.url
    assert reparsed.arxiv_id == original.arxiv_id


def _parse_one(tmp_path, body: str) -> ResearchPaper:
    bib_file = tmp_path / "one.bib"
    bib_file.write_text(body, encoding="utf-8")
    (paper,) = list(BibtexLibGateway().parse_file(str(bib_file)))
    return paper


def test_latex_escapes_become_unicode_on_import(tmp_path):
    """Issue #531: bxc's translator turns accents into real characters, and the
    existing brace stripping still removes the {B} case-protection groups."""
    paper = _parse_one(
        tmp_path,
        "@article{special_chars_2022,\n"
        '  title = {Na{\\"i}ve {B}ayes {\\`a} la carte},\n'
        '  author = {M{\\"u}ller, Hans and Erd\\H{o}s, Paul and Fran\\c{c}ois, Jean},\n'
        "  journal = {Revue d'{\\'E}tudes},\n"
        "  abstract = {The S{\\o}ren method \\& beyond},\n"
        "  year = {2022}\n"
        "}\n",
    )

    assert paper.title == "Na\u00efve Bayes \u00e0 la carte"
    assert paper.authors == ["M\u00fcller, Hans", "Erd\u0151s, Paul", "Fran\u00e7ois, Jean"]
    assert paper.publication == "Revue d'\u00c9tudes"
    assert paper.abstract == "The S\u00f8ren method & beyond"


def test_booktitle_and_journaltitle_are_translated_too(tmp_path):
    paper = _parse_one(
        tmp_path,
        '@inproceedings{k, title={T}, booktitle={Proc. of the {\\"U}berconf}, year={2020}}\n',
    )
    assert paper.publication == "Proc. of the \u00dcberconf"


def test_identifier_fields_are_left_exactly_as_written(tmp_path):
    """A DOI or URL is not prose: a backslash or percent there must survive."""
    paper = _parse_one(
        tmp_path,
        "@article{k, title={T}, doi={10.1000/a_b\\_c}, url={https://x.org/a%20b?q=1&r=2},\n"
        "  eprint={2301.00001}, archivePrefix={arXiv}, year={2020}}\n",
    )
    assert paper.doi == "10.1000/a_b\\_c"
    assert paper.url == "https://x.org/a%20b?q=1&r=2"
    assert paper.arxiv_id == "2301.00001"
    assert paper.year == "2020"


def test_plain_and_already_unicode_text_is_unchanged(tmp_path):
    paper = _parse_one(
        tmp_path,
        "@article{k, title={Plain title}, author={M\u00fcller, Hans}, journal={Journal}, year={2020}}\n",
    )
    assert paper.title == "Plain title"
    assert paper.authors == ["M\u00fcller, Hans"]
    assert paper.publication == "Journal"


def test_math_and_unknown_commands_are_not_mangled(tmp_path):
    paper = _parse_one(
        tmp_path,
        "@article{k, title={On $\\alpha$-stable laws}, abstract={Uses \\textbf{bold}}, year={2020}}\n",
    )
    assert "$\\alpha$" in paper.title
    assert "\\textbf" in paper.abstract


def test_a_missing_field_stays_missing(tmp_path):
    paper = _parse_one(tmp_path, "@article{k, year={2020}}\n")
    assert paper.title == "No Title"
    assert paper.authors == []
    assert paper.publication is None
    assert paper.abstract == ""
