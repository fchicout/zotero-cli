"""File handling utilities for CSV to BibTeX conversion pipeline."""

import csv
from pathlib import Path
from typing import List, Dict


class FileHandler:
    """Manages file operations for the conversion pipeline.
    
    Provides robust file I/O operations with proper error handling,
    path validation, and cross-platform compatibility using pathlib.
    """
    
    @staticmethod
    def read_csv(path: Path) -> List[Dict[str, str]]:
        """Read CSV file and return rows as list of dictionaries.
        
        Args:
            path: Path to the CSV file to read
            
        Returns:
            List of dictionaries, where each dict represents a CSV row
            with column headers as keys
            
        Raises:
            FileNotFoundError: If the file does not exist
            PermissionError: If the file cannot be read due to permissions
            ValueError: If the file is not a valid CSV format
        """
        # Validate file existence (Requirement 7.2)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")
        
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")
        
        try:
            rows = []
            with open(path, 'r', encoding='utf-8', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    rows.append(row)
            return rows
        except PermissionError as e:
            raise PermissionError(f"Permission denied reading file: {path}") from e
        except csv.Error as e:
            raise ValueError(f"Invalid CSV format in file {path}: {str(e)}") from e
        except UnicodeDecodeError as e:
            raise ValueError(f"File encoding error in {path}: {str(e)}") from e
    
    @staticmethod
    def write_bibtex(path: Path, content: str) -> None:
        """Write BibTeX content to file, creating directories if needed.
        
        Args:
            path: Path where the BibTeX file should be written
            content: BibTeX content as a string
            
        Raises:
            PermissionError: If the file cannot be written due to permissions
            OSError: If there are disk space or other OS-level issues
        """
        # Create necessary directories (Requirement 7.3)
        FileHandler.ensure_directory(path.parent)
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except PermissionError as e:
            raise PermissionError(
                f"Permission denied writing to file: {path}"
            ) from e
        except OSError as e:
            raise OSError(
                f"Error writing to file {path}: {str(e)}"
            ) from e
    
    @staticmethod
    def ensure_directory(path: Path) -> None:
        """Create directory and all parent directories if they don't exist.
        
        Args:
            path: Path to the directory to create
            
        Raises:
            PermissionError: If directories cannot be created due to permissions
            OSError: If there are other OS-level issues creating directories
        """
        try:
            # Create all parent directories as needed (Requirement 7.3)
            path.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise PermissionError(
                f"Permission denied creating directory: {path}"
            ) from e
        except OSError as e:
            raise OSError(
                f"Error creating directory {path}: {str(e)}"
            ) from e
    
    @staticmethod
    def validate_csv_file(path: Path) -> bool:
        """Validate that a file exists and appears to be a valid CSV.
        
        Performs basic validation:
        - File exists
        - File is readable
        - File has CSV extension
        - File can be parsed as CSV with headers
        
        Args:
            path: Path to the CSV file to validate
            
        Returns:
            True if the file appears to be a valid CSV, False otherwise
        """
        # Check file existence (Requirement 7.2)
        if not path.exists():
            return False
        
        if not path.is_file():
            return False
        
        # Check file extension
        if path.suffix.lower() not in ['.csv', '.txt']:
            return False
        
        # Try to read the file as CSV
        try:
            with open(path, 'r', encoding='utf-8', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                # Try to read first row to validate format
                first_row = next(reader, None)
                # Valid CSV should have at least one row with headers
                return first_row is not None and len(first_row) > 0
        except (csv.Error, UnicodeDecodeError, PermissionError):
            return False

    @staticmethod
    def ensure_directory_exists(path: str) -> None:
        """Create directory if it doesn't exist.
        
        Convenience wrapper around ensure_directory that accepts string paths.
        
        Args:
            path: Path to the directory as a string
            
        Raises:
            PermissionError: If directories cannot be created due to permissions
            OSError: If there are other OS-level issues creating directories
        """
        FileHandler.ensure_directory(Path(path))
    
    @staticmethod
    def generate_unique_filename(base_name: str, extension: str) -> str:
        """Generate unique filename with timestamp.
        
        Creates a filename in the format: base_name_YYYYMMDD_HHMMSS.extension
        
        Args:
            base_name: Base name for the file (without extension)
            extension: File extension (with or without leading dot)
            
        Returns:
            Unique filename string with timestamp
        """
        from datetime import datetime
        
        # Ensure extension has leading dot
        if not extension.startswith('.'):
            extension = f'.{extension}'
        
        # Generate timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        return f"{base_name}_{timestamp}{extension}"
    
    @staticmethod
    def validate_csv_structure(file_path: str, required_columns: List[str]) -> bool:
        """Validate CSV has required columns.
        
        Checks if a CSV file contains all the specified column headers.
        
        Args:
            file_path: Path to the CSV file as a string
            required_columns: List of column names that must be present
            
        Returns:
            True if all required columns are present, False otherwise
        """
        path = Path(file_path)
        
        # Check file exists
        if not path.exists() or not path.is_file():
            return False
        
        try:
            with open(path, 'r', encoding='utf-8', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Check if fieldnames exist
                if reader.fieldnames is None:
                    return False
                
                # Check if all required columns are present
                return all(col in reader.fieldnames for col in required_columns)
                
        except (csv.Error, UnicodeDecodeError, PermissionError):
            return False
    
    @staticmethod
    def file_exists(file_path: str) -> bool:
        """Check if a file exists at the given path.
        
        Args:
            file_path: Path to check as a string
            
        Returns:
            True if file exists, False otherwise
        """
        path = Path(file_path)
        return path.exists() and path.is_file()
