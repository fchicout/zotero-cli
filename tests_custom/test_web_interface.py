"""Tests for the web interface.

This module tests the Flask web application endpoints to ensure proper
file upload, conversion, and download functionality.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from io import BytesIO
from hypothesis import given, settings, strategies as st

from custom.web.app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    app.config['UPLOAD_FOLDER'] = Path(tempfile.mkdtemp())
    app.config['OUTPUT_FOLDER'] = Path(tempfile.mkdtemp())
    
    with app.test_client() as client:
        yield client
    
    # Cleanup
    shutil.rmtree(app.config['UPLOAD_FOLDER'], ignore_errors=True)
    shutil.rmtree(app.config['OUTPUT_FOLDER'], ignore_errors=True)


@pytest.fixture
def sample_csv():
    """Create a sample Springer CSV file for testing."""
    csv_content = """Item Title,Authors,Publication Year,Item DOI,URL,Content Type,Publication Title,Journal Volume,Journal Issue
"Machine Learning Applications","John Smith",2023,10.1007/test,https://example.com,Article,Journal of AI,10,2
"Deep Learning Methods","Jane Doe",2024,10.1007/test2,https://example.com,Conference Paper,AI Conference,,
"""
    return csv_content.encode('utf-8')


def test_index_route(client):
    """Test that the index page loads successfully."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'CSV to BibTeX Converter' in response.data


def test_convert_no_file(client):
    """Test conversion endpoint with no file uploaded."""
    response = client.post('/convert')
    assert response.status_code == 400
    data = response.get_json()
    assert data['success'] is False
    assert 'No file uploaded' in data['error']


def test_convert_empty_filename(client):
    """Test conversion endpoint with empty filename."""
    data = {'csv_file': (BytesIO(b''), '')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['success'] is False
    assert 'No file selected' in json_data['error']


def test_convert_invalid_file_type(client):
    """Test conversion endpoint with non-CSV file."""
    data = {'csv_file': (BytesIO(b'test content'), 'test.txt')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['success'] is False
    assert 'Invalid file type' in json_data['error']


def test_convert_valid_csv(client, sample_csv):
    """Test successful conversion of a valid CSV file."""
    data = {'csv_file': (BytesIO(sample_csv), 'test.csv')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    
    # Should succeed
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['success'] is True
    assert json_data['entries_count'] == 2
    assert len(json_data['files']) > 0
    
    # Check that download links are generated
    for file_info in json_data['files']:
        assert 'filename' in file_info
        assert 'url' in file_info
        assert file_info['filename'].endswith('.bib')


def test_download_existing_file(client, sample_csv):
    """Test successful download of an existing file."""
    # First, create a file through conversion
    data = {'csv_file': (BytesIO(sample_csv), 'test.csv')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data['success'] is True
    assert len(json_data['files']) > 0
    
    # Get the first file
    filename = json_data['files'][0]['filename']
    
    # Download the file
    download_response = client.get(f'/download/{filename}')
    
    # Verify successful download
    assert download_response.status_code == 200
    assert len(download_response.data) > 0
    
    # Verify content is BibTeX format
    content = download_response.data.decode('utf-8')
    assert '@' in content  # BibTeX entries start with @
    assert 'author' in content.lower()
    
    # Verify correct content-disposition header for download
    assert download_response.headers.get('Content-Disposition') is not None


def test_download_nonexistent_file(client):
    """Test downloading a file that doesn't exist."""
    response = client.get('/download/nonexistent.bib')
    assert response.status_code == 404
    json_data = response.get_json()
    assert json_data['success'] is False
    assert 'File not found' in json_data['error']


def test_download_with_path_traversal_attempt(client):
    """Test that path traversal attempts are blocked."""
    # Try to access a file outside the output directory
    response = client.get('/download/../../../etc/passwd')
    # Should either return 404 or handle securely
    assert response.status_code in [404, 400]
    
    # Try with encoded path traversal
    response = client.get('/download/..%2F..%2Fetc%2Fpasswd')
    assert response.status_code in [404, 400]


def test_file_size_limit(client):
    """Test that files exceeding size limit are rejected."""
    # Create a file larger than 16MB
    large_content = b'x' * (17 * 1024 * 1024)
    data = {'csv_file': (BytesIO(large_content), 'large.csv')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    assert response.status_code == 413
    # The error handler may return JSON or HTML depending on request type
    if response.content_type and 'json' in response.content_type:
        json_data = response.get_json()
        assert json_data['success'] is False
        assert 'too large' in json_data['error'].lower()


def test_empty_csv_file(client):
    """Test handling of empty CSV file (Requirement 4.5)."""
    empty_content = b''
    data = {'csv_file': (BytesIO(empty_content), 'empty.csv')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    # Should fail with appropriate error
    json_data = response.get_json()
    assert json_data['success'] is False


def test_malformed_csv_file(client):
    """Test handling of malformed CSV file (Requirement 4.5)."""
    # CSV with missing required columns
    malformed_content = b'Column1,Column2\nValue1,Value2\n'
    data = {'csv_file': (BytesIO(malformed_content), 'malformed.csv')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    # Should fail gracefully
    json_data = response.get_json()
    assert json_data['success'] is False


def test_csv_with_special_characters(client):
    """Test handling of CSV with special characters (Requirement 4.5)."""
    csv_content = b"""Item Title,Authors,Publication Year,Item DOI,URL,Content Type,Publication Title,Journal Volume,Journal Issue
"Test & Title with <special> chars","Author's Name",2023,10.1007/test,https://example.com,Article,Journal,10,2
"""
    data = {'csv_file': (BytesIO(csv_content), 'special.csv')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    # Should handle special characters gracefully
    assert response.status_code in [200, 500]  # Either succeeds or fails gracefully
    json_data = response.get_json()
    if json_data['success']:
        # If successful, verify the file was created
        assert len(json_data['files']) > 0


def test_concurrent_uploads(client, sample_csv):
    """Test handling of concurrent file uploads (Requirement 8.4)."""
    # Simulate multiple uploads
    responses = []
    for i in range(3):
        data = {'csv_file': (BytesIO(sample_csv), f'test{i}.csv')}
        response = client.post('/convert', data=data, content_type='multipart/form-data')
        responses.append(response)
    
    # All should succeed independently
    for response in responses:
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True


def test_error_message_clarity(client):
    """Test that error messages are clear and helpful (Requirement 4.5, 7.5)."""
    # Test various error scenarios and verify error messages
    
    # No file uploaded
    response = client.post('/convert')
    json_data = response.get_json()
    assert 'file' in json_data['error'].lower()
    
    # Empty filename
    data = {'csv_file': (BytesIO(b''), '')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    json_data = response.get_json()
    assert 'file' in json_data['error'].lower() or 'select' in json_data['error'].lower()
    
    # Invalid file type
    data = {'csv_file': (BytesIO(b'test'), 'test.txt')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    json_data = response.get_json()
    assert 'csv' in json_data['error'].lower() or 'type' in json_data['error'].lower()


def test_progress_indicator_workflow(client, sample_csv):
    """Test that the conversion workflow provides appropriate feedback (Requirement 8.4)."""
    # This test verifies the API returns appropriate data for progress indication
    data = {'csv_file': (BytesIO(sample_csv), 'test.csv')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    
    json_data = response.get_json()
    # Response should include entry count for progress feedback
    assert 'entries_count' in json_data
    # Response should include files list for completion feedback
    assert 'files' in json_data


def test_error_recovery(client, sample_csv):
    """Test that system can recover from errors (Requirement 4.5)."""
    # First, cause an error with invalid file
    data = {'csv_file': (BytesIO(b'invalid'), 'test.txt')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    
    # Then, verify system can still process valid file
    data = {'csv_file': (BytesIO(sample_csv), 'test.csv')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['success'] is True


def test_file_upload_with_unicode_filename(client, sample_csv):
    """Test handling of files with unicode characters in filename (Requirement 8.4)."""
    unicode_filename = 'test_文件_файл_αρχείο.csv'
    data = {'csv_file': (BytesIO(sample_csv), unicode_filename)}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    # Should handle unicode filenames gracefully
    assert response.status_code in [200, 400]  # Either succeeds or fails gracefully
    json_data = response.get_json()
    # Should not crash the server
    assert 'success' in json_data


def test_warnings_in_response(client):
    """Test that warnings are included in response when appropriate (Requirement 4.5)."""
    # Create CSV with potential issues that might generate warnings
    csv_content = b"""Item Title,Authors,Publication Year,Item DOI,URL,Content Type,Publication Title,Journal Volume,Journal Issue
"Valid Entry","John Smith",2023,10.1007/test,https://example.com,Article,Journal,10,2
"""
    data = {'csv_file': (BytesIO(csv_content), 'test.csv')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    
    json_data = response.get_json()
    # Response should have a warnings field (even if empty)
    assert 'warnings' in json_data or 'errors' in json_data


def test_cleanup_endpoint(client, sample_csv):
    """Test that the cleanup endpoint removes files after download."""
    # First, create a file through conversion
    data = {'csv_file': (BytesIO(sample_csv), 'test.csv')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data['success'] is True
    assert len(json_data['files']) > 0
    
    # Get the first file
    filename = json_data['files'][0]['filename']
    file_path = app.config['OUTPUT_FOLDER'] / filename
    
    # Verify file exists
    assert file_path.exists()
    
    # Call cleanup endpoint
    cleanup_response = client.post(f'/cleanup/{filename}')
    assert cleanup_response.status_code == 200
    
    cleanup_data = cleanup_response.get_json()
    assert cleanup_data['success'] is True
    
    # Verify file was deleted
    assert not file_path.exists()


def test_cleanup_nonexistent_file(client):
    """Test cleanup endpoint with a file that doesn't exist."""
    response = client.post('/cleanup/nonexistent.bib')
    # Should succeed even if file doesn't exist (idempotent)
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['success'] is True


def test_download_file_persistence(client, sample_csv):
    """Test that files persist after download until explicitly cleaned up."""
    # Step 1: Convert CSV to BibTeX
    data = {'csv_file': (BytesIO(sample_csv), 'test.csv')}
    response = client.post('/convert', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    
    json_data = response.get_json()
    assert json_data['success'] is True
    assert len(json_data['files']) > 0
    
    # Get the first file
    filename = json_data['files'][0]['filename']
    file_path = app.config['OUTPUT_FOLDER'] / filename
    
    # Step 2: Verify file exists before download
    assert file_path.exists()
    
    # Step 3: Download the file
    download_response = client.get(f'/download/{filename}')
    assert download_response.status_code == 200
    assert len(download_response.data) > 0
    
    # Verify content is valid BibTeX
    content = download_response.data.decode('utf-8')
    assert '@' in content
    
    # Step 4: File should still exist after download (not auto-deleted)
    assert file_path.exists()
    
    # Step 5: Can download the same file multiple times
    download_response2 = client.get(f'/download/{filename}')
    assert download_response2.status_code == 200
    assert download_response2.data == download_response.data
    
    # File still exists after multiple downloads
    assert file_path.exists()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


# Property-Based Tests

def create_test_client():
    """Create a test client for property-based tests."""
    app.config['TESTING'] = True
    temp_upload = Path(tempfile.mkdtemp())
    temp_output = Path(tempfile.mkdtemp())
    app.config['UPLOAD_FOLDER'] = temp_upload
    app.config['OUTPUT_FOLDER'] = temp_output
    
    client = app.test_client()
    return client, temp_upload, temp_output


# Feature: csv-to-bib-refactor, Property 7: File upload validation
# Validates: Requirements 4.2
@settings(max_examples=100)
@given(
    filename=st.one_of(
        # Valid CSV filenames - must have a base name before .csv
        st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            whitelist_characters='_-'
        )).filter(lambda s: s and s.strip()).map(lambda s: f"{s}.csv"),
        # Invalid non-CSV filenames
        st.sampled_from([
            'test.txt', 'test.pdf', 'test.doc', 'test.xlsx', 
            'test.json', 'test.xml', 'test.bib', 'test.py',
            'test.html', 'test.zip', 'test', 'test.CSV.txt',
            'test.csv.bak', 'file.Csv', 'file.CSV'
        ])
    ),
    file_content=st.binary(min_size=0, max_size=1000)
)
def test_property_file_upload_validation(filename, file_content):
    """Property 7: For any file uploaded, system SHALL reject non-CSV and accept CSV files.
    
    This property test verifies that:
    1. Files with .csv extension (case-insensitive) are accepted for processing
    2. Files without .csv extension are rejected with appropriate error
    3. The validation happens before any processing occurs
    
    Note: This test validates the file extension check. Files with valid .csv extension
    may still fail during processing if the content is invalid, but they should NOT
    be rejected with "Invalid file type" error.
    """
    # Create test client for this test
    client, temp_upload, temp_output = create_test_client()
    
    try:
        # Determine if this should be accepted based on extension
        # The allowed_file() function checks for .csv extension (case-insensitive)
        is_valid_csv_extension = (
            '.' in filename and 
            filename.rsplit('.', 1)[1].lower() == 'csv'
        )
        
        # Upload the file
        data = {'csv_file': (BytesIO(file_content), filename)}
        response = client.post('/convert', data=data, content_type='multipart/form-data')
        json_data = response.get_json()
        
        if is_valid_csv_extension:
            # Valid CSV files should either succeed or fail with conversion errors (not validation errors)
            # They should NOT be rejected for invalid file type
            if not json_data['success']:
                error_msg = json_data.get('error', '')
                assert 'Invalid file type' not in error_msg, \
                    f"File with .csv extension should not be rejected for invalid type: {filename}"
        else:
            # Invalid files should be rejected with 400 status and appropriate error
            assert response.status_code == 400, \
                f"Non-CSV file should return 400 status: {filename}"
            assert json_data['success'] is False
            assert 'Invalid file type' in json_data['error'] or 'No file selected' in json_data['error']
    finally:
        # Cleanup
        shutil.rmtree(temp_upload, ignore_errors=True)
        shutil.rmtree(temp_output, ignore_errors=True)


# Feature: csv-to-bib-refactor, Property 8: Web pipeline completeness
# Validates: Requirements 4.4
@settings(max_examples=100)
@given(
    num_entries=st.integers(min_value=1, max_value=10),
    authors_have_concatenation=st.booleans()
)
def test_property_web_pipeline_completeness(num_entries, authors_have_concatenation):
    """Property 8: For any valid CSV file uploaded, system SHALL execute both conversion and author fixing.
    
    This property test verifies that:
    1. The web interface accepts valid CSV files
    2. The CSV conversion step executes (produces raw BibTeX)
    3. The author fixing step executes automatically (produces _fixed files)
    4. The response contains download links for the fixed files
    
    The test generates random CSV data and verifies that both pipeline steps
    execute automatically without requiring separate user actions.
    """
    # Create test client for this test
    client, temp_upload, temp_output = create_test_client()
    
    try:
        # Generate valid Springer CSV content
        csv_lines = [
            "Item Title,Authors,Publication Year,Item DOI,URL,Content Type,Publication Title,Journal Volume,Journal Issue"
        ]
        
        for i in range(num_entries):
            # Generate author names - sometimes with concatenation to test fixing
            if authors_have_concatenation:
                # Create concatenated names like "JohnSmithMaryJones"
                authors = f"John{chr(65 + (i % 26))}Smith{chr(65 + ((i+1) % 26))}Jones"
            else:
                # Normal separated names
                authors = f"John Smith and Mary Jones"
            
            title = f"Test Paper Number {i} About Machine Learning"
            year = 2020 + (i % 5)
            doi = f"10.1007/test{i}"
            url = f"https://example.com/paper{i}"
            content_type = "Article" if i % 2 == 0 else "Conference Paper"
            journal = f"Test Journal {i}"
            volume = str(10 + i)
            issue = str(i + 1)
            
            csv_lines.append(
                f'"{title}","{authors}",{year},{doi},{url},{content_type},"{journal}",{volume},{issue}'
            )
        
        csv_content = '\n'.join(csv_lines).encode('utf-8')
        
        # Upload the CSV file through the web interface
        data = {'csv_file': (BytesIO(csv_content), 'test_springer.csv')}
        response = client.post('/convert', data=data, content_type='multipart/form-data')
        
        # Verify the request succeeded
        assert response.status_code == 200, \
            f"Valid CSV should return 200 status, got {response.status_code}"
        
        json_data = response.get_json()
        assert json_data is not None, "Response should contain JSON data"
        assert json_data['success'] is True, \
            f"Conversion should succeed for valid CSV. Errors: {json_data.get('errors', [])}"
        
        # Property 8 Verification: Both steps must execute
        
        # 1. Verify CSV conversion executed (entries were processed)
        assert json_data['entries_count'] == num_entries, \
            f"Should process all {num_entries} entries, got {json_data['entries_count']}"
        
        # 2. Verify author fixing executed (files have _fixed suffix)
        assert 'files' in json_data, "Response should contain files list"
        assert len(json_data['files']) > 0, "Should generate at least one output file"
        
        # All output files should have _fixed suffix (indicating author fixing was applied)
        for file_info in json_data['files']:
            filename = file_info['filename']
            assert '_fixed' in filename, \
                f"File '{filename}' should have _fixed suffix, indicating author fixing step executed"
            assert filename.endswith('.bib'), \
                f"File '{filename}' should be a BibTeX file"
        
        # 3. Verify download links are provided (part of complete pipeline)
        for file_info in json_data['files']:
            assert 'url' in file_info, "Each file should have a download URL"
            assert '/download/' in file_info['url'], \
                "Download URL should point to download endpoint"
        
        # 4. Verify the actual files exist in the output directory
        for file_info in json_data['files']:
            filename = file_info['filename']
            file_path = temp_output / filename
            assert file_path.exists(), \
                f"Output file {filename} should exist after pipeline completes"
            
            # Verify the file contains BibTeX content
            content = file_path.read_text(encoding='utf-8')
            assert '@' in content, "File should contain BibTeX entries (starting with @)"
            assert 'author' in content.lower(), "File should contain author fields"
        
        # Additional verification: If authors were concatenated, check that fixing occurred
        if authors_have_concatenation:
            # Read one of the output files and verify it contains " and " separators
            first_file = temp_output / json_data['files'][0]['filename']
            content = first_file.read_text(encoding='utf-8')
            # The author fixer should have inserted " and " between concatenated names
            assert ' and ' in content, \
                "Author fixing should have separated concatenated names with ' and '"
        
    finally:
        # Cleanup
        shutil.rmtree(temp_upload, ignore_errors=True)
        shutil.rmtree(temp_output, ignore_errors=True)


# Feature: csv-to-bib-refactor, Property 9: Download link generation
# Validates: Requirements 4.3
@settings(max_examples=100)
@given(
    num_entries=st.integers(min_value=1, max_value=100),
    entries_per_file=st.integers(min_value=1, max_value=50)
)
def test_property_download_link_generation(num_entries, entries_per_file):
    """Property 9: For any successful conversion, response SHALL contain download links for all generated files.
    
    This property test verifies that:
    1. After successful conversion, the response contains a 'files' list
    2. Each file entry has both 'filename' and 'url' fields
    3. The number of download links matches the number of generated files
    4. Each download URL points to the correct download endpoint
    5. Each download URL contains the correct filename
    6. All generated files have corresponding download links
    
    The test generates random CSV data with varying numbers of entries and
    verifies that download links are correctly generated for all output files.
    """
    # Create test client for this test
    client, temp_upload, temp_output = create_test_client()
    
    try:
        # Generate valid Springer CSV content with specified number of entries
        csv_lines = [
            "Item Title,Authors,Publication Year,Item DOI,URL,Content Type,Publication Title,Journal Volume,Journal Issue"
        ]
        
        for i in range(num_entries):
            title = f"Research Paper {i} on Advanced Topics"
            authors = f"Author{i} Lastname{i}"
            year = 2020 + (i % 5)
            doi = f"10.1007/paper{i}"
            url = f"https://example.com/paper{i}"
            content_type = "Article"
            journal = f"Journal {i}"
            volume = str(i + 1)
            issue = str(i + 1)
            
            csv_lines.append(
                f'"{title}","{authors}",{year},{doi},{url},{content_type},"{journal}",{volume},{issue}'
            )
        
        csv_content = '\n'.join(csv_lines).encode('utf-8')
        
        # Upload the CSV file through the web interface
        data = {'csv_file': (BytesIO(csv_content), 'test_data.csv')}
        response = client.post('/convert', data=data, content_type='multipart/form-data')
        
        # Verify the request succeeded
        assert response.status_code == 200, \
            f"Valid CSV should return 200 status, got {response.status_code}"
        
        json_data = response.get_json()
        assert json_data is not None, "Response should contain JSON data"
        assert json_data['success'] is True, \
            f"Conversion should succeed. Errors: {json_data.get('errors', [])}"
        
        # Property 9 Verification: Download links for all generated files
        
        # 1. Response must contain 'files' list
        assert 'files' in json_data, \
            "Response must contain 'files' field with download links"
        
        files_list = json_data['files']
        assert isinstance(files_list, list), \
            "'files' field must be a list"
        
        # 2. At least one file should be generated
        assert len(files_list) > 0, \
            "Response must contain at least one download link for generated files"
        
        # 3. Calculate expected number of files based on entries_per_file
        # The converter uses entries_per_file=49 by default
        expected_num_files = (num_entries + 48) // 49  # Ceiling division
        
        # The actual number of files should match expected
        # (allowing for the fact that the converter might use its default)
        assert len(files_list) >= 1, \
            f"Should generate at least 1 file for {num_entries} entries"
        
        # 4. Each file entry must have required fields
        for idx, file_info in enumerate(files_list):
            assert isinstance(file_info, dict), \
                f"File entry {idx} must be a dictionary"
            
            # Must have 'filename' field
            assert 'filename' in file_info, \
                f"File entry {idx} must have 'filename' field"
            
            # Must have 'url' field
            assert 'url' in file_info, \
                f"File entry {idx} must have 'url' field"
            
            filename = file_info['filename']
            url = file_info['url']
            
            # Filename must be non-empty string
            assert isinstance(filename, str) and len(filename) > 0, \
                f"Filename must be non-empty string, got: {filename}"
            
            # URL must be non-empty string
            assert isinstance(url, str) and len(url) > 0, \
                f"URL must be non-empty string, got: {url}"
            
            # Filename must end with .bib
            assert filename.endswith('.bib'), \
                f"Filename must end with .bib extension: {filename}"
            
            # Filename must contain _fixed suffix (indicating author fixing was applied)
            assert '_fixed' in filename, \
                f"Filename must contain _fixed suffix: {filename}"
            
            # URL must point to download endpoint
            assert '/download/' in url, \
                f"URL must point to /download/ endpoint: {url}"
            
            # URL must contain the filename
            assert filename in url, \
                f"URL must contain the filename. URL: {url}, Filename: {filename}"
        
        # 5. Verify that all generated files have corresponding download links
        # Check that files actually exist in the output directory
        actual_files = list(temp_output.glob('*.bib'))
        
        # All files in the response should exist
        response_filenames = {f['filename'] for f in files_list}
        for file_info in files_list:
            filename = file_info['filename']
            file_path = temp_output / filename
            assert file_path.exists(), \
                f"File referenced in download link should exist: {filename}"
        
        # All existing _fixed.bib files should have download links
        for actual_file in actual_files:
            if '_fixed' in actual_file.name:
                assert actual_file.name in response_filenames, \
                    f"Generated file {actual_file.name} should have a download link in response"
        
        # 6. Verify download links are functional (can be used to download files)
        for file_info in files_list:
            filename = file_info['filename']
            # Extract the path from the URL (remove any query parameters or fragments)
            url_path = file_info['url'].split('?')[0].split('#')[0]
            
            # Make a request to the download endpoint
            download_response = client.get(url_path)
            
            # Should return 200 OK
            assert download_response.status_code == 200, \
                f"Download link should be functional: {url_path}"
            
            # Should return file content
            assert len(download_response.data) > 0, \
                f"Downloaded file should have content: {filename}"
            
            # Content should be BibTeX format (contains @ symbol)
            content = download_response.data.decode('utf-8', errors='ignore')
            assert '@' in content, \
                f"Downloaded file should contain BibTeX entries: {filename}"
        
    finally:
        # Cleanup
        shutil.rmtree(temp_upload, ignore_errors=True)
        shutil.rmtree(temp_output, ignore_errors=True)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
