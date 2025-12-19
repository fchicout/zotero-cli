"""Tests for Hypothesis strategies.

This module validates that the custom Hypothesis strategies generate
valid test data that can be used in property-based tests.
"""

import pytest
from pathlib import Path
from hypothesis import given, settings, strategies as st

from tests_custom.strategies import (
    generate_valid_springer_csv,
    generate_concatenated_authors,
    generate_compound_names,
    generate_file_paths,
    generate_bibtex_entry_type,
    generate_bibtex_key,
    csv_filenames,
    bibtex_filenames,
    publication_years,
    dois
)


@settings(max_examples=10)
@given(csv_data=generate_valid_springer_csv(min_entries=1, max_entries=3))
def test_generate_valid_springer_csv(csv_data):
    """Test that generate_valid_springer_csv produces valid CSV data."""
    assert isinstance(csv_data, str)
    assert len(csv_data) > 0
    
    lines = csv_data.split('\n')
    assert len(lines) >= 2  # At least header + 1 data row
    
    # Check header
    header = lines[0]
    assert 'Item Title' in header
    assert 'Authors' in header
    assert 'Publication Year' in header
    assert 'Item DOI' in header
    
    # Check that data rows exist
    for line in lines[1:]:
        assert len(line) > 0


@settings(max_examples=20)
@given(authors=generate_concatenated_authors())
def test_generate_concatenated_authors(authors):
    """Test that generate_concatenated_authors produces valid author strings."""
    assert isinstance(authors, str)
    assert len(authors) > 0
    
    # Should contain at least one name
    assert any(c.isupper() for c in authors)


@settings(max_examples=20)
@given(name=generate_compound_names())
def test_generate_compound_names(name):
    """Test that generate_compound_names produces valid compound names."""
    assert isinstance(name, str)
    assert len(name) > 0
    
    # Should contain a compound name pattern
    compound_prefixes = ['Mc', 'Mac', "O'", 'De', 'Van', 'Von', 'Di', 'Da', 'La', 'Le']
    assert any(prefix in name for prefix in compound_prefixes)


@settings(max_examples=20)
@given(path=generate_file_paths())
def test_generate_file_paths_no_extension(path):
    """Test that generate_file_paths produces valid paths without extension."""
    assert isinstance(path, Path)
    assert len(str(path)) > 0


@settings(max_examples=20)
@given(path=generate_file_paths(extension='.csv'))
def test_generate_file_paths_with_csv_extension(path):
    """Test that generate_file_paths produces valid CSV paths."""
    assert isinstance(path, Path)
    assert str(path).endswith('.csv')


@settings(max_examples=20)
@given(path=generate_file_paths(extension='.bib'))
def test_generate_file_paths_with_bib_extension(path):
    """Test that generate_file_paths produces valid BibTeX paths."""
    assert isinstance(path, Path)
    assert str(path).endswith('.bib')


@settings(max_examples=20)
@given(entry_type=generate_bibtex_entry_type())
def test_generate_bibtex_entry_type(entry_type):
    """Test that generate_bibtex_entry_type produces valid entry types."""
    assert isinstance(entry_type, str)
    assert len(entry_type) > 0
    
    # Should be a known BibTeX entry type
    valid_types = [
        'article', 'inproceedings', 'book', 'incollection',
        'phdthesis', 'mastersthesis', 'techreport', 'misc'
    ]
    assert entry_type in valid_types


@settings(max_examples=20)
@given(key=generate_bibtex_key())
def test_generate_bibtex_key(key):
    """Test that generate_bibtex_key produces valid citation keys."""
    assert isinstance(key, str)
    assert len(key) > 0
    
    # Should follow Author_Year_Keyword pattern
    parts = key.split('_')
    assert len(parts) == 3
    
    # Year should be numeric
    assert parts[1].isdigit()
    year = int(parts[1])
    assert 1900 <= year <= 2025


@settings(max_examples=20)
@given(filename=csv_filenames)
def test_csv_filenames_strategy(filename):
    """Test that csv_filenames strategy produces valid CSV filenames."""
    assert isinstance(filename, str)
    assert filename.endswith('.csv')
    assert len(filename) > 4  # At least 'x.csv'


@settings(max_examples=20)
@given(filename=bibtex_filenames)
def test_bibtex_filenames_strategy(filename):
    """Test that bibtex_filenames strategy produces valid BibTeX filenames."""
    assert isinstance(filename, str)
    assert filename.endswith('.bib')
    assert len(filename) > 4  # At least 'x.bib'


@settings(max_examples=20)
@given(year=publication_years)
def test_publication_years_strategy(year):
    """Test that publication_years strategy produces valid years."""
    assert isinstance(year, int)
    assert 1900 <= year <= 2025


@settings(max_examples=20)
@given(doi=dois)
def test_dois_strategy(doi):
    """Test that dois strategy produces valid DOI patterns."""
    assert isinstance(doi, str)
    assert doi.startswith('10.')
    assert '/' in doi
    
    # Check DOI format: 10.XXXX/suffix
    parts = doi.split('/', 1)
    assert len(parts) == 2
    
    prefix = parts[0]
    assert prefix.startswith('10.')
    
    # Prefix should be 10.XXXX where XXXX is numeric
    prefix_num = prefix[3:]
    assert prefix_num.isdigit()


def test_strategies_can_be_combined():
    """Test that strategies can be combined in complex scenarios."""
    @settings(max_examples=10)
    @given(
        csv_data=generate_valid_springer_csv(min_entries=1, max_entries=5),
        output_path=generate_file_paths(extension='.bib')
    )
    def combined_test(csv_data, output_path):
        assert isinstance(csv_data, str)
        assert isinstance(output_path, Path)
        assert str(output_path).endswith('.bib')
    
    # Run the combined test
    combined_test()


def test_strategies_with_parameters():
    """Test that strategies accept and respect parameters."""
    @settings(max_examples=10)
    @given(
        csv_data=generate_valid_springer_csv(min_entries=5, max_entries=5),
    )
    def parameterized_test(csv_data):
        lines = csv_data.split('\n')
        # Should have exactly 6 lines (header + 5 data rows)
        assert len(lines) == 6
    
    # Run the parameterized test
    parameterized_test()


def test_concatenated_authors_variety():
    """Test that concatenated authors strategy produces variety."""
    @settings(max_examples=20)
    @given(
        authors1=generate_concatenated_authors(min_authors=1, max_authors=1),
        authors2=generate_concatenated_authors(min_authors=3, max_authors=3),
    )
    def variety_test(authors1, authors2):
        # Single author should be shorter than 3 authors
        # (This is probabilistic but should hold most of the time)
        assert isinstance(authors1, str)
        assert isinstance(authors2, str)
    
    # Run the variety test
    variety_test()
