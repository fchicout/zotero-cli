"""Tests for the AuthorFixer class."""

import pytest
from pathlib import Path
from custom.core.author_fixer import AuthorFixer


class TestAuthorFixer:
    """Test suite for AuthorFixer functionality."""
    
    def test_fix_author_string_simple_concatenation(self):
        """Test basic concatenated name separation."""
        fixer = AuthorFixer()
        
        # Simple concatenation
        result = fixer.fix_author_string("John SmithMary Jones")
        assert result == "John Smith and Mary Jones"
    
    def test_fix_author_string_preserves_compound_names(self):
        """Test that compound names like McDonald are preserved."""
        fixer = AuthorFixer()
        
        # McDonald should not be split
        result = fixer.fix_author_string("Ronald McDonald")
        assert result == "Ronald McDonald"
        
        # O'Brien should not be split
        result = fixer.fix_author_string("Patrick O'Brien")
        assert result == "Patrick O'Brien"
        
        # MacArthur should not be split
        result = fixer.fix_author_string("Douglas MacArthur")
        assert result == "Douglas MacArthur"
    
    def test_fix_author_string_anonymous(self):
        """Test that Anonymous is handled correctly."""
        fixer = AuthorFixer()
        
        result = fixer.fix_author_string("Anonymous")
        assert result == "Anonymous"
        
        result = fixer.fix_author_string("anonymous")
        assert result == "anonymous"
    
    def test_fix_author_string_multiple_concatenations(self):
        """Test multiple concatenated names."""
        fixer = AuthorFixer()
        
        result = fixer.fix_author_string("John SmithMary JonesBob Wilson")
        assert result == "John Smith and Mary Jones and Bob Wilson"
    
    def test_fix_file_creates_output(self, tmp_path):
        """Test that fix_file creates an output file."""
        fixer = AuthorFixer()
        
        # Create a test input file
        input_file = tmp_path / "test_input.bib"
        input_file.write_text(
            "@article{test2023,\n"
            "  author = {John SmithMary Jones},\n"
            "  title = {Test Article},\n"
            "  year = {2023}\n"
            "}\n",
            encoding='utf-8'
        )
        
        output_file = tmp_path / "test_output.bib"
        
        result = fixer.fix_file(input_file, output_file)
        
        assert result.success is True
        assert result.entries_count == 1  # One correction made
        assert output_file.exists()
        
        # Verify the content
        content = output_file.read_text(encoding='utf-8')
        assert "John Smith and Mary Jones" in content
    
    def test_fix_file_nonexistent_input(self, tmp_path):
        """Test that fix_file handles nonexistent input files."""
        fixer = AuthorFixer()
        
        input_file = tmp_path / "nonexistent.bib"
        output_file = tmp_path / "output.bib"
        
        result = fixer.fix_file(input_file, output_file)
        
        assert result.success is False
        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()
    
    def test_fix_file_preserves_non_author_lines(self, tmp_path):
        """Test that non-author lines are preserved unchanged."""
        fixer = AuthorFixer()
        
        input_file = tmp_path / "test_input.bib"
        input_file.write_text(
            "@article{test2023,\n"
            "  title = {Test Article},\n"
            "  author = {John Smith},\n"
            "  year = {2023},\n"
            "  journal = {Test Journal}\n"
            "}\n",
            encoding='utf-8'
        )
        
        output_file = tmp_path / "test_output.bib"
        
        result = fixer.fix_file(input_file, output_file)
        
        assert result.success is True
        
        content = output_file.read_text(encoding='utf-8')
        assert "title = {Test Article}" in content
        assert "year = {2023}" in content
        assert "journal = {Test Journal}" in content
    
    def test_fix_author_string_compound_names_with_concatenation(self):
        """Test compound names mixed with concatenated names.
        
        Note: The original script only splits on lowercase-to-uppercase transitions.
        After protecting compound names, if there's no lowercase-to-uppercase transition,
        no split occurs. For example:
        - "McDonaldPatrick" → "__MCDONALD__0__Patrick" → no lowercase before P, no split
        - "O'BrienJohn" → "__OAPOS__0__John" → no lowercase before J, no split
        - "SmithJohn" → "Smith" + "John" → "hJ" is lowercase-to-uppercase, WILL split
        """
        fixer = AuthorFixer()
        
        # McDonald followed by name starting with uppercase - NO split (no lowercase-to-uppercase)
        result = fixer.fix_author_string("Ronald McDonaldPatrick O'Brien")
        assert result == "Ronald McDonaldPatrick O'Brien"
        
        # O'Brien followed by name starting with uppercase - NO split (after protection, no lowercase-to-uppercase)
        result = fixer.fix_author_string("Patrick O'BrienJohn Smith")
        assert result == "Patrick O'BrienJohn Smith"
        
        # Regular name followed by another - WILL split (lowercase h to uppercase J)
        result = fixer.fix_author_string("John SmithMary Jones")
        assert result == "John Smith and Mary Jones"
        
        # MacArthur in the middle - splits at "hD" but not after MacArthur (protected)
        result = fixer.fix_author_string("John SmithDouglas MacArthurMary Jones")
        assert result == "John Smith and Douglas MacArthurMary Jones"
