// JavaScript for CSV to BibTeX Converter Web Interface

document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('csv_file');
    const fileLabel = document.getElementById('fileLabel');
    const convertBtn = document.getElementById('convertBtn');
    const progressSection = document.getElementById('progressSection');
    const errorSection = document.getElementById('errorSection');
    const resultsSection = document.getElementById('resultsSection');
    const uploadSection = document.querySelector('.upload-section');

    // File input change handler
    fileInput.addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            const file = e.target.files[0];
            const fileName = file.name;
            
            // Client-side validation (Requirement 8.4)
            const validation = validateFile(file);
            if (!validation.valid) {
                showError(validation.error);
                fileInput.value = '';
                fileLabel.textContent = 'Choose CSV file or drag and drop';
                return;
            }
            
            fileLabel.textContent = fileName;
            fileLabel.style.color = '#48bb78'; // Green to indicate valid file
        }
    });

    // Drag and drop handlers
    const fileLabelElement = document.querySelector('.file-label');
    
    fileLabelElement.addEventListener('dragover', function(e) {
        e.preventDefault();
        fileLabelElement.classList.add('drag-over');
    });

    fileLabelElement.addEventListener('dragleave', function(e) {
        e.preventDefault();
        fileLabelElement.classList.remove('drag-over');
    });

    fileLabelElement.addEventListener('drop', function(e) {
        e.preventDefault();
        fileLabelElement.classList.remove('drag-over');
        
        if (e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            
            // Client-side validation
            const validation = validateFile(file);
            if (!validation.valid) {
                showError(validation.error);
                fileInput.value = '';
                fileLabel.textContent = 'Choose CSV file or drag and drop';
                return;
            }
            
            fileInput.files = e.dataTransfer.files;
            fileLabel.textContent = file.name;
            fileLabel.style.color = '#48bb78'; // Green to indicate valid file
        }
    });

    // Form submission handler
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Validate file is selected
        if (!fileInput.files || fileInput.files.length === 0) {
            showError('Please select a file to upload');
            return;
        }

        // Final validation before upload
        const validation = validateFile(fileInput.files[0]);
        if (!validation.valid) {
            showError(validation.error);
            return;
        }

        // Disable button to prevent double submission
        convertBtn.disabled = true;
        convertBtn.textContent = 'Converting...';

        // Show progress indicator (Requirement 8.4)
        showProgress();

        // Create FormData and submit
        const formData = new FormData();
        formData.append('csv_file', fileInput.files[0]);

        // Send request to server
        fetch('/convert', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Conversion failed');
                }).catch(() => {
                    // If JSON parsing fails, throw generic error
                    throw new Error(`Server error: ${response.status} ${response.statusText}`);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                showResults(data);
            } else {
                showError(data.error || 'Conversion failed');
            }
        })
        .catch(error => {
            showError(error.message || 'An error occurred during conversion');
        })
        .finally(() => {
            // Re-enable button
            convertBtn.disabled = false;
            convertBtn.textContent = 'Convert to BibTeX';
        });
    });
});

/**
 * Validate file before upload (Requirement 8.4)
 * @param {File} file - The file to validate
 * @returns {Object} - Validation result with valid flag and error message
 */
function validateFile(file) {
    // Check if file exists
    if (!file) {
        return { valid: false, error: 'No file selected' };
    }

    // Check file extension
    const fileName = file.name.toLowerCase();
    if (!fileName.endsWith('.csv')) {
        return { valid: false, error: 'Invalid file type. Please upload a CSV file.' };
    }

    // Check file size (16MB limit)
    const maxSize = 16 * 1024 * 1024; // 16MB in bytes
    if (file.size > maxSize) {
        const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
        return { 
            valid: false, 
            error: `File too large (${sizeMB}MB). Maximum file size is 16MB.` 
        };
    }

    // Check if file is empty
    if (file.size === 0) {
        return { valid: false, error: 'File is empty. Please select a valid CSV file.' };
    }

    return { valid: true };
}

/**
 * Show progress indicator during conversion
 */
function showProgress() {
    document.getElementById('uploadForm').style.display = 'none';
    document.getElementById('errorSection').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('progressSection').style.display = 'block';
}

/**
 * Show error message to user (Requirement 4.5)
 */
function showError(message) {
    const fileLabel = document.querySelector('.file-label');
    const convertBtn = document.getElementById('convertBtn');
    
    // Add error visual feedback
    fileLabel.classList.add('file-error');
    setTimeout(() => fileLabel.classList.remove('file-error'), 3000);
    
    // Re-enable button
    convertBtn.disabled = false;
    convertBtn.textContent = 'Convert to BibTeX';
    
    document.getElementById('uploadForm').style.display = 'block';
    document.getElementById('progressSection').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
    document.getElementById('errorSection').style.display = 'block';
    document.getElementById('errorMessage').textContent = message;
}

/**
 * Show conversion results with download links (Requirement 4.3)
 */
function showResults(data) {
    document.getElementById('uploadForm').style.display = 'none';
    document.getElementById('progressSection').style.display = 'none';
    document.getElementById('errorSection').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'block';

    // Update entry count
    document.getElementById('entryCount').textContent = data.entries_count;

    // Generate download links
    const downloadList = document.getElementById('downloadList');
    downloadList.innerHTML = '';

    // Add "Download All" button if multiple files
    if (data.files.length > 1) {
        const downloadAllBtn = document.createElement('button');
        downloadAllBtn.className = 'btn btn-download-all';
        downloadAllBtn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 8px; vertical-align: middle;">
                <polyline points="8 17 12 21 16 17"></polyline>
                <line x1="12" y1="12" x2="12" y2="21"></line>
                <path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.29"></path>
            </svg>
            Download All Files (ZIP)
        `;
        downloadAllBtn.onclick = () => downloadAllFiles(data.files);
        downloadList.appendChild(downloadAllBtn);
        
        // Add separator
        const separator = document.createElement('div');
        separator.style.margin = '20px 0';
        separator.style.borderTop = '1px solid #e2e8f0';
        downloadList.appendChild(separator);
    }

    data.files.forEach(file => {
        const downloadItem = document.createElement('div');
        downloadItem.className = 'download-item';
        
        const filename = document.createElement('span');
        filename.className = 'download-filename';
        filename.textContent = file.filename;
        
        const downloadLink = document.createElement('a');
        downloadLink.className = 'download-link';
        downloadLink.href = file.url;
        downloadLink.textContent = 'Download';
        downloadLink.download = file.filename;
        
        // Don't auto-cleanup - let files persist for multiple downloads
        // Users can manually cleanup or files will be overwritten on next conversion
        
        downloadItem.appendChild(filename);
        downloadItem.appendChild(downloadLink);
        downloadList.appendChild(downloadItem);
    });

    // Show warnings if any
    if (data.warnings && data.warnings.length > 0) {
        const warningsSection = document.getElementById('warningsSection');
        const warningsList = document.getElementById('warningsList');
        
        warningsList.innerHTML = '';
        data.warnings.forEach(warning => {
            const li = document.createElement('li');
            li.textContent = warning;
            warningsList.appendChild(li);
        });
        
        warningsSection.style.display = 'block';
    } else {
        document.getElementById('warningsSection').style.display = 'none';
    }
}

/**
 * Download all files as a ZIP archive
 */
function downloadAllFiles(files) {
    const filenames = files.map(f => f.filename);
    
    fetch('/download-all', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ filenames: filenames })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to create ZIP file');
        }
        return response.blob();
    })
    .then(blob => {
        // Create download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filenames[0].replace('_fixed', '').replace('_part1', '') + '_bibtex_files.zip';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    })
    .catch(error => {
        alert('Error downloading files: ' + error.message);
    });
}

/**
 * Reset form to initial state
 */
function resetForm() {
    const uploadForm = document.getElementById('uploadForm');
    const fileLabel = document.getElementById('fileLabel');
    const convertBtn = document.getElementById('convertBtn');
    
    uploadForm.reset();
    fileLabel.textContent = 'Choose CSV file or drag and drop';
    fileLabel.style.color = ''; // Reset color
    convertBtn.disabled = false;
    convertBtn.textContent = 'Convert to BibTeX';
    
    uploadForm.style.display = 'block';
    document.getElementById('progressSection').style.display = 'none';
    document.getElementById('errorSection').style.display = 'none';
    document.getElementById('resultsSection').style.display = 'none';
}

/**
 * Clean up downloaded file from server
 */
function cleanupFile(filename) {
    fetch(`/cleanup/${filename}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        // Silently handle cleanup - don't notify user
        console.log('File cleanup:', data.success ? 'success' : 'failed');
    })
    .catch(error => {
        // Silently handle cleanup errors
        console.log('Cleanup error:', error);
    });
}
