"""Article data extraction from CSV to Excel.

This module provides functionality to extract DOI, Title, and Abstract
from academic CSV files (e.g., Springer) and generate Excel spreadsheets
formatted for systematic review screening.
"""

import csv
import re
from pathlib import Path
from typing import List, Dict, Optional, Callable
from openpyxl import Workbook


# Default paths configuration
DEFAULT_INPUT_PATH = "bibtools/data/input/z_raw_springer.csv"
DEFAULT_OUTPUT_PATH = "bibtools/data/output/screening_data.xlsx"

# Web interface configuration (imported from security module)
UPLOAD_FOLDER = "bibtools/web/static/uploads"
try:
    from bibtools.utils.security import MAX_FILE_SIZE as MAX_UPLOAD_SIZE
except ImportError:
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB fallback


class ArticleExtractorError(Exception):
    """Base exception for extractor errors."""
    pass


class FileNotFoundError(ArticleExtractorError):
    """Input file not found.
    
    Raised when the specified input file does not exist or is not accessible.
    """
    pass


class InvalidCSVError(ArticleExtractorError):
    """CSV structure is invalid.
    
    Raised when the CSV file is malformed, missing required columns,
    or cannot be parsed correctly.
    """
    pass


class EmptyDataError(ArticleExtractorError):
    """No data to process.
    
    Raised when the CSV file contains no data rows (only headers or empty).
    """
    pass


class PermissionError(ArticleExtractorError):
    """Permission denied for file operation.
    
    Raised when the system cannot read the input file or write to the
    output location due to insufficient permissions.
    """
    pass


class ArticleExtractor:
    """Extracts DOI, Title, and Abstract from academic CSV files.
    
    This class handles reading CSV files containing academic article metadata,
    extracting specific columns (DOI, Title, Abstract Note), and writing the
    results to Excel format for systematic review screening.
    
    Attributes:
        input_path: Path to the input CSV file
        output_path: Path where the Excel file will be created
    """
    
    # DOI regex pattern - matches common DOI formats
    DOI_PATTERN = re.compile(
        r'(?:doi[:\s]+)?'  # Optional "doi:" or "DOI:" prefix
        r'(10\.\d{4,}/[^\s,;]+)',  # DOI format: 10.xxxx/...
        re.IGNORECASE
    )
    
    def __init__(self, input_path: str, output_path: str):
        """Initialize extractor with input and output paths.
        
        Args:
            input_path: Path to the input CSV file
            output_path: Path for the output Excel file
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
    
    def validate_input(self) -> bool:
        """Validate that input file exists and is readable.
        
        Returns:
            True if file exists and is readable, False otherwise
            
        Raises:
            FileNotFoundError: If the input file does not exist
            PermissionError: If the file exists but cannot be read
        """
        if not self.input_path.exists():
            raise FileNotFoundError(
                f"The input file could not be found at: {self.input_path}\n"
                f"Please check that:\n"
                f"  - The file path is correct\n"
                f"  - The file has not been moved or deleted\n"
                f"  - You have permission to access this location"
            )
        
        if not self.input_path.is_file():
            raise FileNotFoundError(
                f"The specified path is not a file: {self.input_path}\n"
                f"Please provide a path to a CSV file, not a directory."
            )
        
        # Check if file is readable
        try:
            with open(self.input_path, 'r', encoding='utf-8') as f:
                f.read(1)  # Try to read one character
        except IOError as e:
            raise PermissionError(
                f"Cannot read the input file: {self.input_path}\n"
                f"Error: {str(e)}\n"
                f"Please check that you have read permission for this file."
            )
        
        return True
    
    def _extract_doi_from_extra(self, extra_field: str) -> str:
        """Extract DOI from the Extra field using regex.
        
        Many Springer exports place DOIs in the "Extra" field with formats like:
        - "DOI: 10.1007/978-3-031-89363-6_16"
        - "doi:10.1007/..."
        - "10.1007/..." (direct)
        
        Args:
            extra_field: Content of the Extra field
            
        Returns:
            Extracted DOI string, or empty string if not found
        """
        if not extra_field:
            return ''
        
        match = self.DOI_PATTERN.search(extra_field)
        if match:
            return match.group(1).strip()
        
        return ''
    
    def extract_data(self) -> List[Dict[str, str]]:
        """Extract DOI, Title, and Abstract Note from CSV.
        
        Reads the CSV file and extracts the three required columns.
        Missing fields are represented as empty strings.
        
        Returns:
            List of dictionaries with keys: 'DOI', 'Title', 'Abstract'
            
        Raises:
            InvalidCSVError: If CSV is malformed or missing required columns
            EmptyDataError: If CSV contains no data rows
        """
        try:
            with open(self.input_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Validate required columns exist
                if reader.fieldnames is None:
                    raise InvalidCSVError(
                        "The CSV file appears to be empty or has no header row.\n"
                        "Please ensure your CSV file:\n"
                        "  - Contains a header row with column names\n"
                        "  - Is not empty\n"
                        "  - Is properly formatted"
                    )
                
                # Check for required columns (DOI can be in Extra field)
                required_columns = ['Title', 'Abstract Note']
                missing_columns = [
                    col for col in required_columns 
                    if col not in reader.fieldnames
                ]
                
                if missing_columns:
                    available_columns = ', '.join(reader.fieldnames[:5])
                    if len(reader.fieldnames) > 5:
                        available_columns += ', ...'
                    
                    raise InvalidCSVError(
                        f"The CSV file is missing required columns: {', '.join(missing_columns)}\n"
                        f"Required columns: Title, Abstract Note (DOI or Extra)\n"
                        f"Available columns: {available_columns}\n\n"
                        f"Please ensure your CSV file is exported from an academic database "
                        f"(Springer, IEEE, etc.) with the correct column names."
                    )
                
                # Check if we have DOI or Extra field
                has_doi_field = 'DOI' in reader.fieldnames
                has_extra_field = 'Extra' in reader.fieldnames
                
                if not has_doi_field and not has_extra_field:
                    raise InvalidCSVError(
                        "The CSV file must have either a 'DOI' or 'Extra' column.\n"
                        "Neither column was found in the file."
                    )
                
                # Extract data
                data = []
                row_number = 1  # Start at 1 (header is row 0)
                
                try:
                    for row in reader:
                        row_number += 1
                        
                        # Extract DOI - try DOI field first, then Extra field
                        doi = row.get('DOI', '').strip()
                        
                        if not doi and has_extra_field:
                            # Try to extract DOI from Extra field
                            extra_content = row.get('Extra', '')
                            doi = self._extract_doi_from_extra(extra_content)
                        
                        data.append({
                            'DOI': doi,
                            'Title': row.get('Title', '').strip(),
                            'Abstract': row.get('Abstract Note', '').strip()
                        })
                except csv.Error as e:
                    raise InvalidCSVError(
                        f"Error parsing CSV at row {row_number}: {str(e)}\n"
                        f"The file may be corrupted or improperly formatted.\n"
                        f"Please check the file and try again."
                    )
                
                if not data:
                    raise EmptyDataError(
                        "The CSV file contains no data rows (only headers).\n"
                        "Please ensure your CSV file:\n"
                        "  - Contains at least one article record\n"
                        "  - Is not just a header row\n"
                        "  - Has been exported correctly from the database"
                    )
                
                return data
                
        except csv.Error as e:
            raise InvalidCSVError(
                f"Failed to parse the CSV file: {str(e)}\n"
                f"The file may be:\n"
                f"  - Corrupted or incomplete\n"
                f"  - Not a valid CSV format\n"
                f"  - Using an unsupported delimiter\n\n"
                f"Please verify the file is a valid CSV and try again."
            )
        except UnicodeDecodeError as e:
            raise InvalidCSVError(
                f"Cannot read the file due to encoding issues: {str(e)}\n"
                f"The file may be:\n"
                f"  - Saved in an incompatible encoding\n"
                f"  - Corrupted during transfer\n"
                f"  - Not a text-based CSV file\n\n"
                f"Try re-exporting the CSV file with UTF-8 encoding."
            )
    
    def write_excel(self, data: List[Dict[str, str]]) -> str:
        """Write extracted data to Excel file.
        
        Creates an Excel workbook with a header row and data rows.
        Creates parent directories if they don't exist.
        
        Args:
            data: List of dictionaries containing DOI, Title, and Abstract
            
        Returns:
            Path to the created Excel file as a string
            
        Raises:
            PermissionError: If unable to write to output path
        """
        # Ensure output directory exists
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise PermissionError(
                f"Cannot create output directory: {self.output_path.parent}\n"
                f"Error: {str(e)}\n"
                f"Please check that:\n"
                f"  - You have write permission for this location\n"
                f"  - The path is valid and accessible\n"
                f"  - There is sufficient disk space"
            )
        
        # Create workbook and active sheet
        wb = Workbook()
        ws = wb.active
        ws.title = "Screening Data"
        
        # Write header row
        headers = ['DOI', 'Title', 'Abstract']
        ws.append(headers)
        
        # Write data rows
        for row_data in data:
            ws.append([
                row_data['DOI'],
                row_data['Title'],
                row_data['Abstract']
            ])
        
        # Save workbook
        try:
            wb.save(self.output_path)
        except IOError as e:
            raise PermissionError(
                f"Cannot write to output file: {self.output_path}\n"
                f"Error: {str(e)}\n"
                f"Please check that:\n"
                f"  - You have write permission for this location\n"
                f"  - The file is not open in another program\n"
                f"  - There is sufficient disk space\n"
                f"  - The path is valid and accessible"
            )
        except Exception as e:
            raise ArticleExtractorError(
                f"Failed to create Excel file: {str(e)}\n"
                f"An unexpected error occurred while writing the output file."
            )
        
        return str(self.output_path)
    
    def process(self, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> str:
        """Main processing method that orchestrates extraction and writing.
        
        Validates input, extracts data, writes Excel file, and reports progress.
        
        Args:
            progress_callback: Optional callback function for progress updates.
                             Called with (current, total, message) parameters.
                             
        Returns:
            Path to the output Excel file as a string
            
        Raises:
            FileNotFoundError: If input file doesn't exist
            InvalidCSVError: If CSV is malformed
            EmptyDataError: If CSV has no data
            PermissionError: If cannot write output file
        """
        # Validate input file
        self.validate_input()
        
        if progress_callback:
            progress_callback(0, 100, "Starting extraction...")
        
        # Extract data from CSV
        data = self.extract_data()
        total_records = len(data)
        
        if progress_callback:
            progress_callback(50, 100, f"Extracted {total_records} records")
        
        # Write to Excel
        output_file = self.write_excel(data)
        
        if progress_callback:
            progress_callback(100, 100, f"Completed: {output_file}")
        
        return output_file
