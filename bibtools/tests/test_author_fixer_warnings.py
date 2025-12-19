"""Tests for author fixer warning messages.

This module tests that the AuthorFixer properly warns users when
author fixing results in suspicious output (e.g., too many authors).
"""

import tempfile
from pathlib import Path
import pytest

from bibtools.core.author_fixer import AuthorFixer


class TestAuthorFixerWarnings:
    """Test suite for author fixer warning functionality."""
    
    def test_warns_on_excessive_authors(self, tmp_path):
        """Test that a warning is generated when fixing results in >20 authors.
        
        This can happen when the splitting heuristic goes wrong, and the user
        should be alerted to manually review these cases.
        """
        # Create a BibTeX file with an author string that will result in many splits
        # This simulates a case where the heuristic might go wrong
        test_bibtex = """@article{Test_2025_Many,
  title = {Test Article with Many Authors},
  author = {AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz},
  year = {2025},
  journal = {Test Journal},
  publisher = {Springer}
}"""
        
        input_file = tmp_path / "many_authors.bib"
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(test_bibtex)
        
        output_file = tmp_path / "many_authors_fixed.bib"
        
        # Run the fixer
        fixer = AuthorFixer()
        result = fixer.fix_file(input_file, output_file)
        
        # Should have warnings about excessive authors
        assert len(result.errors) > 0, "Expected warning about excessive authors"
        assert any("may need manual review" in error for error in result.errors), \
            "Expected 'may need manual review' message in errors"
        assert any("authors" in error.lower() for error in result.errors), \
            "Expected mention of 'authors' in warning"
    
    def test_no_warning_on_normal_authors(self, tmp_path):
        """Test that no warning is generated for normal author counts."""
        test_bibtex = """@article{Test_2025_Normal,
  title = {Test Article with Normal Authors},
  author = {John SmithMary JonesRobert BrownSarah Davis},
  year = {2025},
  journal = {Test Journal},
  publisher = {Springer}
}"""
        
        input_file = tmp_path / "normal_authors.bib"
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(test_bibtex)
        
        output_file = tmp_path / "normal_authors_fixed.bib"
        
        # Run the fixer
        fixer = AuthorFixer()
        result = fixer.fix_file(input_file, output_file)
        
        # Should have no warnings
        assert len(result.errors) == 0, f"Unexpected warnings: {result.errors}"
    
    def test_warning_includes_line_number(self, tmp_path):
        """Test that warnings include the line number for easy location."""
        test_bibtex = """@article{Test_2025_Many,
  title = {Test Article},
  author = {AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz},
  year = {2025},
  journal = {Test Journal}
}"""
        
        input_file = tmp_path / "line_test.bib"
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(test_bibtex)
        
        output_file = tmp_path / "line_test_fixed.bib"
        
        # Run the fixer
        fixer = AuthorFixer()
        result = fixer.fix_file(input_file, output_file)
        
        # Warning should include line number
        assert len(result.errors) > 0
        assert any("Line" in error for error in result.errors), \
            "Expected line number in warning message"
    
    def test_success_true_even_with_warnings(self, tmp_path):
        """Test that operation is still marked successful even with warnings.
        
        Warnings are informational - the file is still processed and saved,
        but the user should review the flagged entries.
        """
        test_bibtex = """@article{Test_2025_Many,
  title = {Test Article},
  author = {AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz},
  year = {2025}
}"""
        
        input_file = tmp_path / "success_test.bib"
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(test_bibtex)
        
        output_file = tmp_path / "success_test_fixed.bib"
        
        # Run the fixer
        fixer = AuthorFixer()
        result = fixer.fix_file(input_file, output_file)
        
        # Should be successful despite warnings
        assert result.success is True, "Operation should succeed even with warnings"
        assert len(result.errors) > 0, "Should have warnings"
        assert output_file.exists(), "Output file should be created"
    
    def test_multiple_problematic_entries(self, tmp_path):
        """Test that multiple problematic entries all generate warnings."""
        test_bibtex = """@article{Test1_2025_Many,
  title = {First Article},
  author = {AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz},
  year = {2025}
}

@article{Test2_2025_Normal,
  title = {Second Article},
  author = {John SmithMary Jones},
  year = {2025}
}

@article{Test3_2025_Many,
  title = {Third Article},
  author = {AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz},
  year = {2025}
}"""
        
        input_file = tmp_path / "multiple_test.bib"
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(test_bibtex)
        
        output_file = tmp_path / "multiple_test_fixed.bib"
        
        # Run the fixer
        fixer = AuthorFixer()
        result = fixer.fix_file(input_file, output_file)
        
        # Should have warnings for both problematic entries
        assert len(result.errors) >= 2, \
            f"Expected at least 2 warnings, got {len(result.errors)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
