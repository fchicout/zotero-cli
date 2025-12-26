"""Command-line interface for article extraction to Excel.

This module provides a CLI for extracting DOI, Title, and Abstract
from academic CSV files and generating Excel spreadsheets for
systematic review screening.
"""

import argparse
import sys
from pathlib import Path

from bibtools.core.article_extractor import (
    ArticleExtractor,
    ArticleExtractorError,
    FileNotFoundError as ExtractorFileNotFoundError,
    InvalidCSVError,
    EmptyDataError,
    DEFAULT_INPUT_PATH,
    DEFAULT_OUTPUT_PATH
)


def main():
    """CLI entry point for article extraction.
    
    Parses command-line arguments and executes the extraction pipeline,
    providing progress output and error reporting.
    
    Requirements: 6.1, 6.2, 6.5, 5.1, 5.2, 5.3, 5.5
    """
    parser = argparse.ArgumentParser(
        description='Extract DOI, Title, and Abstract from academic CSV to Excel',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic extraction with default paths
  python -m bibtools.cli.extract_articles
  
  # Custom input file
  python -m bibtools.cli.extract_articles --input bibtools/data/input/my_articles.csv
  
  # Custom input and output
  python -m bibtools.cli.extract_articles --input bibtools/data/input/articles.csv --output bibtools/data/output/screening.xlsx
  
  # Show help
  python -m bibtools.cli.extract_articles --help
        """
    )
    
    # Optional arguments
    parser.add_argument(
        '--input', '-i',
        type=str,
        default=DEFAULT_INPUT_PATH,
        help=f'Input CSV file path (default: {DEFAULT_INPUT_PATH})'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=DEFAULT_OUTPUT_PATH,
        help=f'Output Excel file path (default: {DEFAULT_OUTPUT_PATH})'
    )
    
    args = parser.parse_args()
    
    # Execute extraction
    exit_code = execute_extraction(args.input, args.output)
    sys.exit(exit_code)


def execute_extraction(input_path: str, output_path: str) -> int:
    """Execute the extraction pipeline with progress reporting.
    
    Args:
        input_path: Path to input CSV file
        output_path: Path for output Excel file
        
    Returns:
        Exit code (0 for success, non-zero for failure)
        
    Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.3, 6.4
    """
    # Display start message (Requirement 5.1)
    print("Article Extraction Tool")
    print("=" * 60)
    print(f"Input file:  {input_path}")
    print(f"Output file: {output_path}")
    print()
    
    # Create extractor
    extractor = ArticleExtractor(input_path, output_path)
    
    # Progress tracking variables
    total_records = 0
    
    def progress_callback(current: int, total: int, message: str):
        """Progress callback for reporting extraction progress.
        
        Requirements: 5.2, 5.5
        """
        nonlocal total_records
        if "Extracted" in message:
            # Extract record count from message
            import re
            match = re.search(r'(\d+)', message)
            if match:
                total_records = int(match.group(1))
        print(f"[{current:3d}%] {message}")
    
    try:
        # Execute extraction with progress tracking
        print("Starting extraction...")
        output_file = extractor.process(progress_callback=progress_callback)
        
        # Display success message (Requirement 5.3)
        print()
        print("=" * 60)
        print("✓ Extraction completed successfully!")
        print(f"✓ Processed {total_records} records")
        print(f"✓ Output file: {output_file}")
        print()
        print("You can now open this file in Excel or Google Sheets for screening.")
        print()
        
        return 0  # Success exit code (Requirement 6.3)
        
    except ExtractorFileNotFoundError as e:
        # Display detailed error message (Requirement 5.4, 4.2)
        print()
        print("=" * 60)
        print("✗ FILE NOT FOUND ERROR", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(file=sys.stderr)
        print(str(e), file=sys.stderr)
        print(file=sys.stderr)
        print("Tip: Use --help to see usage examples", file=sys.stderr)
        print()
        return 1  # Error exit code (Requirement 6.4)
        
    except InvalidCSVError as e:
        # Display detailed error message (Requirement 5.4, 1.5)
        print()
        print("=" * 60)
        print("✗ INVALID CSV FILE ERROR", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(file=sys.stderr)
        print(str(e), file=sys.stderr)
        print(file=sys.stderr)
        print("Tip: Ensure your CSV is exported from an academic database", file=sys.stderr)
        print("     with columns: DOI, Title, Abstract Note", file=sys.stderr)
        print()
        return 2  # Error exit code (Requirement 6.4)
        
    except EmptyDataError as e:
        # Display detailed error message (Requirement 5.4, 1.4)
        print()
        print("=" * 60)
        print("✗ EMPTY FILE ERROR", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(file=sys.stderr)
        print(str(e), file=sys.stderr)
        print(file=sys.stderr)
        print("Tip: Verify your CSV file contains article records", file=sys.stderr)
        print()
        return 3  # Error exit code (Requirement 6.4)
        
    except PermissionError as e:
        # Display detailed error message (Requirement 5.4, 3.5)
        print()
        print("=" * 60)
        print("✗ PERMISSION DENIED ERROR", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(file=sys.stderr)
        print(str(e), file=sys.stderr)
        print(file=sys.stderr)
        print("Tip: Check file permissions and ensure the output directory", file=sys.stderr)
        print("     is writable and the file is not open in another program", file=sys.stderr)
        print()
        return 4  # Error exit code (Requirement 6.4)
        
    except ArticleExtractorError as e:
        # Display detailed error message (Requirement 5.4)
        print()
        print("=" * 60)
        print("✗ EXTRACTION ERROR", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(file=sys.stderr)
        print(str(e), file=sys.stderr)
        print(file=sys.stderr)
        print("Tip: Check the error message above for specific details", file=sys.stderr)
        print()
        return 5  # Error exit code (Requirement 6.4)
        
    except Exception as e:
        # Display detailed error message (Requirement 5.4)
        print()
        print("=" * 60)
        print("✗ UNEXPECTED ERROR", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(file=sys.stderr)
        print(f"An unexpected error occurred: {type(e).__name__}", file=sys.stderr)
        print(f"{str(e)}", file=sys.stderr)
        print(file=sys.stderr)
        print("This may be a bug. Please report this error with the details above.", file=sys.stderr)
        print()
        return 99  # Unexpected error exit code (Requirement 6.4)


if __name__ == '__main__':
    main()
