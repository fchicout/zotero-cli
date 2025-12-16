# paper2zotero

![Build Status](https://github.com/fchicout/paper2zotero/actions/workflows/release.yml/badge.svg)
![Tests](https://github.com/fchicout/paper2zotero/actions/workflows/tests.yml/badge.svg)
![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**paper2zotero** is a robust command-line utility designed to streamline the import of research papers into [Zotero](https://www.zotero.org/). It supports fetching papers directly from **arXiv**, importing from **BibTeX** and **RIS** files, importing from **Springer** and **IEEE** CSV exports, and managing Zotero collections.

It automatically handles collection creation and populates rich metadata including authors, abstracts, DOIs, and publication dates.

## Features

*   **arXiv Integration**: Search and bulk import papers directly from arXiv queries.
*   **BibTeX & RIS Support**: Import bibliographic data from standard file formats.
*   **CSV Support**: Import from Springer and IEEE CSV exports.
*   **Zotero Management**: Automatically creates collections (folders) if they don't exist.
*   **Maintenance**: Utility to remove attachments (PDFs/snapshots) to save storage space.
*   **Flexible Input**: Accepts queries via command arguments, files, or standard input (pipes).

## Installation

### From Binaries (Recommended)
Download the latest release for your platform from the [Releases Page](https://github.com/fchicout/paper2zotero/releases).

*   **Linux**: Download `.deb` (Debian/Ubuntu) or `.rpm` (Fedora/RHEL).
    ```bash
    # Ubuntu/Debian
    sudo dpkg -i paper2zotero-linux-amd64.deb
    
    # Fedora/RHEL
    sudo rpm -i paper2zotero-linux-amd64.rpm
    ```
*   **Windows**: Download `paper2zotero.exe` and add it to your PATH.
*   **Standalone**: Download the binary `paper2zotero` and run it directly.

### From Source
Requires Python 3.8+.

```bash
git clone https://github.com/fchicout/paper2zotero.git
cd paper2zotero
pip install .
```

## Configuration

You must set the following environment variables to authenticate with Zotero:

```bash
export ZOTERO_API_KEY="your_api_key_here"
export ZOTERO_TARGET_GROUP="https://www.zotero.org/groups/1234567/group_name"
```
*   **ZOTERO_API_KEY**: Create one at [Zotero API Settings](https://www.zotero.org/settings/keys).
*   **ZOTERO_TARGET_GROUP**: The URL or ID of the group library you want to manage.

## Usage

### 1. Add a Single Paper (arXiv)
Add a specific paper by its arXiv ID.

```bash
paper2zotero add --arxiv-id "2301.00001" \
                 --title "Sample Paper Title" \
                 --abstract "This is the abstract..." \
                 --folder "My Reading List"
```

### 2. Bulk Import from arXiv
Search arXiv and import all matching results.

**Direct Query:**
```bash
paper2zotero import --query "LLM cybersecurity" --limit 50 --folder "AI Security" --verbose
```

**From File:**
```bash
paper2zotero import --file query.txt --folder "AI Security"
```

**From Pipe:**
```bash
echo "generative AI" | paper2zotero import --folder "GenAI" --limit 10
```

### 3. Import from BibTeX
Import references from a `.bib` file (e.g., exported from Google Scholar, ScienceDirect).

```bash
paper2zotero bibtex --file references.bib --folder "Literature Review" --verbose
```

### 4. Import from RIS
Import references from a `.ris` file.

```bash
paper2zotero ris --file citations.ris --folder "Research 2025"
```

### 5. Import from Springer CSV
Import references from a Springer Search Results CSV export.

```bash
paper2zotero springer-csv --file SearchResults.csv --folder "Springer Papers"
```

### 6. Import from IEEE CSV
Import references from an IEEE Xplore CSV export.

```bash
paper2zotero ieee-csv --file export2025.csv --folder "IEEE Papers"
```

### 7. Remove Attachments
Remove all child items (PDFs, snapshots) from items in a specific folder to clean up storage.

```bash
paper2zotero remove-attachments --folder "AI Security" --verbose
```

## Development

```bash
# Install dev dependencies
pip install -e .

# Run tests
python -m unittest discover tests
```

## License

MIT License. See [LICENSE](LICENSE) for details.