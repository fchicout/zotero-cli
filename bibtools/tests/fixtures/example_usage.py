#!/usr/bin/env python3
"""
Example usage of the custom CSV-to-BibTeX conversion tools.

This demonstrates how to use the refactored code and how warning messages
are displayed to users when author fixing might need manual review.
"""

from pathlib import Path
from bibtools.core.csv_converter import CSVConverter
from bibtools.core.author_fixer import AuthorFixer


def example_csv_conversion():
    """Example: Convert CSV to BibTeX"""
    print("=" * 60)
    print("Example 1: CSV to BibTeX Conversion")
    print("=" * 60)
    
    # Setup paths
    csv_file = Path("tests_custom/fixtures/sample_springer.csv")
    output_dir = Path("bibtools/data/output")
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Convert CSV to BibTeX
    converter = CSVConverter(entries_per_file=49)
    result = converter.convert(csv_file, output_dir)
    
    # Display results
    print(f"\nConversion {'successful' if result.success else 'failed'}!")
    print(f"Entries processed: {result.entries_count}")
    print(f"Output files created: {len(result.output_files)}")
    for file in result.output_files:
        print(f"  - {file}")
    
    if result.errors:
        print(f"\nWarnings/Errors:")
        for error in result.errors:
            print(f"  ⚠ {error}")
    
    return result.output_files


def example_author_fixing(bibtex_files):
    """Example: Fix concatenated author names"""
    print("\n" + "=" * 60)
    print("Example 2: Author Name Fixing")
    print("=" * 60)
    
    fixer = AuthorFixer()
    
    for bib_file in bibtex_files:
        print(f"\nProcessing: {bib_file.name}")
        
        # Fix authors (output will have _fixed suffix)
        output_file = bib_file.parent / f"{bib_file.stem}_fixed{bib_file.suffix}"
        result = fixer.fix_file(bib_file, output_file)
        
        # Display results
        print(f"  Corrections made: {result.entries_count}")
        print(f"  Output: {output_file.name}")
        
        # IMPORTANT: Display warnings if any
        if result.errors:
            print(f"\n  ⚠ WARNINGS - Manual review recommended:")
            for error in result.errors:
                print(f"    • {error}")
            print(f"\n  Please review the flagged entries in: {output_file}")


def example_with_problematic_authors():
    """Example: Demonstrate warning messages for problematic author strings"""
    print("\n" + "=" * 60)
    print("Example 3: Warning Messages for Problematic Authors")
    print("=" * 60)
    
    # Create a test file with a problematic author string
    test_content = """@article{Test_2025_Example,
  title = {Test Article with Many Concatenated Authors},
  author = {AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz},
  year = {2025},
  journal = {Test Journal}
}"""
    
    test_file = Path("bibtools/data/temp/test_problematic.bib")
    test_file.parent.mkdir(exist_ok=True, parents=True)
    test_file.write_text(test_content, encoding='utf-8')
    
    # Fix the file
    fixer = AuthorFixer()
    output_file = test_file.parent / f"{test_file.stem}_fixed{test_file.suffix}"
    result = fixer.fix_file(test_file, output_file)
    
    print(f"\nProcessed: {test_file.name}")
    print(f"Corrections made: {result.entries_count}")
    
    # This will trigger a warning because it results in >20 authors
    if result.errors:
        print(f"\n⚠ WARNING MESSAGES:")
        print("-" * 60)
        for error in result.errors:
            print(f"  {error}")
        print("-" * 60)
        print(f"\nThe author fixing heuristic may have split names incorrectly.")
        print(f"Please manually review: {output_file}")
        print(f"\nThis happens when:")
        print(f"  • Author names are in an unusual format")
        print(f"  • The CSV data has formatting issues")
        print(f"  • Names contain many lowercase-to-uppercase transitions")
    
    # Cleanup
    test_file.unlink()
    output_file.unlink()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CSV-to-BibTeX Conversion Tool - Usage Examples")
    print("=" * 60)
    
    # Example 1: Normal conversion
    bibtex_files = example_csv_conversion()
    
    # Example 2: Author fixing
    example_author_fixing(bibtex_files)
    
    # Example 3: Warning messages
    example_with_problematic_authors()
    
    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)
