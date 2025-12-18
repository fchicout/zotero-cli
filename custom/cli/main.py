"""Command-line interface for CSV to BibTeX conversion.

This module provides a CLI for the conversion pipeline, supporting both
CSV conversion and optional author name fixing.
"""

import argparse
import sys
from pathlib import Path

from custom.core.csv_converter import CSVConverter
from custom.core.author_fixer import AuthorFixer


def main():
    """CLI entry point for CSV to BibTeX conversion pipeline.
    
    Parses command-line arguments and executes the conversion pipeline,
    optionally followed by author name fixing. Provides progress output
    and error reporting.
    
    Requirements: 2.1, 2.2, 2.3, 2.4
    """
    parser = argparse.ArgumentParser(
        description='Convert Springer CSV files to BibTeX format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic conversion
  python -m custom.cli.main --input data/input/SearchResults.csv
  
  # Conversion with author fixing
  python -m custom.cli.main --input data/input/SearchResults.csv --fix-authors
  
  # Custom output directory
  python -m custom.cli.main --input data/input/SearchResults.csv --output-dir output/bibtex
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Path to input Springer CSV file'
    )
    
    # Optional arguments
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/output',
        help='Output directory for BibTeX files (default: data/output)'
    )
    
    parser.add_argument(
        '--fix-authors',
        action='store_true',
        help='Apply author name fixing to separate concatenated names'
    )
    
    args = parser.parse_args()
    
    # Convert paths
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    
    # Validate input file exists
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    if not input_path.is_file():
        print(f"Error: Input path is not a file: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    # Execute conversion pipeline
    exit_code = execute_pipeline(input_path, output_dir, args.fix_authors)
    sys.exit(exit_code)


def execute_pipeline(
    input_path: Path,
    output_dir: Path,
    fix_authors: bool
) -> int:
    """Execute the conversion pipeline with progress reporting.
    
    Args:
        input_path: Path to input CSV file
        output_dir: Directory for output files
        fix_authors: Whether to apply author fixing
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    print(f"CSV to BibTeX Converter")
    print(f"=" * 60)
    print(f"Input file: {input_path}")
    print(f"Output directory: {output_dir}")
    print(f"Author fixing: {'enabled' if fix_authors else 'disabled'}")
    print()
    
    # Step 1: CSV to BibTeX conversion (Requirement 2.1)
    print("Step 1: Converting CSV to BibTeX...")
    converter = CSVConverter()
    
    try:
        result = converter.convert(input_path, output_dir)
    except Exception as e:
        print(f"Error during conversion: {e}", file=sys.stderr)
        return 1
    
    if not result.success:
        print("Conversion failed!", file=sys.stderr)
        for error in result.errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    
    # Report conversion results
    print(f"[OK] Converted {result.entries_count} entries")
    print(f"[OK] Created {len(result.output_files)} file(s):")
    for output_file in result.output_files:
        print(f"  - {output_file}")
    
    if result.errors:
        print(f"\nWarnings during conversion:")
        for error in result.errors:
            print(f"  - {error}")
    
    print()
    
    # Step 2: Author fixing (optional) (Requirement 2.3, 2.4)
    if fix_authors:
        print("Step 2: Fixing author names...")
        fixer = AuthorFixer()
        
        fixed_files = []
        total_corrections = 0
        all_errors = []
        
        for raw_file in result.output_files:
            # Generate output filename with _fixed suffix (Requirement 2.4)
            fixed_file = raw_file.with_stem(f"{raw_file.stem}_fixed")
            
            try:
                fix_result = fixer.fix_file(raw_file, fixed_file)
            except Exception as e:
                print(f"Error fixing {raw_file.name}: {e}", file=sys.stderr)
                all_errors.append(str(e))
                continue
            
            if fix_result.success:
                fixed_files.append(fixed_file)
                total_corrections += fix_result.entries_count
                all_errors.extend(fix_result.errors)
            else:
                print(f"Failed to fix {raw_file.name}", file=sys.stderr)
                all_errors.extend(fix_result.errors)
        
        if fixed_files:
            print(f"[OK] Fixed {total_corrections} author field(s)")
            print(f"[OK] Created {len(fixed_files)} fixed file(s):")
            for fixed_file in fixed_files:
                print(f"  - {fixed_file}")
        else:
            print("No files were successfully fixed", file=sys.stderr)
            return 1
        
        if all_errors:
            print(f"\nWarnings during author fixing:")
            for error in all_errors:
                print(f"  - {error}")
        
        print()
    
    # Success summary
    print("=" * 60)
    print("Conversion completed successfully!")
    
    if fix_authors:
        print(f"\nFinal output files are in: {output_dir}")
        print("Look for files with '_fixed' suffix for the corrected versions.")
    else:
        print(f"\nOutput files are in: {output_dir}")
        print("Tip: Use --fix-authors to automatically fix concatenated author names.")
    
    return 0


if __name__ == '__main__':
    main()
