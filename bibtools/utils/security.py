"""Security utilities for file upload and processing.

This module provides security functions for validating file uploads,
sanitizing paths, and preventing common security vulnerabilities.
"""

import os
import csv
from pathlib import Path
from typing import Optional, Tuple
from werkzeug.utils import secure_filename


# Security configuration
ALLOWED_EXTENSIONS = {'csv'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_FILENAME_LENGTH = 255


class SecurityError(Exception):
    """Base exception for security-related errors."""
    pass


class InvalidFileTypeError(SecurityError):
    """File type is not allowed."""
    pass


class FileSizeExceededError(SecurityError):
    """File size exceeds maximum allowed."""
    pass


class PathTraversalError(SecurityError):
    """Attempted path traversal attack detected."""
    pass


def validate_file_extension(filename: str) -> bool:
    """Validate that file has an allowed extension.
    
    Args:
        filename: Name of the file to validate
        
    Returns:
        True if file extension is allowed, False otherwise
    """
    if not filename or '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


def validate_csv_format(file_path: Path) -> Tuple[bool, Optional[str]]:
    """Validate that a file is a properly formatted CSV.
    
    Performs deep validation beyond just checking the extension:
    - Attempts to parse the file as CSV
    - Checks for valid headers
    - Validates encoding
    
    Args:
        file_path: Path to the file to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        If valid, returns (True, None)
        If invalid, returns (False, error_message)
    """
    if not file_path.exists():
        return False, "File does not exist"
    
    if not file_path.is_file():
        return False, "Path is not a file"
    
    # Check file size
    try:
        file_size = file_path.stat().st_size
        if file_size == 0:
            return False, "File is empty"
        
        if file_size > MAX_FILE_SIZE:
            return False, f"File size exceeds maximum allowed ({MAX_FILE_SIZE} bytes)"
    except OSError as e:
        return False, f"Cannot access file: {str(e)}"
    
    # Try to parse as CSV
    try:
        with open(file_path, 'r', encoding='utf-8', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Check for headers
            if reader.fieldnames is None or len(reader.fieldnames) == 0:
                return False, "CSV file has no headers"
            
            # Try to read first row to ensure it's parseable
            try:
                first_row = next(reader, None)
                if first_row is None:
                    return False, "CSV file has no data rows"
            except csv.Error as e:
                return False, f"CSV parsing error: {str(e)}"
            
        return True, None
        
    except UnicodeDecodeError:
        return False, "File encoding error - file must be UTF-8"
    except csv.Error as e:
        return False, f"Invalid CSV format: {str(e)}"
    except Exception as e:
        return False, f"Error validating file: {str(e)}"


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent security issues.
    
    Uses werkzeug's secure_filename and adds additional checks:
    - Removes path components
    - Limits filename length
    - Ensures filename is not empty after sanitization
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for filesystem operations
        
    Raises:
        SecurityError: If filename cannot be sanitized safely
    """
    if not filename:
        raise SecurityError("Filename cannot be empty")
    
    # Use werkzeug's secure_filename to remove dangerous characters
    safe_name = secure_filename(filename)
    
    if not safe_name:
        raise SecurityError("Filename contains only invalid characters")
    
    # Limit filename length
    if len(safe_name) > MAX_FILENAME_LENGTH:
        # Keep extension, truncate base name
        name_parts = safe_name.rsplit('.', 1)
        if len(name_parts) == 2:
            base, ext = name_parts
            max_base_length = MAX_FILENAME_LENGTH - len(ext) - 1
            safe_name = f"{base[:max_base_length]}.{ext}"
        else:
            safe_name = safe_name[:MAX_FILENAME_LENGTH]
    
    return safe_name


def validate_path_safety(path: Path, allowed_base: Path) -> bool:
    """Validate that a path is safe and within allowed directory.
    
    Prevents path traversal attacks by ensuring the resolved path
    is within the allowed base directory.
    
    Args:
        path: Path to validate
        allowed_base: Base directory that path must be within
        
    Returns:
        True if path is safe, False otherwise
    """
    try:
        # Resolve both paths to absolute paths
        resolved_path = path.resolve()
        resolved_base = allowed_base.resolve()
        
        # Check if path is within allowed base
        return resolved_path.is_relative_to(resolved_base)
    except (ValueError, RuntimeError):
        return False


def sanitize_path(path_str: str, base_dir: Path) -> Path:
    """Sanitize a path string and ensure it's within base directory.
    
    Args:
        path_str: Path string to sanitize
        base_dir: Base directory that path must be within
        
    Returns:
        Sanitized Path object
        
    Raises:
        PathTraversalError: If path attempts to escape base directory
        SecurityError: If path is invalid
    """
    if not path_str:
        raise SecurityError("Path cannot be empty")
    
    # Remove any path traversal attempts
    path_str = path_str.replace('..', '').replace('~', '')
    
    # Create path relative to base directory
    try:
        full_path = (base_dir / path_str).resolve()
    except (ValueError, RuntimeError) as e:
        raise SecurityError(f"Invalid path: {str(e)}")
    
    # Verify path is within base directory
    if not validate_path_safety(full_path, base_dir):
        raise PathTraversalError(
            f"Path '{path_str}' attempts to escape base directory"
        )
    
    return full_path


def check_file_size(file_path: Path, max_size: int = MAX_FILE_SIZE) -> bool:
    """Check if file size is within allowed limit.
    
    Args:
        file_path: Path to the file to check
        max_size: Maximum allowed file size in bytes
        
    Returns:
        True if file size is acceptable, False otherwise
    """
    try:
        file_size = file_path.stat().st_size
        return file_size <= max_size
    except OSError:
        return False


def cleanup_temp_file(file_path: Path, ignore_errors: bool = True) -> bool:
    """Safely delete a temporary file.
    
    Args:
        file_path: Path to the file to delete
        ignore_errors: If True, suppress exceptions and return False on error
        
    Returns:
        True if file was deleted successfully, False otherwise
        
    Raises:
        OSError: If ignore_errors is False and deletion fails
    """
    try:
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
            return True
        return False
    except OSError as e:
        if ignore_errors:
            return False
        raise


def cleanup_old_files(directory: Path, max_age_seconds: int = 3600) -> int:
    """Clean up old temporary files from a directory.
    
    Removes files older than the specified age. Useful for periodic
    cleanup of temporary upload directories.
    
    Args:
        directory: Directory to clean up
        max_age_seconds: Maximum age of files to keep (default: 1 hour)
        
    Returns:
        Number of files deleted
    """
    import time
    
    if not directory.exists() or not directory.is_dir():
        return 0
    
    deleted_count = 0
    current_time = time.time()
    
    try:
        for file_path in directory.iterdir():
            if not file_path.is_file():
                continue
            
            try:
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    file_path.unlink()
                    deleted_count += 1
            except OSError:
                # Skip files we can't access
                continue
    except OSError:
        # If we can't read directory, return count so far
        pass
    
    return deleted_count
