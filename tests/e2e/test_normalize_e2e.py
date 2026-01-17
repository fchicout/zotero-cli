import csv
import subprocess


def test_system_normalize_e2e(tmp_path):
    """
    E2E Test: Verify the 'system normalize' CLI command.
    """
    input_file = tmp_path / "ieee_raw.csv"
    output_file = tmp_path / "canonical_output.csv"

    # Setup IEEE raw format
    headers = ["Document Title", "Authors", "Publication Title", "Abstract", "DOI", "Year"]
    row = {
        "Document Title": "IEEE Paper",
        "Authors": "John Doe",
        "Publication Title": "IEEE Conf",
        "Abstract": "Summary",
        "DOI": "10.1109/test",
        "Year": "2023",
    }

    with open(input_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerow(row)

    # Action: Run CLI
    result = subprocess.run(
        ["zotero-cli", "system", "normalize", str(input_file), "--output", str(output_file)],
        capture_output=True,
        text=True,
    )

    # Assert
    assert result.returncode == 0
    assert "Normalization complete" in result.stdout
    assert output_file.exists()

    # Verify content headers are canonical
    with open(output_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames is not None
        assert "title" in reader.fieldnames
        assert "doi" in reader.fieldnames
        assert "authors" in reader.fieldnames
        first_row = next(reader)
        assert first_row["title"] == "IEEE Paper"
        assert first_row["doi"] == "10.1109/test"
