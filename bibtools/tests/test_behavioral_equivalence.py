"""Behavioral equivalence validation tests.

This module validates that the refactored code produces functionally equivalent
output to the original scripts. It tests the complete conversion pipeline:
CSV -> BibTeX -> Author Fixed BibTeX

**Validates: Requirements 2.5**
"""

import csv
import tempfile
from pathlib import Path
import pytest

# Import original scripts
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "converters"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "utils"))

from csv_to_bibtex import csv_to_bibtex
from fix_bibtex_authors_claude import process_bibtex_file

# Import refactored code
from bibtools.core.csv_converter import CSVConverter
from bibtools.core.author_fixer import AuthorFixer


# Sample Springer CSV data for testing
SAMPLE_CSV_DATA = [
    {
        'Item Title': 'Large Language Model-Based Network Intrusion Detection',
        'Publication Title': 'Proceedings of International Conference on Information Technology and Applications',
        'Book Series Title': '',
        'Journal Volume': '',
        'Journal Issue': '',
        'Item DOI': '10.1007/978-981-96-1758-6_26',
        'Authors': 'Dhruv DaveyKayvan KarimHani Ragab HassenHadj Batatia',
        'Publication Year': '2025',
        'URL': 'https://link.springer.com/chapter/10.1007/978-981-96-1758-6_26',
        'Content Type': 'Conference paper'
    },
    {
        'Item Title': 'Localized large language model TCNNet 9B for Taiwanese networking and cybersecurity',
        'Publication Title': 'Scientific Reports',
        'Book Series Title': '',
        'Journal Volume': '',
        'Journal Issue': '',
        'Item DOI': '10.1038/s41598-025-90320-9',
        'Authors': 'Jiun-Yi YangChia-Chun Wu',
        'Publication Year': '2025',
        'URL': 'https://link.springer.com/article/10.1038/s41598-025-90320-9',
        'Content Type': 'Article'
    },
    {
        'Item Title': 'Artificial Intelligence and Cyber Security',
        'Publication Title': 'Machine Learning, Optimization, and Data Science',
        'Book Series Title': '',
        'Journal Volume': '',
        'Journal Issue': '',
        'Item DOI': '10.1007/978-3-031-82481-4_8',
        'Authors': 'Martti Lehto',
        'Publication Year': '2025',
        'URL': 'https://link.springer.com/chapter/10.1007/978-3-031-82481-4_8',
        'Content Type': 'Conference paper'
    },
]


def create_test_csv(data, path):
    """Create a test CSV file with the given data."""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        if data:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)


def normalize_bibtex_content(content):
    """Normalize BibTeX content for comparison.
    
    Removes whitespace variations and normalizes formatting to allow
    for minor differences in output format while ensuring semantic equivalence.
    """
    # Remove extra whitespace
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    # Sort lines within each entry to handle field order differences
    normalized = []
    current_entry = []
    
    for line in lines:
        if line.startswith('@'):
            if current_entry:
                # Sort fields within entry (except first line which is @type{key,)
                normalized.append(current_entry[0])
                normalized.extend(sorted(current_entry[1:-1]))
                normalized.append(current_entry[-1])
                current_entry = []
            current_entry.append(line)
        elif line == '}':
            current_entry.append(line)
            # Flush entry
            if len(current_entry) > 1:
                normalized.append(current_entry[0])
                if len(current_entry) > 2:
                    normalized.extend(sorted(current_entry[1:-1]))
                normalized.append(current_entry[-1])
            current_entry = []
        else:
            current_entry.append(line)
    
    # Handle last entry if exists
    if current_entry:
        normalized.append(current_entry[0])
        if len(current_entry) > 2:
            normalized.extend(sorted(current_entry[1:-1]))
        if len(current_entry) > 1:
            normalized.append(current_entry[-1])
    
    return '\n'.join(normalized)


def extract_bibtex_entries(content):
    """Extract individual BibTeX entries from content."""
    entries = []
    current_entry = []
    in_entry = False
    
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('@'):
            if current_entry:
                entries.append('\n'.join(current_entry))
            current_entry = [line]
            in_entry = True
        elif in_entry:
            current_entry.append(line)
            if line == '}':
                entries.append('\n'.join(current_entry))
                current_entry = []
                in_entry = False
    
    if current_entry:
        entries.append('\n'.join(current_entry))
    
    return entries


class TestBehavioralEquivalence:
    """Test suite for behavioral equivalence validation."""
    
    def test_csv_conversion_equivalence(self, tmp_path):
        """Test that CSV conversion produces equivalent output.
        
        Validates that the refactored CSVConverter produces the same
        BibTeX entries as the original csv_to_bibtex script.
        """
        # Create test CSV file
        csv_file = tmp_path / "test_input.csv"
        create_test_csv(SAMPLE_CSV_DATA, csv_file)
        
        # Run original script
        original_output_dir = tmp_path / "original"
        original_output_dir.mkdir()
        original_base = str(original_output_dir / "springer_results_raw")
        original_count, original_files = csv_to_bibtex(
            str(csv_file), 
            original_base, 
            entries_per_file=49
        )
        
        # Run refactored code
        refactored_output_dir = tmp_path / "refactored"
        refactored_output_dir.mkdir()
        converter = CSVConverter(entries_per_file=49)
        result = converter.convert(csv_file, refactored_output_dir, output_base_name="springer_results_raw")
        
        # Verify same number of entries processed
        assert result.entries_count == original_count, \
            f"Entry count mismatch: original={original_count}, refactored={result.entries_count}"
        
        # Verify same number of output files
        assert len(result.output_files) == len(original_files), \
            f"File count mismatch: original={len(original_files)}, refactored={len(result.output_files)}"
        
        # Compare content of each file
        for orig_file_path in original_files:
            orig_file = Path(orig_file_path)
            # Find corresponding refactored file
            refactored_file = refactored_output_dir / orig_file.name
            
            assert refactored_file.exists(), \
                f"Refactored file not found: {refactored_file}"
            
            # Read both files
            with open(orig_file, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            with open(refactored_file, 'r', encoding='utf-8') as f:
                refactored_content = f.read()
            
            # Extract and compare entries
            original_entries = extract_bibtex_entries(original_content)
            refactored_entries = extract_bibtex_entries(refactored_content)
            
            assert len(original_entries) == len(refactored_entries), \
                f"Entry count mismatch in {orig_file.name}: " \
                f"original={len(original_entries)}, refactored={len(refactored_entries)}"
            
            # Compare each entry (normalized)
            for i, (orig_entry, refact_entry) in enumerate(zip(original_entries, refactored_entries)):
                orig_normalized = normalize_bibtex_content(orig_entry)
                refact_normalized = normalize_bibtex_content(refact_entry)
                
                assert orig_normalized == refact_normalized, \
                    f"Entry {i} mismatch in {orig_file.name}:\n" \
                    f"Original:\n{orig_entry}\n\n" \
                    f"Refactored:\n{refact_entry}"
    
    def test_author_fixing_equivalence(self, tmp_path):
        """Test that author fixing produces equivalent output.
        
        Validates that the refactored AuthorFixer produces the same
        author name corrections as the original fix_bibtex_authors_claude script.
        """
        # Create a test BibTeX file with concatenated authors
        test_bibtex = """@inproceedings{Davey_2025_Large,
  title = {Large Language Model-Based Network Intrusion Detection},
  author = {Dhruv DaveyKayvan KarimHani Ragab HassenHadj Batatia},
  year = {2025},
  doi = {10.1007/978-981-96-1758-6_26},
  url = {https://link.springer.com/chapter/10.1007/978-981-96-1758-6_26},
  booktitle = {Proceedings of International Conference on Information Technology and Applications},
  publisher = {Springer}
}

@article{Yang_2025_Localized,
  title = {Localized large language model TCNNet 9B for Taiwanese networking and cybersecurity},
  author = {Jiun-Yi YangChia-Chun Wu},
  year = {2025},
  doi = {10.1038/s41598-025-90320-9},
  url = {https://link.springer.com/article/10.1038/s41598-025-90320-9},
  journal = {Scientific Reports},
  publisher = {Springer}
}"""
        
        input_file = tmp_path / "test_input.bib"
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(test_bibtex)
        
        # Run original script
        original_output = tmp_path / "original_fixed.bib"
        original_corrections, original_problematic, _ = process_bibtex_file(
            str(input_file),
            str(original_output)
        )
        
        # Run refactored code
        refactored_output = tmp_path / "refactored_fixed.bib"
        fixer = AuthorFixer()
        result = fixer.fix_file(input_file, refactored_output)
        
        # Verify same number of corrections
        assert result.entries_count == original_corrections, \
            f"Correction count mismatch: original={original_corrections}, refactored={result.entries_count}"
        
        # Read both output files
        with open(original_output, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        with open(refactored_output, 'r', encoding='utf-8') as f:
            refactored_content = f.read()
        
        # Extract and compare entries
        original_entries = extract_bibtex_entries(original_content)
        refactored_entries = extract_bibtex_entries(refactored_content)
        
        assert len(original_entries) == len(refactored_entries), \
            f"Entry count mismatch: original={len(original_entries)}, refactored={len(refactored_entries)}"
        
        # Compare each entry
        for i, (orig_entry, refact_entry) in enumerate(zip(original_entries, refactored_entries)):
            orig_normalized = normalize_bibtex_content(orig_entry)
            refact_normalized = normalize_bibtex_content(refact_entry)
            
            assert orig_normalized == refact_normalized, \
                f"Entry {i} mismatch:\n" \
                f"Original:\n{orig_entry}\n\n" \
                f"Refactored:\n{refact_entry}"
    
    def test_complete_pipeline_equivalence(self, tmp_path):
        """Test complete pipeline: CSV -> BibTeX -> Fixed BibTeX.
        
        Validates that running the complete conversion and fixing pipeline
        produces equivalent results between original and refactored code.
        """
        # Create test CSV file
        csv_file = tmp_path / "test_input.csv"
        create_test_csv(SAMPLE_CSV_DATA, csv_file)
        
        # === Original Pipeline ===
        original_output_dir = tmp_path / "original"
        original_output_dir.mkdir()
        
        # Step 1: Convert CSV to BibTeX
        original_base = str(original_output_dir / "springer_results_raw")
        _, original_files = csv_to_bibtex(
            str(csv_file),
            original_base,
            entries_per_file=49
        )
        
        # Step 2: Fix authors
        original_fixed_files = []
        for orig_file in original_files:
            orig_path = Path(orig_file)
            fixed_path = orig_path.parent / f"{orig_path.stem}_fixed{orig_path.suffix}"
            process_bibtex_file(str(orig_path), str(fixed_path))
            original_fixed_files.append(fixed_path)
        
        # === Refactored Pipeline ===
        refactored_output_dir = tmp_path / "refactored"
        refactored_output_dir.mkdir()
        
        # Step 1: Convert CSV to BibTeX
        converter = CSVConverter(entries_per_file=49)
        result = converter.convert(csv_file, refactored_output_dir)
        
        # Step 2: Fix authors
        fixer = AuthorFixer()
        refactored_fixed_files = []
        for bib_file in result.output_files:
            fixed_path = bib_file.parent / f"{bib_file.stem}_fixed{bib_file.suffix}"
            fixer.fix_file(bib_file, fixed_path)
            refactored_fixed_files.append(fixed_path)
        
        # === Compare Final Outputs ===
        assert len(original_fixed_files) == len(refactored_fixed_files), \
            f"File count mismatch: original={len(original_fixed_files)}, refactored={len(refactored_fixed_files)}"
        
        for orig_file, refact_file in zip(original_fixed_files, refactored_fixed_files):
            # Read both files
            with open(orig_file, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            with open(refact_file, 'r', encoding='utf-8') as f:
                refactored_content = f.read()
            
            # Extract and compare entries
            original_entries = extract_bibtex_entries(original_content)
            refactored_entries = extract_bibtex_entries(refactored_content)
            
            assert len(original_entries) == len(refactored_entries), \
                f"Entry count mismatch in {orig_file.name}: " \
                f"original={len(original_entries)}, refactored={len(refactored_entries)}"
            
            # Compare each entry
            for i, (orig_entry, refact_entry) in enumerate(zip(original_entries, refactored_entries)):
                orig_normalized = normalize_bibtex_content(orig_entry)
                refact_normalized = normalize_bibtex_content(refact_entry)
                
                assert orig_normalized == refact_normalized, \
                    f"Entry {i} mismatch in {orig_file.name}:\n" \
                    f"Original:\n{orig_entry}\n\n" \
                    f"Refactored:\n{refact_entry}"
    
    def test_edge_case_empty_csv(self, tmp_path):
        """Test that both implementations handle empty CSV files equivalently."""
        # Create empty CSV file (header only)
        csv_file = tmp_path / "empty.csv"
        create_test_csv([], csv_file)
        
        # Add header manually
        with open(csv_file, 'w', encoding='utf-8') as f:
            f.write('Item Title,Publication Title,Book Series Title,Journal Volume,Journal Issue,Item DOI,Authors,Publication Year,URL,Content Type\n')
        
        # Run original script
        original_output_dir = tmp_path / "original"
        original_output_dir.mkdir()
        original_base = str(original_output_dir / "springer_results_raw")
        original_count, original_files = csv_to_bibtex(
            str(csv_file),
            original_base,
            entries_per_file=49
        )
        
        # Run refactored code
        refactored_output_dir = tmp_path / "refactored"
        refactored_output_dir.mkdir()
        converter = CSVConverter(entries_per_file=49)
        result = converter.convert(csv_file, refactored_output_dir)
        
        # Both should produce 0 entries
        assert original_count == 0
        assert result.entries_count == 0
        assert len(original_files) == len(result.output_files)
    
    def test_compound_name_preservation(self, tmp_path):
        """Test that compound names are preserved identically.
        
        Tests that compound names like McDonald, O'Brien, and MacArthur
        are not incorrectly split when they appear in concatenated author strings.
        """
        # Create BibTeX with compound names in concatenated format
        # Note: lowercase-to-uppercase transitions trigger splitting
        test_bibtex = """@article{Test_2025_Compound,
  title = {Test Article with Compound Names},
  author = {John McDonaldMary O'BrienRobert MacArthurJane SmithDavid DeLucaPatrick McCarthyAnne O'Connor},
  year = {2025},
  journal = {Test Journal},
  publisher = {Springer}
}"""
        
        input_file = tmp_path / "compound_test.bib"
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(test_bibtex)
        
        # Run original script
        original_output = tmp_path / "original_compound_fixed.bib"
        process_bibtex_file(str(input_file), str(original_output))
        
        # Run refactored code
        refactored_output = tmp_path / "refactored_compound_fixed.bib"
        fixer = AuthorFixer()
        fixer.fix_file(input_file, refactored_output)
        
        # Read both outputs
        with open(original_output, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        with open(refactored_output, 'r', encoding='utf-8') as f:
            refactored_content = f.read()
        
        # Both should preserve compound names without splitting them
        for compound_name in ['McDonald', "O'Brien", 'MacArthur', 'DeLuca', 'McCarthy', "O'Connor"]:
            assert compound_name in original_content, f"{compound_name} not found in original output"
            assert compound_name in refactored_content, f"{compound_name} not found in refactored output"
        
        # Both should NOT have incorrectly split compound names
        # e.g., "Mc Donald" or "O' Brien" should not appear
        assert 'Mc Donald' not in original_content
        assert 'Mc Donald' not in refactored_content
        assert "O' Brien" not in original_content
        assert "O' Brien" not in refactored_content
        
        # Compare normalized content
        orig_normalized = normalize_bibtex_content(original_content)
        refact_normalized = normalize_bibtex_content(refactored_content)
        assert orig_normalized == refact_normalized


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
