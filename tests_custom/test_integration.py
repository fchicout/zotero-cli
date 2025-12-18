"""Integration tests for the complete CSV to BibTeX conversion pipeline.

This module tests the end-to-end workflows for both CLI and web interfaces,
verifying that all components work together correctly.

Requirements tested: 2.1, 2.2, 2.3, 2.4, 4.1, 4.2, 4.3, 4.4
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import subprocess
import sys
import re

from custom.core.csv_converter import CSVConverter
from custom.core.author_fixer import AuthorFixer
from custom.web.app import app


class TestCLIIntegration:
    """Integration tests for CLI workflow."""
    
    def test_cli_basic_conversion(self, tmp_path):
        """Test CLI: CSV input → BibTeX output (Requirement 2.1, 2.2)"""
        # Setup
        input_csv = Path("tests_custom/fixtures/sample_springer.csv")
        output_dir = tmp_path / "output"
        
        # Execute CLI command
        result = subprocess.run(
            [
                sys.executable, "-m", "custom.cli.main",
                "--input", str(input_csv),
                "--output-dir", str(output_dir)
            ],
            capture_output=True,
            text=True
        )
        
        # Verify success
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "Conversion completed successfully" in result.stdout
        
        # Verify output file exists with correct naming (Requirement 2.2)
        output_files = list(output_dir.glob("springer_results_raw*.bib"))
        assert len(output_files) > 0, "No output files created"
        
        # Verify file naming convention
        for f in output_files:
            assert re.match(r'springer_results_raw(_part\d+)?\.bib', f.name), \
                f"Invalid filename: {f.name}"
        
        # Verify content is valid BibTeX
        content = output_files[0].read_text()
        assert "@" in content, "Output doesn't contain BibTeX entries"
        assert "author = {" in content, "Missing author field"
        assert "title = {" in content, "Missing title field"
    
    def test_cli_with_author_fixing(self, tmp_path):
        """Test CLI: CSV → BibTeX → fixed authors (Requirement 2.3, 2.4)"""
        # Setup
        input_csv = Path("tests_custom/fixtures/sample_springer.csv")
        output_dir = tmp_path / "output"
        
        # Execute CLI with --fix-authors flag
        result = subprocess.run(
            [
                sys.executable, "-m", "custom.cli.main",
                "--input", str(input_csv),
                "--output-dir", str(output_dir),
                "--fix-authors"
            ],
            capture_output=True,
            text=True
        )
        
        # Verify success
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "Conversion completed successfully" in result.stdout
        assert "Fixed" in result.stdout or "author" in result.stdout.lower()
        
        # Verify both raw and fixed files exist
        raw_files = list(output_dir.glob("springer_results_raw*.bib"))
        fixed_files = list(output_dir.glob("*_fixed.bib"))
        
        assert len(raw_files) > 0, "No raw output files created"
        assert len(fixed_files) > 0, "No fixed output files created"
        
        # Verify fixed file naming convention (Requirement 2.4)
        for fixed_file in fixed_files:
            assert "_fixed" in fixed_file.name, \
                f"Fixed file doesn't have _fixed suffix: {fixed_file.name}"
            
            # Verify corresponding raw file exists
            raw_name = fixed_file.name.replace("_fixed", "")
            raw_file = output_dir / raw_name
            assert raw_file.exists(), \
                f"Corresponding raw file not found: {raw_name}"
        
        # Verify author fixing worked
        fixed_content = fixed_files[0].read_text()
        assert " and " in fixed_content, "Authors not properly separated"
    
    def test_cli_error_handling_missing_file(self):
        """Test CLI error handling for non-existent input file"""
        result = subprocess.run(
            [
                sys.executable, "-m", "custom.cli.main",
                "--input", "nonexistent.csv",
                "--output-dir", "data/output"
            ],
            capture_output=True,
            text=True
        )
        
        # Should fail with error message
        assert result.returncode != 0, "CLI should fail for missing file"
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()
    
    def test_cli_output_directory_creation(self, tmp_path):
        """Test CLI creates output directory if it doesn't exist (Requirement 7.3)"""
        input_csv = Path("tests_custom/fixtures/sample_springer.csv")
        output_dir = tmp_path / "nested" / "output" / "dir"
        
        # Directory shouldn't exist yet
        assert not output_dir.exists()
        
        # Execute CLI
        result = subprocess.run(
            [
                sys.executable, "-m", "custom.cli.main",
                "--input", str(input_csv),
                "--output-dir", str(output_dir)
            ],
            capture_output=True,
            text=True
        )
        
        # Verify success and directory was created
        assert result.returncode == 0
        assert output_dir.exists(), "Output directory was not created"
        assert list(output_dir.glob("*.bib")), "No files in created directory"


class TestWebIntegration:
    """Integration tests for web interface workflow."""
    
    @pytest.fixture
    def client(self):
        """Create Flask test client."""
        app.config['TESTING'] = True
        app.config['UPLOAD_FOLDER'] = Path(tempfile.mkdtemp())
        app.config['OUTPUT_FOLDER'] = Path(tempfile.mkdtemp())
        
        with app.test_client() as client:
            yield client
        
        # Cleanup
        shutil.rmtree(app.config['UPLOAD_FOLDER'], ignore_errors=True)
        shutil.rmtree(app.config['OUTPUT_FOLDER'], ignore_errors=True)
    
    def test_web_index_page_loads(self, client):
        """Test web interface index page loads (Requirement 4.1)"""
        response = client.get('/')
        
        assert response.status_code == 200
        assert b'upload' in response.data.lower() or b'csv' in response.data.lower()
    
    def test_web_complete_workflow(self, client):
        """Test web: upload CSV → download fixed BibTeX (Requirement 4.1-4.4)"""
        # Read sample CSV
        csv_path = Path("tests_custom/fixtures/sample_springer.csv")
        
        with open(csv_path, 'rb') as f:
            csv_data = f.read()
        
        # Upload and convert (Requirement 4.1, 4.2)
        from io import BytesIO
        response = client.post(
            '/convert',
            data={'csv_file': (BytesIO(csv_data), 'test.csv')},
            content_type='multipart/form-data'
        )
        
        # Verify successful conversion
        assert response.status_code == 200
        json_data = response.get_json()
        
        assert json_data['success'] is True, f"Conversion failed: {json_data.get('error')}"
        assert json_data['entries_count'] > 0, "No entries converted"
        
        # Verify download links are provided (Requirement 4.3)
        assert 'files' in json_data, "No files in response"
        assert len(json_data['files']) > 0, "No download links provided"
        
        # Verify files have _fixed suffix (automatic pipeline - Requirement 4.4)
        for file_info in json_data['files']:
            assert '_fixed' in file_info['filename'], \
                f"File doesn't have _fixed suffix: {file_info['filename']}"
        
        # Test downloading a file (Requirement 4.3)
        download_filename = json_data['files'][0]['filename']
        download_response = client.get(f'/download/{download_filename}')
        
        assert download_response.status_code == 200
        assert download_response.mimetype == 'application/octet-stream' or \
               'attachment' in download_response.headers.get('Content-Disposition', '')
        
        # Verify downloaded content is valid BibTeX
        content = download_response.data.decode('utf-8')
        assert "@" in content, "Downloaded file doesn't contain BibTeX entries"
        assert "author = {" in content, "Missing author field in downloaded file"
    
    def test_web_file_validation(self, client):
        """Test web interface validates file format (Requirement 4.2)"""
        # Try uploading a non-CSV file
        from io import BytesIO
        response = client.post(
            '/convert',
            data={'csv_file': (BytesIO(b'not a csv'), 'test.txt')},
            content_type='multipart/form-data'
        )
        
        # Should reject non-CSV files
        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert 'csv' in json_data['error'].lower() or 'invalid' in json_data['error'].lower() or 'file type' in json_data['error'].lower()
    
    def test_web_error_handling_no_file(self, client):
        """Test web interface error handling for missing file (Requirement 4.5)"""
        response = client.post('/convert', data={})
        
        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False
        assert 'error' in json_data
    
    def test_web_error_handling_empty_filename(self, client):
        """Test web interface error handling for empty filename (Requirement 4.5)"""
        from io import BytesIO
        response = client.post(
            '/convert',
            data={'csv_file': (BytesIO(b''), '')},
            content_type='multipart/form-data'
        )
        
        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data['success'] is False


class TestNamingConventions:
    """Tests to verify all output files follow naming conventions."""
    
    def test_raw_output_naming_convention(self, tmp_path):
        """Verify raw BibTeX files follow springer_results_raw_partX.bib pattern (Requirement 2.2)"""
        converter = CSVConverter()
        input_csv = Path("tests_custom/fixtures/sample_springer.csv")
        
        result = converter.convert(input_csv, tmp_path)
        
        assert result.success
        
        # Check each output file matches the pattern
        for output_file in result.output_files:
            filename = output_file.name
            assert filename.startswith("springer_results_raw"), \
                f"File doesn't start with springer_results_raw: {filename}"
            assert filename.endswith(".bib"), \
                f"File doesn't end with .bib: {filename}"
            
            # If multiple files, should have _partN
            if len(result.output_files) > 1:
                assert re.match(r'springer_results_raw_part\d+\.bib', filename), \
                    f"Multi-file output doesn't match pattern: {filename}"
    
    def test_fixed_output_naming_convention(self, tmp_path):
        """Verify fixed BibTeX files have _fixed suffix (Requirement 2.4)"""
        # First create a raw file
        converter = CSVConverter()
        input_csv = Path("tests_custom/fixtures/sample_springer.csv")
        result = converter.convert(input_csv, tmp_path)
        
        assert result.success
        raw_file = result.output_files[0]
        
        # Fix the file
        fixer = AuthorFixer()
        fixed_file = raw_file.with_stem(f"{raw_file.stem}_fixed")
        fix_result = fixer.fix_file(raw_file, fixed_file)
        
        assert fix_result.success
        assert fixed_file.exists()
        
        # Verify naming
        assert "_fixed" in fixed_file.name
        assert fixed_file.stem.replace("_fixed", "") == raw_file.stem


class TestErrorHandling:
    """Tests to verify error handling works across all components."""
    
    def test_converter_handles_missing_file(self):
        """Test converter error handling for non-existent file (Requirement 7.2)"""
        converter = CSVConverter()
        result = converter.convert(Path("nonexistent.csv"), Path("output"))
        
        assert not result.success
        assert len(result.errors) > 0
        assert "nonexistent.csv" in str(result.errors).lower() or \
               "not found" in str(result.errors).lower()
    
    def test_fixer_handles_missing_file(self):
        """Test author fixer error handling for non-existent file (Requirement 7.2)"""
        fixer = AuthorFixer()
        result = fixer.fix_file(
            Path("nonexistent.bib"),
            Path("output.bib")
        )
        
        assert not result.success
        assert len(result.errors) > 0
        assert "not found" in str(result.errors).lower()
    
    def test_error_messages_include_paths(self, tmp_path):
        """Test error messages include file paths (Requirement 7.5)"""
        converter = CSVConverter()
        missing_file = tmp_path / "missing.csv"
        
        result = converter.convert(missing_file, tmp_path)
        
        assert not result.success
        # Error message should mention the file path
        error_text = " ".join(result.errors).lower()
        assert "missing.csv" in error_text or str(missing_file) in error_text


class TestCleanup:
    """Tests for temporary file cleanup."""
    
    def test_web_cleans_uploaded_files(self, tmp_path):
        """Verify web interface cleans up uploaded CSV files"""
        from io import BytesIO
        app.config['TESTING'] = True
        app.config['UPLOAD_FOLDER'] = tmp_path / "upload"
        app.config['OUTPUT_FOLDER'] = tmp_path / "output"
        app.config['UPLOAD_FOLDER'].mkdir(parents=True, exist_ok=True)
        app.config['OUTPUT_FOLDER'].mkdir(parents=True, exist_ok=True)
        
        with app.test_client() as client:
            csv_path = Path("tests_custom/fixtures/sample_springer.csv")
            with open(csv_path, 'rb') as f:
                csv_data = f.read()
            
            # Upload and convert
            response = client.post(
                '/convert',
                data={'csv_file': (BytesIO(csv_data), 'test.csv')},
                content_type='multipart/form-data'
            )
            
            assert response.status_code == 200
            
            # Verify uploaded CSV was cleaned up
            uploaded_files = list(app.config['UPLOAD_FOLDER'].glob("*.csv"))
            assert len(uploaded_files) == 0, \
                f"Uploaded CSV not cleaned up: {uploaded_files}"
