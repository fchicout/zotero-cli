# zotero-cli

![Build Status](https://github.com/fchicout/zotero-cli/actions/workflows/release.yml/badge.svg)
![Tests](https://github.com/fchicout/zotero-cli/actions/workflows/tests.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-80%25-green)
![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**zotero-cli** (formerly paper2zotero) is a robust command-line utility designed to streamline the import of research papers into [Zotero](https://www.zotero.org/). It supports fetching papers directly from **arXiv**, importing from **BibTeX** and **RIS** files, importing from **Springer** and **IEEE** CSV exports, and managing Zotero collections.

It automatically handles collection creation and populates rich metadata including authors, abstracts, DOIs, and publication dates.

## Features

*   **arXiv Integration**: Search and bulk import papers directly from arXiv queries.
*   **BibTeX & RIS Support**: Import bibliographic data from standard file formats.
*   **CSV Support**: Import from Springer and IEEE CSV exports.
*   **Zotero Management**: Automatically creates collections (folders) if they don't exist.
*   **Maintenance**: Utility to remove attachments (PDFs/snapshots) to save storage space.
*   **Flexible Input**: Accepts queries via command arguments, files, or standard input (pipes).
*   **Collection Management**: List collections, move papers between collections, audit collection completeness, and find duplicate papers.
*   **Citation Analysis**: Generate rich citation graphs leveraging combined data from CrossRef and Semantic Scholar.

## Installation

### From Binaries (Recommended)
Download the latest release for your platform from the [Releases Page](https://github.com/fchicout/zotero-cli/releases).

*   **Linux**: Download `.deb` (Debian/Ubuntu) or `.rpm` (Fedora/RHEL).
    ```bash
    # Ubuntu/Debian
    sudo dpkg -i zotero-cli-linux-amd64.deb
    
    # Fedora/RHEL
    sudo rpm -i zotero-cli-linux-amd64.rpm
    ```
*   **Windows**: Download `zotero-cli.exe` and add it to your PATH.
*   **Standalone**: Download the binary `zotero-cli` and run it directly.

### From Source
Requires Python 3.8+.

```bash
git clone https://github.com/fchicout/zotero-cli.git
cd zotero-cli
pip install .
```

## Configuration

You must set the following environment variables to authenticate with Zotero:

```bash
export ZOTERO_API_KEY="your_zotero_api_key_here"
export ZOTERO_TARGET_GROUP="https://www.zotero.org/groups/1234567/your_group_name"
export SEMANTIC_SCHOLAR_API_KEY="your_semantic_scholar_api_key_here"
```
*   **ZOTERO_API_KEY**: Create one at [Zotero API Settings](https://www.zotero.org/settings/keys).
*   **ZOTERO_TARGET_GROUP**: The URL or ID of the group library you want to manage.
*   **SEMANTIC_SCHOLAR_API_KEY**: Obtain your API key from the Semantic Scholar API portal. This is used for enriched metadata and citation graph generation.

## Usage

### 1. Add a Single Paper (arXiv)
Add a specific paper by its arXiv ID.

```bash
zotero-cli add --arxiv-id "2301.00001" \
                 --title "Sample Paper Title" \
                 --abstract "This is the abstract..." \
                 --folder "My Reading List"
```

### 2. Bulk Import from arXiv
Search arXiv and import all matching results.

**Direct Query:**
```bash
zotero-cli import --query "LLM cybersecurity" --limit 50 --folder "AI Security" --verbose
```

**From File:**
```bash
zotero-cli import --file query.txt --folder "AI Security"
```

**From Pipe:**
```bash
echo "generative AI" | zotero-cli import --folder "GenAI" --limit 10
```

### 3. Import from BibTeX
Import references from a `.bib` file (e.g., exported from Google Scholar, ScienceDirect).

```bash
zotero-cli bibtex --file references.bib --folder "Literature Review" --verbose
```

### 4. Import from RIS
Import references from a `.ris` file.

```bash
zotero-cli ris --file citations.ris --folder "Research 2025"
```

### 5. Import from Springer CSV
Import references from a Springer Search Results CSV export.

```bash
zotero-cli springer-csv --file SearchResults.csv --folder "Springer Papers"
```

### 6. Import from IEEE CSV
Import references from an IEEE Xplore CSV export.

```bash
zotero-cli ieee-csv --file export2025.csv --folder "IEEE Papers"
```

### 7. Remove Attachments
Remove all child items (PDFs, snapshots) from items in a specific folder to clean up storage.

```bash
zotero-cli remove-attachments --folder "AI Security" --verbose
```

### 8. List Collections
List all collections in the Zotero library with their keys and item counts.

```bash
zotero-cli list-collections
```

### 9. Move Paper
Move a paper (identified by DOI or arXiv ID) from one collection to another.

```bash
zotero-cli move --id "2301.00001" --from-col "Reading List" --to-col "AI Security"
```

### 10. Audit Collection
Audit a Zotero collection for completeness (presence of ID, title, abstract, and PDF attachment).

```bash
zotero-cli audit --collection "My Research"
```

### 11. Find Duplicates
Find duplicate papers (by DOI or normalized title) across multiple Zotero collections.

```bash
zotero-cli duplicates --collections "Reading List, My Research, Archive"
```

### 12. Generate Citation Graph
Generate a directed citation graph in Graphviz DOT format for papers within specified collections. The output can be piped to `dot` to generate an image (e.g., SVG, PNG).

```bash
zotero-cli graph --collections "AI, Machine Learning" > citation_graph.dot
dot -Tsvg citation_graph.dot -o citation_graph.svg
```

### 13. Tag Management
Manage tags within your Zotero library.

**List all tags:**
```bash
zotero-cli tag list
```

**Rename a tag:**
```bash
zotero-cli tag rename --old "AI" --new "Artificial Intelligence"
```

**Delete a tag:**
```bash
zotero-cli tag delete --tag "obsolete_tag"
```

**Add tags to an item:**
```bash
zotero-cli tag add --item "ITEMKEY123" --tags "important, to_read"
```

**Remove tags from an item:**
```bash
zotero-cli tag remove --item "ITEMKEY123" --tags "to_read"
```

### 14. PDF Attachment (Auto)
Automatically find (via Unpaywall) and attach PDFs to items in a collection that are missing them.

```bash
zotero-cli attach-pdf --collection "My Reading List"
```

### 15. Search ArXiv (Advanced)
Search ArXiv using complex queries (terms, date ranges, etc.).

```bash
zotero-cli search-arxiv --query "terms: title=LLM; date_range: from 2023-01-01" --verbose
```

## Changelog

### v0.2.0 (December 16, 2025)

This release introduces significant new features and architectural improvements focused on Zotero collection management and advanced citation analysis.

**New Features:**
*   **Move Paper (`move` command)**: Easily move Zotero items between collections using their DOI or arXiv ID.
*   **Collection Audit (`audit` command)**: Verify the completeness of papers in a Zotero collection, checking for missing DOIs, arXiv IDs, titles, abstracts, and PDF attachments.
*   **Duplicate Detection (`duplicates` command)**: Identify duplicate papers across multiple specified Zotero collections based on DOI or normalized title.
*   **Citation Graph Generation (`graph` command)**: Generate Graphviz DOT format output representing citation relationships between papers in your Zotero collections. This leverages metadata from external providers.
*   **List Collections (`list-collections` command)**: View all Zotero collections in your target group, including their unique keys and item counts.

**Architectural Improvements:**
*   **Metadata Aggregation**: Implemented a `MetadataAggregatorService` to combine and select the "best" metadata from multiple external providers (currently CrossRef and Semantic Scholar).
*   **Semantic Scholar Integration**: Added `SemanticScholarAPIClient` to fetch rich metadata, including abstracts and references, adhering to rate limits.
*   **Domain Model Enhancement**: Introduced `ZoteroItem` for robust internal representation of Zotero library items and enhanced the `ResearchPaper` model to include references and citation counts.
*   **Performance Optimizations**: Refactored `ZoteroAPIClient` to use `requests.Session` for improved network efficiency and parallelized PDF attachment checks in `CollectionAuditor` using `ThreadPoolExecutor`.

## Development

Requires Python 3.8+.

```bash
# Clone the repository
git clone https://github.com/fchicout/zotero-cli.git
cd zotero-cli

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Check coverage
pytest --cov=zotero_cli --cov-report=term-missing
```

## License

MIT License. See [LICENSE](LICENSE) for details.