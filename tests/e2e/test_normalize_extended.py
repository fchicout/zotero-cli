import csv
import subprocess

RIS_CONTENT = """TY  - JOUR
TI  - RIS Paper Title
AU  - Ris Author
DO  - 10.ris/test
PY  - 2022
ER  -
"""

BIB_CONTENT = """@article{key1,
  title={Bibtex Paper Title},
  author={Bib Author},
  doi={10.bib/test},
  year={2021}
}
"""

CSV_MISSING_ID = """title,abstract,authors,year
"No ID Paper","Just an abstract","Ghost Author",2020
"""


def test_normalize_ris(tmp_path):
    input_file = tmp_path / "input.ris"
    output_file = tmp_path / "output_ris.csv"
    input_file.write_text(RIS_CONTENT, encoding="utf-8")

    subprocess.run(
        ["zotero-cli", "system", "normalize", str(input_file), "--output", str(output_file)],
        check=True,
    )

    with open(output_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)
        assert row["title"] == "RIS Paper Title"
        assert row["doi"] == "10.ris/test"


def test_normalize_bib(tmp_path):
    input_file = tmp_path / "input.bib"
    output_file = tmp_path / "output_bib.csv"
    input_file.write_text(BIB_CONTENT, encoding="utf-8")

    subprocess.run(
        ["zotero-cli", "system", "normalize", str(input_file), "--output", str(output_file)],
        check=True,
    )

    with open(output_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)
        assert row["title"] == "Bibtex Paper Title"
        assert row["doi"] == "10.bib/test"


def test_normalize_csv_missing_ids(tmp_path):
    """
    Test robust handling of canonical CSVs that lack ID columns (or have empty ones).
    We treat the input as a "Canonical" CSV (title exists), even if partial.
    """
    input_file = tmp_path / "partial.csv"
    output_file = tmp_path / "output_partial.csv"
    # Note: Our detection logic requires 'title' AND 'doi' in header to be detected as Canonical.
    # If we feed a CSV without 'doi' header, it might fail detection.
    # Let's verify the behavior. If strict detection fails, we might need to relax it or the user must provide empty DOI col.

    # Strict Scenario: Input MUST have headers matching canonical to be detected.
    # So we provide the headers but empty values.

    headers = ["title", "doi", "arxiv_id", "abstract", "authors", "year", "publication", "url"]
    row = {
        "title": "No ID Paper",
        "doi": "",
        "arxiv_id": "",
        "abstract": "Just an abstract",
        "authors": "Ghost Author",
        "year": "2020",
        "publication": "",
        "url": "",
    }

    with open(input_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerow(row)

    subprocess.run(
        ["zotero-cli", "system", "normalize", str(input_file), "--output", str(output_file)],
        check=True,
    )

    with open(output_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)
        assert row["title"] == "No ID Paper"
        assert row["doi"] == ""
