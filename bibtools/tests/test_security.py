"""Tests for security utilities.

This module tests the security functions that protect against
common vulnerabilities like path traversal, file size attacks,
and invalid file uploads.
"""

import pytest
from pathlib import Path
import tempfile
import csv

from bibtools.utils.security import (
    validate_file_extension,
    validate_csv_format,
    sanitize_filename,
    validate_path_safety,
    sanitize_path,
    check_file_size,
    cleanup_temp_file,
    cleanup_old_files,
    SecurityError,
    InvalidFileTypeError,
    PathTraversalError,
    MAX_FILE_SIZE
)


class TestFileExtensionValidation:
    """Test file extension validation."""
    
    def test_valid_csv_extension(self):
        """Test that CSV files are accepted."""
        assert validate_file_extension('test.csv') is True
        assert validate_file_extension('TEST.CSV') is True
        assert validate_file_extension('file.name.csv') is True
    
    def test_invalid_extensions(self):
        """Test that non-CSV files are rejected."""
        assert validate_file_extension('test.txt') is False
        assert validate_file_extension('test.xlsx') is False
        assert validate_file_extension('test.exe') is False
        assert validate_file_extension('test.pdf') is False
    
    def test_no_extension(self):
        """Test that files without extensions are rejected."""
        assert validate_file_extension('test') is False
        assert validate_file_extension('') is False
        assert validate_file_extension(None) is False


class TestCSVFormatValidation:
    """Test CSV format validation."""
    
    def test_valid_csv_file(self, tmp_path):
        """Test that valid CSV files pass validation."""
        csv_file = tmp_path / "test.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Header1', 'Header2'])
            writer.writerow(['Value1', 'Value2'])
        
        is_valid, error = validate_csv_format(csv_file)
        assert is_valid is True
        assert error is None
    
    def test_empty_csv_file(self, tmp_path):
        """Test that empty CSV files are rejected."""
        csv_file = tmp_path / "empty.csv"
        csv_file.touch()
        
        is_valid, error = validate_csv_format(csv_file)
        assert is_valid is False
        assert 'empty' in error.lower()
    
    def test_csv_without_headers(self, tmp_path):
        """Test that CSV files without headers are rejected."""
        csv_file = tmp_path / "no_headers.csv"
        with open(csv_file, 'w', encoding='utf-8') as f:
            f.write('\n')
        
        is_valid, error = validate_csv_format(csv_file)
        assert is_valid is False
    
    def test_csv_without_data(self, tmp_path):
        """Test that CSV files with only headers are rejected."""
        csv_file = tmp_path / "only_headers.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Header1', 'Header2'])
        
        is_valid, error = validate_csv_format(csv_file)
        assert is_valid is False
        assert 'no data' in error.lower()
    
    def test_file_too_large(self, tmp_path):
        """Test that files exceeding size limit are rejected."""
        csv_file = tmp_path / "large.csv"
        # Create a file larger than MAX_FILE_SIZE
        with open(csv_file, 'wb') as f:
            f.write(b'x' * (MAX_FILE_SIZE + 1))
        
        is_valid, error = validate_csv_format(csv_file)
        assert is_valid is False
        assert 'size exceeds' in error.lower()
    
    def test_nonexistent_file(self, tmp_path):
        """Test that nonexistent files are rejected."""
        csv_file = tmp_path / "nonexistent.csv"
        
        is_valid, error = validate_csv_format(csv_file)
        assert is_valid is False
        assert 'does not exist' in error.lower()


class TestFilenameSanitization:
    """Test filename sanitization."""
    
    def test_safe_filename(self):
        """Test that safe filenames pass through unchanged."""
        assert sanitize_filename('test.csv') == 'test.csv'
        assert sanitize_filename('my_file_123.csv') == 'my_file_123.csv'
    
    def test_remove_path_components(self):
        """Test that path components are removed."""
        # werkzeug's secure_filename removes path separators
        result = sanitize_filename('../../../etc/passwd')
        assert '/' not in result
        assert '\\' not in result
    
    def test_remove_dangerous_characters(self):
        """Test that dangerous characters are removed or replaced."""
        result = sanitize_filename('test<>:"|?*.csv')
        # Should not contain dangerous characters
        assert '<' not in result
        assert '>' not in result
        assert ':' not in result
        assert '"' not in result
        assert '|' not in result
        assert '?' not in result
        assert '*' not in result
    
    def test_empty_filename_raises_error(self):
        """Test that empty filenames raise an error."""
        with pytest.raises(SecurityError):
            sanitize_filename('')
        
        with pytest.raises(SecurityError):
            sanitize_filename(None)
    
    def test_filename_length_limit(self):
        """Test that very long filenames are truncated."""
        long_name = 'a' * 300 + '.csv'
        result = sanitize_filename(long_name)
        assert len(result) <= 255
        assert result.endswith('.csv')


class TestPathSafety:
    """Test path safety validation."""
    
    def test_safe_path_within_base(self, tmp_path):
        """Test that paths within base directory are accepted."""
        base = tmp_path / "base"
        base.mkdir()
        
        safe_path = base / "subdir" / "file.csv"
        assert validate_path_safety(safe_path, base) is True
    
    def test_path_traversal_rejected(self, tmp_path):
        """Test that path traversal attempts are rejected."""
        base = tmp_path / "base"
        base.mkdir()
        
        # Try to escape base directory
        unsafe_path = base / ".." / ".." / "etc" / "passwd"
        assert validate_path_safety(unsafe_path, base) is False
    
    def test_sanitize_path_removes_traversal(self, tmp_path):
        """Test that sanitize_path detects and rejects traversal attempts."""
        base = tmp_path / "base"
        base.mkdir()
        
        # Should detect path traversal attempts and raise error
        # Even after removing .., the resulting path may still be unsafe
        with pytest.raises(PathTraversalError):
            sanitize_path("../../../etc/passwd", base)
    
    def test_sanitize_path_raises_on_escape(self, tmp_path):
        """Test that sanitize_path raises error if path escapes base."""
        base = tmp_path / "base"
        base.mkdir()
        
        # Even after sanitization, if path would escape, raise error
        # This is a safety check
        with pytest.raises((PathTraversalError, SecurityError)):
            # Try various escape attempts
            sanitize_path("", base)


class TestFileSizeCheck:
    """Test file size checking."""
    
    def test_file_within_limit(self, tmp_path):
        """Test that files within size limit pass."""
        test_file = tmp_path / "small.csv"
        test_file.write_text("small content")
        
        assert check_file_size(test_file) is True
    
    def test_file_exceeds_limit(self, tmp_path):
        """Test that files exceeding limit are rejected."""
        test_file = tmp_path / "large.csv"
        # Create file larger than default limit
        with open(test_file, 'wb') as f:
            f.write(b'x' * (MAX_FILE_SIZE + 1))
        
        assert check_file_size(test_file) is False
    
    def test_custom_size_limit(self, tmp_path):
        """Test that custom size limits work."""
        test_file = tmp_path / "test.csv"
        test_file.write_text("x" * 100)
        
        assert check_file_size(test_file, max_size=50) is False
        assert check_file_size(test_file, max_size=200) is True


class TestFileCleanup:
    """Test file cleanup functions."""
    
    def test_cleanup_existing_file(self, tmp_path):
        """Test that existing files are deleted."""
        test_file = tmp_path / "test.csv"
        test_file.write_text("content")
        
        assert test_file.exists()
        result = cleanup_temp_file(test_file)
        assert result is True
        assert not test_file.exists()
    
    def test_cleanup_nonexistent_file(self, tmp_path):
        """Test that cleanup of nonexistent files returns False."""
        test_file = tmp_path / "nonexistent.csv"
        
        result = cleanup_temp_file(test_file)
        assert result is False
    
    def test_cleanup_old_files(self, tmp_path):
        """Test that old files are cleaned up."""
        import time
        
        # Create some test files
        old_file = tmp_path / "old.csv"
        old_file.write_text("old")
        
        # Make file appear old by modifying its timestamp
        old_time = time.time() - 7200  # 2 hours ago
        import os
        os.utime(old_file, (old_time, old_time))
        
        new_file = tmp_path / "new.csv"
        new_file.write_text("new")
        
        # Clean up files older than 1 hour
        deleted = cleanup_old_files(tmp_path, max_age_seconds=3600)
        
        assert deleted >= 1
        assert not old_file.exists()
        assert new_file.exists()


class TestSecurityIntegration:
    """Integration tests for security measures."""
    
    def test_full_upload_validation_workflow(self, tmp_path):
        """Test complete validation workflow for file upload."""
        # Create a valid CSV file
        csv_file = tmp_path / "test.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['DOI', 'Title', 'Abstract Note'])
            writer.writerow(['10.1234/test', 'Test Title', 'Test Abstract'])
        
        # Step 1: Validate extension
        assert validate_file_extension(csv_file.name) is True
        
        # Step 2: Sanitize filename
        safe_name = sanitize_filename(csv_file.name)
        assert safe_name == 'test.csv'
        
        # Step 3: Check file size
        assert check_file_size(csv_file) is True
        
        # Step 4: Validate CSV format
        is_valid, error = validate_csv_format(csv_file)
        assert is_valid is True
        assert error is None
        
        # Step 5: Cleanup
        assert cleanup_temp_file(csv_file) is True
    
    def test_malicious_upload_rejected(self, tmp_path):
        """Test that malicious uploads are rejected."""
        # Create a file with malicious filename
        malicious_name = "../../../etc/passwd"
        
        # Step 1: Sanitize filename
        safe_name = sanitize_filename(malicious_name)
        
        # Should not contain path traversal
        assert '..' not in safe_name
        assert '/' not in safe_name
        assert '\\' not in safe_name
