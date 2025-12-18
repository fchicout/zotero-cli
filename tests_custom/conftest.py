"""Pytest configuration and fixtures for custom code tests.

This module provides shared fixtures and configuration for testing the custom
CSV-to-BibTeX conversion pipeline, including sample data generation and
Hypothesis settings.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from hypothesis import settings

# Configure Hypothesis settings globally
# Set max_examples to 100 as specified in the design document
settings.register_profile("default", max_examples=100, deadline=None)
settings.load_profile("default")


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files.
    
    Yields:
        Path: Path to temporary directory
        
    The directory is automatically cleaned up after the test completes.
    """
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_springer_csv(temp_dir):
    """Create a sample Springer CSV file for testing.
    
    Args:
        temp_dir: Temporary directory fixture
        
    Returns:
        Path: Path to the created CSV file
        
    The CSV contains realistic Springer export data with multiple entries
    including concatenated author names for testing the author fixer.
    """
    csv_content = """Item Title,Publication Title,Book Series Title,Journal Volume,Journal Issue,Item DOI,Authors,Publication Year,URL,Content Type
Large Language Model-Based Network Intrusion Detection,Proceedings of International Conference on Information Technology and Applications,,,,10.1007/978-981-96-1758-6_26,Dhruv DaveyKayvan KarimHani Ragab HassenHadj Batatia,2025,https://link.springer.com/chapter/10.1007/978-981-96-1758-6_26,Conference paper
Localized large language model TCNNet 9B for Taiwanese networking and cybersecurity,Scientific Reports,,,,10.1038/s41598-025-90320-9,Jiun-Yi YangChia-Chun Wu,2025,https://link.springer.com/article/10.1038/s41598-025-90320-9,Article
Artificial Intelligence and Cyber Security,"Machine Learning, Optimization, and Data Science",,,,10.1007/978-3-031-82481-4_8,Martti Lehto,2025,https://link.springer.com/chapter/10.1007/978-3-031-82481-4_8,Conference paper
"""
    
    csv_file = temp_dir / "sample_springer.csv"
    csv_file.write_text(csv_content, encoding='utf-8')
    return csv_file


@pytest.fixture
def sample_bibtex_with_concatenated_authors(temp_dir):
    """Create a sample BibTeX file with concatenated author names.
    
    Args:
        temp_dir: Temporary directory fixture
        
    Returns:
        Path: Path to the created BibTeX file
        
    The BibTeX file contains entries with various author name patterns:
    - Simple concatenated names (JohnSmithMaryJones)
    - Compound names that should be preserved (McDonald, O'Brien, MacArthur)
    - Mixed patterns for comprehensive testing
    """
    bibtex_content = """@article{test2023a,
  author = {John SmithMary Jones},
  title = {Test Article One},
  year = {2023},
  journal = {Test Journal},
  doi = {10.1234/test1}
}

@article{test2023b,
  author = {Ronald McDonaldPatrick O'Brien},
  title = {Test Article Two},
  year = {2023},
  journal = {Test Journal},
  doi = {10.1234/test2}
}

@article{test2023c,
  author = {Douglas MacArthurJane DoeRobert Brown},
  title = {Test Article Three},
  year = {2023},
  journal = {Test Journal},
  doi = {10.1234/test3}
}

@article{test2023d,
  author = {Anonymous},
  title = {Test Article Four},
  year = {2023},
  journal = {Test Journal},
  doi = {10.1234/test4}
}
"""
    
    bibtex_file = temp_dir / "test_authors.bib"
    bibtex_file.write_text(bibtex_content, encoding='utf-8')
    return bibtex_file


@pytest.fixture
def sample_bibtex_fixed(temp_dir):
    """Create a sample BibTeX file with properly fixed author names.
    
    Args:
        temp_dir: Temporary directory fixture
        
    Returns:
        Path: Path to the created BibTeX file
        
    This represents the expected output after author name fixing has been applied.
    """
    bibtex_content = """@article{test2023a,
  author = {John Smith and Mary Jones},
  title = {Test Article One},
  year = {2023},
  journal = {Test Journal},
  doi = {10.1234/test1}
}

@article{test2023b,
  author = {Ronald McDonald and Patrick O'Brien},
  title = {Test Article Two},
  year = {2023},
  journal = {Test Journal},
  doi = {10.1234/test2}
}

@article{test2023c,
  author = {Douglas MacArthur and Jane Doe and Robert Brown},
  title = {Test Article Three},
  year = {2023},
  journal = {Test Journal},
  doi = {10.1234/test3}
}

@article{test2023d,
  author = {Anonymous},
  title = {Test Article Four},
  year = {2023},
  journal = {Test Journal},
  doi = {10.1234/test4}
}
"""
    
    bibtex_file = temp_dir / "test_authors_fixed.bib"
    bibtex_file.write_text(bibtex_content, encoding='utf-8')
    return bibtex_file


@pytest.fixture
def empty_csv(temp_dir):
    """Create an empty CSV file for testing error handling.
    
    Args:
        temp_dir: Temporary directory fixture
        
    Returns:
        Path: Path to the created empty CSV file
    """
    csv_file = temp_dir / "empty.csv"
    csv_file.write_text("", encoding='utf-8')
    return csv_file


@pytest.fixture
def malformed_csv(temp_dir):
    """Create a malformed CSV file for testing error handling.
    
    Args:
        temp_dir: Temporary directory fixture
        
    Returns:
        Path: Path to the created malformed CSV file
        
    The CSV is missing required columns that the converter expects.
    """
    csv_content = """Column1,Column2,Column3
Value1,Value2,Value3
Value4,Value5,Value6
"""
    
    csv_file = temp_dir / "malformed.csv"
    csv_file.write_text(csv_content, encoding='utf-8')
    return csv_file


@pytest.fixture
def large_springer_csv(temp_dir):
    """Create a large Springer CSV file for testing multi-file output.
    
    Args:
        temp_dir: Temporary directory fixture
        
    Returns:
        Path: Path to the created CSV file
        
    The CSV contains 100 entries to test the file splitting functionality
    (default is 49 entries per file, so this should create 3 files).
    """
    csv_lines = [
        "Item Title,Publication Title,Book Series Title,Journal Volume,Journal Issue,Item DOI,Authors,Publication Year,URL,Content Type"
    ]
    
    for i in range(100):
        title = f"Research Paper {i}: Advanced Machine Learning Techniques"
        journal = f"International Journal of AI Research"
        doi = f"10.1007/test-{i:04d}"
        authors = f"Author{i} LastName{i}"
        year = 2020 + (i % 5)
        url = f"https://link.springer.com/article/{doi}"
        content_type = "Article" if i % 2 == 0 else "Conference paper"
        volume = str(10 + (i // 10))
        issue = str((i % 10) + 1)
        
        csv_lines.append(
            f'"{title}","{journal}",,{volume},{issue},{doi},{authors},{year},{url},{content_type}'
        )
    
    csv_content = '\n'.join(csv_lines)
    csv_file = temp_dir / "large_springer.csv"
    csv_file.write_text(csv_content, encoding='utf-8')
    return csv_file


@pytest.fixture
def output_dir(temp_dir):
    """Create an output directory for test results.
    
    Args:
        temp_dir: Temporary directory fixture
        
    Returns:
        Path: Path to the output directory
        
    The directory is created within the temporary directory and will be
    cleaned up automatically.
    """
    output_path = temp_dir / "output"
    output_path.mkdir(exist_ok=True)
    return output_path


@pytest.fixture
def fixtures_dir():
    """Get the path to the fixtures directory.
    
    Returns:
        Path: Path to tests_custom/fixtures directory
        
    This fixture provides access to the permanent fixture files stored
    in the repository for reference and comparison testing.
    """
    return Path(__file__).parent / "fixtures"
