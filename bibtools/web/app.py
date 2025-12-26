"""Flask web application for CSV to BibTeX conversion.

This module provides a simple web interface for uploading Springer CSV files
and downloading the converted BibTeX files with fixed author names.
"""

from flask import Flask, request, send_file, render_template, jsonify, url_for
from pathlib import Path
from werkzeug.utils import secure_filename
import os
import tempfile

from bibtools.core.csv_converter import CSVConverter
from bibtools.core.author_fixer import AuthorFixer
from bibtools.core.models import ConversionResult


# Initialize Flask app
app = Flask(__name__)

# Configuration
from bibtools.utils.security import MAX_FILE_SIZE

# Set maximum file size for uploads
# Note: This is a global limit. Individual endpoints may enforce stricter limits.
# The convert endpoint uses 16MB, while article extraction uses 50MB.
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE  # 50MB max file size

# Get the project root directory (2 levels up from this file)
PROJECT_ROOT = Path(__file__).parent.parent.parent
app.config['UPLOAD_FOLDER'] = PROJECT_ROOT / 'bibtools' / 'data' / 'temp'
app.config['OUTPUT_FOLDER'] = PROJECT_ROOT / 'bibtools' / 'data' / 'output'

# Ensure directories exist
app.config['UPLOAD_FOLDER'].mkdir(parents=True, exist_ok=True)
app.config['OUTPUT_FOLDER'].mkdir(parents=True, exist_ok=True)

# Periodic cleanup configuration
CLEANUP_INTERVAL_SECONDS = 3600  # Clean up old files every hour
TEMP_FILE_MAX_AGE_SECONDS = 3600  # Delete files older than 1 hour


def allowed_file(filename: str) -> bool:
    """Check if uploaded file has allowed extension.
    
    Args:
        filename: Name of the uploaded file
        
    Returns:
        True if file extension is .csv, False otherwise
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'


@app.route('/')
def index():
    """Render the landing page with tool selection.
    
    Displays a landing page where users can choose between:
    - CSV to BibTeX Converter
    - Article Extraction Tool
    
    Returns:
        Rendered HTML template for the landing page
    """
    return render_template('index.html')


@app.route('/converter')
def converter():
    """Render the CSV to BibTeX converter page.
    
    Displays the file upload form where users can select a CSV file
    for conversion (Requirement 4.1).
    
    Returns:
        Rendered HTML template for the converter page
    """
    return render_template('converter.html')


@app.route('/convert', methods=['POST'])
def convert():
    """Handle file upload and conversion.
    
    Processes the uploaded CSV file through the conversion pipeline:
    1. Validates the uploaded file
    2. Converts CSV to BibTeX
    3. Fixes author names
    4. Returns download links for the generated files
    
    This endpoint implements Requirements 4.1, 4.2, 4.3, 4.4.
    Note: This endpoint has a 16MB file size limit (stricter than the global 50MB limit).
    
    Returns:
        JSON response with success status and download links, or error message
    """
    # Check if file was uploaded
    if 'csv_file' not in request.files:
        return jsonify({
            'success': False,
            'error': 'No file uploaded'
        }), 400
    
    file = request.files['csv_file']
    
    # Check if file was selected
    if file.filename == '':
        return jsonify({
            'success': False,
            'error': 'No file selected'
        }), 400
    
    # Check file size for this endpoint (16MB limit for convert endpoint)
    # This is stricter than the global 50MB limit used by article extraction
    if request.content_length and request.content_length > 16 * 1024 * 1024:
        return jsonify({
            'success': False,
            'error': 'File too large. Maximum file size is 16MB.'
        }), 413
    
    # Validate file type (Requirement 4.2)
    if not allowed_file(file.filename):
        return jsonify({
            'success': False,
            'error': 'Invalid file type. Please upload a CSV file.'
        }), 400
    
    try:
        # Save uploaded file with secure filename
        filename = secure_filename(file.filename)
        input_path = app.config['UPLOAD_FOLDER'] / filename
        file.save(str(input_path))
        
        # Step 1: Convert CSV to BibTeX
        converter = CSVConverter()
        conversion_result = converter.convert(
            input_path,
            app.config['OUTPUT_FOLDER']
        )
        
        if not conversion_result.success:
            return jsonify({
                'success': False,
                'error': 'Conversion failed',
                'details': conversion_result.errors
            }), 500
        
        # Step 2: Fix author names (Requirement 4.4 - automatic pipeline)
        fixer = AuthorFixer()
        fixed_files = []
        
        for bib_file in conversion_result.output_files:
            # Create output path with _fixed suffix (Requirement 2.4)
            output_path = bib_file.with_stem(f"{bib_file.stem}_fixed")
            
            fix_result = fixer.fix_file(bib_file, output_path)
            
            if fix_result.success:
                fixed_files.append(output_path)
            else:
                # If fixing fails, still provide the raw file
                fixed_files.append(bib_file)
        
        # Generate download links (Requirement 4.3)
        download_links = [
            {
                'filename': f.name,
                'url': url_for('download', filename=f.name)
            }
            for f in fixed_files
        ]
        
        # Clean up uploaded file
        try:
            input_path.unlink()
        except:
            pass  # Ignore cleanup errors
        
        return jsonify({
            'success': True,
            'entries_count': conversion_result.entries_count,
            'files': download_links,
            'warnings': conversion_result.errors if conversion_result.errors else []
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'An error occurred during conversion: {str(e)}'
        }), 500


@app.route('/download/<filename>')
def download(filename):
    """Download a generated BibTeX file.
    
    Serves the requested BibTeX file for download. Files are served from
    the output directory (Requirement 4.3).
    
    File cleanup is handled by a separate cleanup endpoint to ensure
    the download completes successfully before deletion.
    
    Args:
        filename: Name of the file to download
        
    Returns:
        File download response, or 404 if file not found
    """
    try:
        # Secure the filename to prevent directory traversal
        filename = secure_filename(filename)
        file_path = app.config['OUTPUT_FOLDER'] / filename
        
        if not file_path.exists():
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error downloading file: {str(e)}'
        }), 500


@app.route('/download-all', methods=['POST'])
def download_all():
    """Download all generated BibTeX files as a ZIP archive.
    
    Creates a ZIP file containing all the BibTeX files from the last conversion
    and serves it for download.
    
    Returns:
        ZIP file download response, or error if files not found
    """
    try:
        import zipfile
        import io
        
        # Get list of files from request
        data = request.get_json()
        filenames = data.get('filenames', [])
        
        if not filenames:
            return jsonify({
                'success': False,
                'error': 'No files specified'
            }), 400
        
        # Create ZIP file in memory
        memory_file = io.BytesIO()
        
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename in filenames:
                # Secure the filename
                filename = secure_filename(filename)
                file_path = app.config['OUTPUT_FOLDER'] / filename
                
                if file_path.exists():
                    # Add file to ZIP with just the filename (no path)
                    zf.write(file_path, arcname=filename)
        
        # Seek to beginning of file
        memory_file.seek(0)
        
        # Generate ZIP filename based on first file
        if filenames:
            base_name = Path(filenames[0]).stem.replace('_fixed', '').replace('_part1', '')
            zip_filename = f"{base_name}_bibtex_files.zip"
        else:
            zip_filename = "bibtex_files.zip"
        
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error creating ZIP file: {str(e)}'
        }), 500


@app.route('/cleanup/<filename>', methods=['POST'])
def cleanup(filename):
    """Clean up a downloaded file.
    
    Removes the specified file from the output directory after download.
    This endpoint should be called by the client after download completes.
    
    Args:
        filename: Name of the file to clean up
        
    Returns:
        JSON response indicating success or failure
    """
    try:
        # Secure the filename to prevent directory traversal
        filename = secure_filename(filename)
        file_path = app.config['OUTPUT_FOLDER'] / filename
        
        if file_path.exists():
            file_path.unlink()
            
            # Also try to clean up the raw (non-fixed) version if it exists
            if '_fixed' in filename:
                raw_filename = filename.replace('_fixed', '')
                raw_path = app.config['OUTPUT_FOLDER'] / raw_filename
                if raw_path.exists():
                    raw_path.unlink()
        
        return jsonify({
            'success': True,
            'message': 'File cleaned up successfully'
        })
        
    except Exception as e:
        # Don't fail if cleanup fails - just log it
        return jsonify({
            'success': False,
            'error': f'Cleanup failed: {str(e)}'
        }), 500


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file size limit exceeded error.
    
    Returns a user-friendly error message when uploaded file exceeds
    the maximum allowed size (Requirement 4.5).
    
    Args:
        error: The error object
        
    Returns:
        JSON error response with 413 status code for AJAX requests,
        or rendered error page for direct requests
    """
    error_message = 'File too large. Maximum file size is 16MB.'
    
    # Check if request is AJAX or in testing mode
    if (request.is_json or 
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        app.config.get('TESTING')):
        return jsonify({
            'success': False,
            'error': error_message
        }), 413
    
    # Return HTML error page for direct requests
    return render_template('error.html', 
                         error_message=error_message,
                         error_details=['Try compressing your CSV file', 
                                      'Split large files into smaller chunks']), 413


@app.errorhandler(500)
def internal_server_error(error):
    """Handle internal server errors.
    
    Returns a user-friendly error message for unexpected server errors
    (Requirement 4.5).
    
    Args:
        error: The error object
        
    Returns:
        JSON error response with 500 status code for AJAX requests,
        or rendered error page for direct requests
    """
    error_message = 'An internal server error occurred. Please try again.'
    
    # Check if request is AJAX or in testing mode
    if (request.is_json or 
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        app.config.get('TESTING')):
        return jsonify({
            'success': False,
            'error': error_message
        }), 500
    
    # Return HTML error page for direct requests
    return render_template('error.html',
                         error_message=error_message,
                         error_details=['Check that your CSV file is properly formatted',
                                      'Ensure the file is not corrupted',
                                      'Try again in a few moments']), 500


@app.errorhandler(400)
def bad_request(error):
    """Handle bad request errors.
    
    Returns a user-friendly error message for invalid requests
    (Requirement 4.5).
    
    Args:
        error: The error object
        
    Returns:
        JSON error response with 400 status code for AJAX requests,
        or rendered error page for direct requests
    """
    error_message = 'Invalid request. Please check your input and try again.'
    
    # Check if request is AJAX or in testing mode
    if (request.is_json or 
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        app.config.get('TESTING')):
        return jsonify({
            'success': False,
            'error': error_message
        }), 400
    
    # Return HTML error page for direct requests
    return render_template('error.html',
                         error_message=error_message,
                         error_details=['Ensure you selected a valid CSV file',
                                      'Check that the file is not empty']), 400


@app.route('/cleanup-old-files', methods=['POST'])
def cleanup_old_files_endpoint():
    """Manually trigger cleanup of old temporary files.
    
    This endpoint can be called periodically to clean up old files
    from the upload and output directories. Implements automatic
    temporary file cleanup per Requirement 7.2.
    
    Returns:
        JSON response with cleanup statistics
    """
    try:
        from bibtools.utils.security import cleanup_old_files
        
        # Clean up old files from both directories
        upload_deleted = cleanup_old_files(
            app.config['UPLOAD_FOLDER'],
            TEMP_FILE_MAX_AGE_SECONDS
        )
        output_deleted = cleanup_old_files(
            app.config['OUTPUT_FOLDER'],
            TEMP_FILE_MAX_AGE_SECONDS
        )
        
        return jsonify({
            'success': True,
            'message': 'Cleanup completed',
            'upload_files_deleted': upload_deleted,
            'output_files_deleted': output_deleted,
            'total_deleted': upload_deleted + output_deleted
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Cleanup failed: {str(e)}'
        }), 500


def perform_periodic_cleanup():
    """Perform periodic cleanup of old temporary files.
    
    This function should be called periodically (e.g., via a scheduler)
    to clean up old files from temporary directories.
    """
    from bibtools.utils.security import cleanup_old_files
    
    try:
        upload_deleted = cleanup_old_files(
            app.config['UPLOAD_FOLDER'],
            TEMP_FILE_MAX_AGE_SECONDS
        )
        output_deleted = cleanup_old_files(
            app.config['OUTPUT_FOLDER'],
            TEMP_FILE_MAX_AGE_SECONDS
        )
        
        if upload_deleted > 0 or output_deleted > 0:
            print(f"Periodic cleanup: deleted {upload_deleted} upload files and {output_deleted} output files")
    except Exception as e:
        print(f"Periodic cleanup failed: {str(e)}")



# Article Extraction Routes

@app.route('/extract-articles', methods=['GET', 'POST'])
def extract_articles():
    """Handle CSV upload and Excel generation for article extraction.
    
    GET: Display upload form
    POST: Process uploaded file and return Excel download
    
    This endpoint implements Requirements 7.1, 7.2, 7.3, 7.4.
    Security measures implemented per Requirement 7.2:
    - File upload validation (CSV format check)
    - Path sanitization to prevent directory traversal
    - File size limits for web uploads
    - Temporary file cleanup
    
    Returns:
        GET: Rendered HTML template for upload form
        POST: JSON response with success status and download link, or error message
    """
    if request.method == 'GET':
        # Display upload form (Requirement 7.1)
        return render_template('extract_articles.html')
    
    # POST request - handle file upload
    # Check if file was uploaded
    if 'csv_file' not in request.files:
        return jsonify({
            'success': False,
            'error': 'No file uploaded'
        }), 400
    
    file = request.files['csv_file']
    
    # Check if file was selected
    if file.filename == '':
        return jsonify({
            'success': False,
            'error': 'No file selected'
        }), 400
    
    # Import security utilities
    from bibtools.utils.security import (
        validate_file_extension,
        sanitize_filename,
        validate_csv_format,
        check_file_size,
        cleanup_temp_file,
        SecurityError,
        InvalidFileTypeError,
        FileSizeExceededError
    )
    
    # Validate file extension (Requirement 7.2 - CSV format check)
    if not validate_file_extension(file.filename):
        return jsonify({
            'success': False,
            'error': 'Invalid file type. Please upload a CSV file.'
        }), 400
    
    input_path = None
    
    try:
        from bibtools.core.article_extractor import (
            ArticleExtractor,
            ArticleExtractorError,
            InvalidCSVError,
            EmptyDataError
        )
        from bibtools.utils.file_handler import FileHandler
        
        # Sanitize filename to prevent path traversal (Requirement 7.2)
        try:
            safe_filename = sanitize_filename(file.filename)
        except SecurityError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid filename: {str(e)}'
            }), 400
        
        # Save uploaded file with secure filename
        input_path = app.config['UPLOAD_FOLDER'] / safe_filename
        file.save(str(input_path))
        
        # Check file size (Requirement 7.2 - file size limits)
        if not check_file_size(input_path):
            cleanup_temp_file(input_path)
            return jsonify({
                'success': False,
                'error': 'File size exceeds maximum allowed (50MB)'
            }), 413
        
        # Validate CSV format deeply (Requirement 7.2 - CSV format validation)
        is_valid, error_msg = validate_csv_format(input_path)
        if not is_valid:
            cleanup_temp_file(input_path)
            return jsonify({
                'success': False,
                'error': f'Invalid CSV file: {error_msg}'
            }), 400
        
        # Generate unique output filename
        output_filename = FileHandler.generate_unique_filename(
            Path(safe_filename).stem + '_screening',
            'xlsx'
        )
        output_path = app.config['OUTPUT_FOLDER'] / output_filename
        
        # Process the file (Requirement 7.2)
        extractor = ArticleExtractor(str(input_path), str(output_path))
        
        # Track progress
        records_processed = 0
        
        def progress_callback(current, total, message):
            nonlocal records_processed
            if "Extracted" in message:
                import re
                match = re.search(r'(\d+)', message)
                if match:
                    records_processed = int(match.group(1))
        
        # Execute extraction
        output_file = extractor.process(progress_callback=progress_callback)
        
        # Clean up uploaded file (Requirement 7.2 - temporary file cleanup)
        cleanup_temp_file(input_path)
        
        # Generate download link (Requirement 7.3)
        download_url = url_for('download_articles', filename=output_filename)
        
        return jsonify({
            'success': True,
            'records_count': records_processed,
            'filename': output_filename,
            'download_url': download_url
        })
        
    except InvalidCSVError as e:
        # Clean up on error
        if input_path:
            cleanup_temp_file(input_path)
        # Display detailed error message (Requirement 7.4, 1.5)
        return jsonify({
            'success': False,
            'error': 'Invalid CSV File',
            'details': str(e),
            'error_type': 'invalid_csv'
        }), 400
        
    except EmptyDataError as e:
        # Clean up on error
        if input_path:
            cleanup_temp_file(input_path)
        # Display detailed error message (Requirement 7.4, 1.4)
        return jsonify({
            'success': False,
            'error': 'Empty File',
            'details': str(e),
            'error_type': 'empty_data'
        }), 400
        
    except ArticleExtractorError as e:
        # Clean up on error
        if input_path:
            cleanup_temp_file(input_path)
        # Display detailed error message (Requirement 7.4)
        return jsonify({
            'success': False,
            'error': 'Extraction Error',
            'details': str(e),
            'error_type': 'extraction_error'
        }), 500
        
    except PermissionError as e:
        # Clean up on error
        if input_path:
            cleanup_temp_file(input_path)
        # Display detailed error message (Requirement 7.4, 3.5)
        return jsonify({
            'success': False,
            'error': 'Permission Denied',
            'details': str(e),
            'error_type': 'permission_error'
        }), 500
        
    except Exception as e:
        # Clean up on error
        if input_path:
            cleanup_temp_file(input_path)
        # Display detailed error message (Requirement 7.4)
        return jsonify({
            'success': False,
            'error': 'Unexpected Error',
            'details': f'An unexpected error occurred: {str(e)}',
            'error_type': 'unexpected_error'
        }), 500


@app.route('/download-articles/<filename>')
def download_articles(filename):
    """Serve generated Excel file for download.
    
    Downloads the Excel file containing extracted article data.
    Files are served with appropriate headers for download (Requirement 7.5).
    Implements path sanitization to prevent directory traversal attacks.
    
    Args:
        filename: Name of the Excel file to download
        
    Returns:
        File download response, or 404 if file not found
    """
    try:
        from bibtools.utils.security import sanitize_filename, validate_path_safety, SecurityError
        
        # Sanitize filename to prevent directory traversal
        try:
            safe_filename = sanitize_filename(filename)
        except SecurityError:
            return jsonify({
                'success': False,
                'error': 'Invalid filename'
            }), 400
        
        file_path = app.config['OUTPUT_FOLDER'] / safe_filename
        
        # Validate path is within allowed directory
        if not validate_path_safety(file_path, app.config['OUTPUT_FOLDER']):
            return jsonify({
                'success': False,
                'error': 'Invalid file path'
            }), 400
        
        if not file_path.exists():
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
        
        # Serve file with appropriate headers (Requirement 7.5)
        return send_file(
            file_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=safe_filename
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error downloading file: {str(e)}'
        }), 500


@app.route('/cleanup-articles/<filename>', methods=['POST'])
def cleanup_articles(filename):
    """Clean up a downloaded Excel file.
    
    Removes the specified Excel file from the output directory after download.
    This endpoint should be called by the client after download completes.
    Implements secure file deletion with path validation.
    
    Args:
        filename: Name of the file to clean up
        
    Returns:
        JSON response indicating success or failure
    """
    try:
        from bibtools.utils.security import sanitize_filename, validate_path_safety, cleanup_temp_file, SecurityError
        
        # Sanitize filename to prevent directory traversal
        try:
            safe_filename = sanitize_filename(filename)
        except SecurityError:
            return jsonify({
                'success': False,
                'error': 'Invalid filename'
            }), 400
        
        file_path = app.config['OUTPUT_FOLDER'] / safe_filename
        
        # Validate path is within allowed directory
        if not validate_path_safety(file_path, app.config['OUTPUT_FOLDER']):
            return jsonify({
                'success': False,
                'error': 'Invalid file path'
            }), 400
        
        # Clean up file securely
        cleanup_temp_file(file_path, ignore_errors=False)
        
        return jsonify({
            'success': True,
            'message': 'File cleaned up successfully'
        })
        
    except Exception as e:
        # Don't fail if cleanup fails - just log it
        return jsonify({
            'success': False,
            'error': f'Cleanup failed: {str(e)}'
        }), 500

if __name__ == '__main__':
    # Perform initial cleanup on startup
    perform_periodic_cleanup()
    
    # Run the development server
    app.run(debug=True, host='0.0.0.0', port=5000)



