"""Command-line interface for custom tools.

This module provides a unified CLI for multiple tools including:
- CSV to BibTeX conversion
- Article extraction to Excel
"""

import argparse
import sys
from pathlib import Path

from bibtools.core.csv_converter import CSVConverter
from bibtools.core.author_fixer import AuthorFixer


def main():
    """Main CLI entry point with subcommands.
    
    Provides access to multiple tools through subcommands.
    
    Requirements: 6.1
    """
    parser = argparse.ArgumentParser(
        description='Custom tools for academic data processing',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
        required=True
    )
    
    # Subcommand: convert (CSV to BibTeX)
    setup_convert_parser(subparsers)
    
    # Subcommand: extract-articles (CSV to Excel)
    setup_extract_parser(subparsers)
    
    args = parser.parse_args()
    
    # Route to appropriate command handler
    if args.command == 'convert':
        exit_code = handle_convert_command(args)
    elif args.command == 'extract-articles':
        exit_code = handle_extract_command(args)
    else:
        parser.print_help()
        exit_code = 1
    
    sys.exit(exit_code)


def setup_convert_parser(subparsers):
    """Set up the 'convert' subcommand parser.
    
    Requirements: 2.1, 2.2, 2.3, 2.4
    """
    parser = subparsers.add_parser(
        'convert',
        help='Convert Springer CSV files to BibTeX format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic conversion
  python -m custom.cli.main convert --input data/input/SearchResults.csv
  
  # Conversion with author fixing
  python -m custom.cli.main convert --input data/input/SearchResults.csv --fix-authors
  
  # Custom output directory
  python -m custom.cli.main convert --input data/input/SearchResults.csv --output-dir output/bibtex
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


def setup_extract_parser(subparsers):
    """Set up the 'extract-articles' subcommand parser.
    
    Requirements: 6.1, 6.2, 6.5
    """
    parser = subparsers.add_parser(
        'extract-articles',
        help='Extract DOI, Title, and Abstract from academic CSV to Excel',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic extraction with default paths
  python -m custom.cli.main extract-articles
  
  # Custom input file
  python -m custom.cli.main extract-articles --input data/input/my_articles.csv
  
  # Custom input and output
  python -m custom.cli.main extract-articles --input data/input/articles.csv --output results/screening.xlsx
        """
    )
    
    # Optional arguments
    parser.add_argument(
        '--input', '-i',
        type=str,
        default='data/input/z_raw_springer.csv',
        help='Input CSV file path (default: data/input/z_raw_springer.csv)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='data/output/screening_data.xlsx',
        help='Output Excel file path (default: data/output/screening_data.xlsx)'
    )


def handle_convert_command(args):
    """Handle the 'convert' subcommand.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, 1 for failure)
        
    Requirements: 2.1, 2.2, 2.3, 2.4
    """
    # Convert paths
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    
    # Validate input file exists
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1
    
    if not input_path.is_file():
        print(f"Error: Input path is not a file: {input_path}", file=sys.stderr)
        return 1
    
    # Execute conversion pipeline
    return execute_pipeline(input_path, output_dir, args.fix_authors)


def handle_extract_command(args):
    """Handle the 'extract-articles' subcommand.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
        
    Requirements: 6.1
    """
    # Import here to avoid circular dependencies
    from bibtools.cli.extract_articles import execute_extraction
    
    # Execute extraction
    return execute_extraction(args.input, args.output)


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
        result = converter.convert(input_path, output_dir, output_base_name="springer_results_raw")
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
