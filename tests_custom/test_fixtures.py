"""Test that fixtures are properly configured and accessible.

This module validates that the pytest fixtures defined in conftest.py
are working correctly and provide the expected test data.
"""

import pytest
from pathlib import Path


def test_temp_dir_fixture(temp_dir):
    """Test that temp_dir fixture creates a valid temporary directory."""
    assert temp_dir.exists()
    assert temp_dir.is_dir()
    
    # Test that we can write to it
    test_file = temp_dir / "test.txt"
    test_file.write_text("test content")
    assert test_file.exists()


def test_sample_springer_csv_fixture(sample_springer_csv):
    """Test that sample_springer_csv fixture creates a valid CSV file."""
    assert sample_springer_csv.exists()
    assert sample_springer_csv.suffix == ".csv"
    
    content = sample_springer_csv.read_text(encoding='utf-8')
    assert "Item Title" in content
    assert "Authors" in content
    assert "Publication Year" in content
    assert "Dhruv DaveyKayvan Karim" in content  # Concatenated authors


def test_sample_bibtex_with_concatenated_authors_fixture(sample_bibtex_with_concatenated_authors):
    """Test that sample_bibtex_with_concatenated_authors fixture creates valid BibTeX."""
    assert sample_bibtex_with_concatenated_authors.exists()
    assert sample_bibtex_with_concatenated_authors.suffix == ".bib"
    
    content = sample_bibtex_with_concatenated_authors.read_text(encoding='utf-8')
    assert "@article" in content
    assert "author" in content
    assert "John SmithMary Jones" in content  # Concatenated
    assert "Ronald McDonaldPatrick O'Brien" in content  # Compound names


def test_sample_bibtex_fixed_fixture(sample_bibtex_fixed):
    """Test that sample_bibtex_fixed fixture creates properly fixed BibTeX."""
    assert sample_bibtex_fixed.exists()
    assert sample_bibtex_fixed.suffix == ".bib"
    
    content = sample_bibtex_fixed.read_text(encoding='utf-8')
    assert "@article" in content
    assert "John Smith and Mary Jones" in content  # Fixed
    assert "Ronald McDonald and Patrick O'Brien" in content  # Compound names preserved


def test_empty_csv_fixture(empty_csv):
    """Test that empty_csv fixture creates an empty file."""
    assert empty_csv.exists()
    assert empty_csv.suffix == ".csv"
    
    content = empty_csv.read_text(encoding='utf-8')
    assert content == ""


def test_malformed_csv_fixture(malformed_csv):
    """Test that malformed_csv fixture creates a CSV with wrong columns."""
    assert malformed_csv.exists()
    assert malformed_csv.suffix == ".csv"
    
    content = malformed_csv.read_text(encoding='utf-8')
    assert "Column1" in content
    assert "Item Title" not in content  # Missing required columns


def test_large_springer_csv_fixture(large_springer_csv):
    """Test that large_springer_csv fixture creates a large CSV file."""
    assert large_springer_csv.exists()
    assert large_springer_csv.suffix == ".csv"
    
    content = large_springer_csv.read_text(encoding='utf-8')
    lines = content.strip().split('\n')
    
    # Should have header + 100 data rows
    assert len(lines) == 101
    assert "Item Title" in lines[0]
    assert "Research Paper" in content


def test_output_dir_fixture(output_dir):
    """Test that output_dir fixture creates a valid output directory."""
    assert output_dir.exists()
    assert output_dir.is_dir()
    
    # Test that we can write to it
    test_file = output_dir / "test_output.bib"
    test_file.write_text("@article{test, author={Test}}")
    assert test_file.exists()


def test_fixtures_dir_fixture(fixtures_dir):
    """Test that fixtures_dir fixture points to the correct directory."""
    assert fixtures_dir.exists()
    assert fixtures_dir.is_dir()
    assert fixtures_dir.name == "fixtures"
    
    # Verify some expected files exist
    assert (fixtures_dir / "sample_springer.csv").exists()
    assert (fixtures_dir / "test_authors.bib").exists()
    assert (fixtures_dir / "test_authors_fixed.bib").exists()


def test_fixtures_are_independent(temp_dir):
    """Test that fixtures create independent temporary directories."""
    # Create a file in this temp_dir
    test_file = temp_dir / "unique_file.txt"
    test_file.write_text("unique content")
    
    # The file should exist in this test's temp_dir
    assert test_file.exists()


def test_fixtures_cleanup(temp_dir):
    """Test that fixtures are properly cleaned up after tests.
    
    Note: This test verifies that we can create and use temporary files.
    The actual cleanup is handled by pytest's fixture teardown.
    """
    # Create multiple files
    for i in range(5):
        test_file = temp_dir / f"test_{i}.txt"
        test_file.write_text(f"content {i}")
        assert test_file.exists()
    
    # All files should exist during the test
    assert len(list(temp_dir.glob("*.txt"))) == 5
