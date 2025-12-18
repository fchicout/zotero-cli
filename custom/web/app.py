"""Flask web application for CSV to BibTeX conversion.

This module provides a simple web interface for uploading Springer CSV files
and downloading the converted BibTeX files with fixed author names.
"""

from flask import Flask, request, send_file, render_template, jsonify, url_for
from pathlib import Path
from werkzeug.utils import secure_filename
import os
import tempfile

from custom.core.csv_converter import CSVConverter
from custom.core.author_fixer import AuthorFixer
from custom.core.models import ConversionResult


# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size (Requirement 8.5)

# Get the project root directory (2 levels up from this file)
PROJECT_ROOT = Path(__file__).parent.parent.parent
app.config['UPLOAD_FOLDER'] = PROJECT_ROOT / 'data' / 'temp'
app.config['OUTPUT_FOLDER'] = PROJECT_ROOT / 'data' / 'output'

# Ensure directories exist
app.config['UPLOAD_FOLDER'].mkdir(parents=True, exist_ok=True)
app.config['OUTPUT_FOLDER'].mkdir(parents=True, exist_ok=True)


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
    """Render the main upload page.
    
    Displays the file upload form where users can select a CSV file
    for conversion (Requirement 4.1).
    
    Returns:
        Rendered HTML template for the upload page
    """
    return render_template('index.html')


@app.route('/convert', methods=['POST'])
def convert():
    """Handle file upload and conversion.
    
    Processes the uploaded CSV file through the conversion pipeline:
    1. Validates the uploaded file
    2. Converts CSV to BibTeX
    3. Fixes author names
    4. Returns download links for the generated files
    
    This endpoint implements Requirements 4.1, 4.2, 4.3, 4.4.
    
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


if __name__ == '__main__':
    # Run the development server
    app.run(debug=True, host='0.0.0.0', port=5000)
