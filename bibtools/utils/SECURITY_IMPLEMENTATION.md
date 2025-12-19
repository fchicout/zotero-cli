# Security Implementation Summary

This document describes the security measures implemented for the CSV to Excel article extraction feature.

## Overview

Comprehensive security measures have been implemented to protect against common web application vulnerabilities, particularly for file upload and processing operations.

## Security Measures Implemented

### 1. File Upload Validation (CSV Format Check)

**Location**: `custom/utils/security.py`

- **Extension Validation**: `validate_file_extension()` ensures only CSV files are accepted
- **Deep Format Validation**: `validate_csv_format()` performs comprehensive checks:
  - Verifies file is parseable as CSV
  - Checks for valid headers
  - Validates file encoding (UTF-8)
  - Ensures file is not empty
  - Confirms file has data rows

**Implementation in Web App**: `custom/web/app.py` - `/extract-articles` endpoint
- Files are validated before processing
- Invalid files are rejected with descriptive error messages
- Multiple validation layers ensure only legitimate CSV files are processed

### 2. Path Sanitization (Directory Traversal Prevention)

**Location**: `custom/utils/security.py`

- **Filename Sanitization**: `sanitize_filename()` function:
  - Uses werkzeug's `secure_filename()` as base
  - Removes path components (/, \, ..)
  - Strips dangerous characters
  - Limits filename length to 255 characters
  - Ensures filename is not empty after sanitization

- **Path Safety Validation**: `validate_path_safety()` function:
  - Resolves paths to absolute paths
  - Verifies resolved path is within allowed base directory
  - Prevents path traversal attacks (../, ~, etc.)

- **Path Sanitization**: `sanitize_path()` function:
  - Removes traversal attempts (.., ~)
  - Validates final path is within base directory
  - Raises `PathTraversalError` if escape attempt detected

**Implementation in Web App**: All file operations use sanitized paths
- Upload filenames are sanitized before saving
- Download paths are validated before serving files
- Cleanup operations verify paths are within allowed directories

### 3. File Size Limits

**Location**: `custom/utils/security.py` and `custom/web/app.py`

- **Global Configuration**: `MAX_FILE_SIZE = 50MB` for article extraction
- **Flask Configuration**: `MAX_CONTENT_LENGTH` set to enforce limits
- **Endpoint-Specific Limits**:
  - Article extraction: 50MB limit
  - Convert endpoint: 16MB limit (backward compatibility)
- **Size Checking**: `check_file_size()` function validates file sizes
- **Error Handling**: Files exceeding limits return 413 status code with clear error message

### 4. Temporary File Cleanup

**Location**: `custom/utils/security.py` and `custom/web/app.py`

- **Immediate Cleanup**: `cleanup_temp_file()` function:
  - Safely deletes temporary files after processing
  - Handles errors gracefully
  - Used in all upload/processing workflows

- **Periodic Cleanup**: `cleanup_old_files()` function:
  - Removes files older than specified age (default: 1 hour)
  - Runs on application startup
  - Can be triggered via `/cleanup-old-files` endpoint
  - Cleans both upload and output directories

- **Error Recovery**: Cleanup occurs even when processing fails
  - Try-finally blocks ensure cleanup
  - Files are removed after successful download
  - Orphaned files are cleaned up periodically

## Security Functions Reference

### File Validation
- `validate_file_extension(filename: str) -> bool`
- `validate_csv_format(file_path: Path) -> Tuple[bool, Optional[str]]`

### Path Security
- `sanitize_filename(filename: str) -> str`
- `validate_path_safety(path: Path, allowed_base: Path) -> bool`
- `sanitize_path(path_str: str, base_dir: Path) -> Path`

### File Management
- `check_file_size(file_path: Path, max_size: int) -> bool`
- `cleanup_temp_file(file_path: Path, ignore_errors: bool) -> bool`
- `cleanup_old_files(directory: Path, max_age_seconds: int) -> int`

## Exception Classes

- `SecurityError`: Base exception for security-related errors
- `InvalidFileTypeError`: File type is not allowed
- `FileSizeExceededError`: File size exceeds maximum allowed
- `PathTraversalError`: Attempted path traversal attack detected

## Testing

Comprehensive test suite in `tests_custom/test_security.py`:
- 26 tests covering all security functions
- Tests for valid and invalid inputs
- Tests for attack scenarios (path traversal, oversized files, etc.)
- Integration tests for complete validation workflows

All tests pass successfully.

## Configuration

### Constants (in `custom/utils/security.py`)
```python
ALLOWED_EXTENSIONS = {'csv'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_FILENAME_LENGTH = 255
```

### Web App Configuration (in `custom/web/app.py`)
```python
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE  # 50MB
CLEANUP_INTERVAL_SECONDS = 3600  # 1 hour
TEMP_FILE_MAX_AGE_SECONDS = 3600  # 1 hour
```

## Usage Example

```python
from custom.utils.security import (
    validate_file_extension,
    sanitize_filename,
    validate_csv_format,
    check_file_size,
    cleanup_temp_file
)

# Validate file upload
if not validate_file_extension(uploaded_file.filename):
    return error("Invalid file type")

# Sanitize filename
safe_name = sanitize_filename(uploaded_file.filename)

# Save file
file_path = upload_dir / safe_name
uploaded_file.save(file_path)

# Validate file size
if not check_file_size(file_path):
    cleanup_temp_file(file_path)
    return error("File too large")

# Validate CSV format
is_valid, error_msg = validate_csv_format(file_path)
if not is_valid:
    cleanup_temp_file(file_path)
    return error(error_msg)

# Process file...

# Cleanup
cleanup_temp_file(file_path)
```

## Security Best Practices Followed

1. **Defense in Depth**: Multiple layers of validation
2. **Fail Secure**: Reject by default, allow only validated inputs
3. **Input Validation**: All user inputs are validated and sanitized
4. **Error Handling**: Graceful error handling with informative messages
5. **Resource Management**: Automatic cleanup prevents resource exhaustion
6. **Least Privilege**: Files are only accessible within designated directories
7. **Secure Defaults**: Conservative limits and strict validation by default

## Compliance with Requirements

This implementation satisfies Requirement 7.2:
- ✅ File upload validation (CSV format check)
- ✅ Path sanitization to prevent directory traversal
- ✅ File size limits for web uploads
- ✅ Temporary file cleanup

## Future Enhancements

Potential improvements for future versions:
- Rate limiting for upload endpoints
- Virus scanning integration
- Content-based file type detection (magic numbers)
- Audit logging for security events
- CSRF token validation
- File encryption at rest
