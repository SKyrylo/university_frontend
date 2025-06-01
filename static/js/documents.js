// Global variables
let currentDeleteId = null;

document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const uploadForm = document.getElementById('uploadForm');
    const tableBody = document.getElementById('documentsTableBody');
    const modal = document.getElementById('deleteModal');
    const confirmDeleteButton = document.getElementById('confirmDelete');

    // Load existing documents
    loadDocuments();

    // Drag and drop handlers
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        handleFiles(files);
    });

    // File input change handler
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    // Modal confirm button handler
    confirmDeleteButton.addEventListener('click', () => {
        if (currentDeleteId) {
            deleteDocument(currentDeleteId);
            closeModal();
        }
    });

    // Handle file upload
    function handleFiles(files) {
        const file = files[0]; // Handle first file only
        if (!file) return;

        // Check file type
        if (file.type !== 'application/pdf') {
            alert('Please upload only PDF files');
            return;
        }

        // Check file size (16MB = 16 * 1024 * 1024 bytes)
        if (file.size > 16 * 1024 * 1024) {
            alert('File size must be less than 16MB');
            return;
        }

        uploadFile(file);
    }

    // Upload file to server
    function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        // Show loading state
        dropZone.classList.add('loading');

        fetch('/api/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                loadDocuments(); // Refresh table
                fileInput.value = ''; // Clear input
            } else {
                throw new Error(data.error || 'Upload failed');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Upload failed: ' + error.message);
        })
        .finally(() => {
            dropZone.classList.remove('loading');
        });
    }

    // Load documents from server
    function loadDocuments() {
        fetch('/api/documents')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(documents => {
            tableBody.innerHTML = '';
            documents.forEach(doc => {
                const row = createTableRow(doc);
                tableBody.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Failed to load documents: ' + error.message);
        });
    }

    // Create table row for document
    function createTableRow(doc) {
        const row = document.createElement('tr');
        const date = new Date(doc.upload_date);
        const formattedDate = date.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        row.innerHTML = `
            <td>${doc.name}</td>
            <td>${formatFileSize(doc.size)}</td>
            <td>${formattedDate}</td>
            <td>
                <button class="action-button delete-button" onclick="showDeleteModal('${doc.id}')">
                    Delete
                </button>
            </td>
        `;
        return row;
    }

    // Format file size
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Make loadDocuments available globally
    window.loadDocuments = loadDocuments;
});

// Show delete confirmation modal
function showDeleteModal(id) {
    currentDeleteId = id;
    const modal = document.getElementById('deleteModal');
    modal.classList.add('show');
}

// Close modal
function closeModal() {
    const modal = document.getElementById('deleteModal');
    modal.classList.remove('show');
    currentDeleteId = null;
}

// Delete document
function deleteDocument(id) {
    fetch(`/api/documents/${id}`, {
        method: 'DELETE'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            loadDocuments(); // Refresh table
        } else {
            throw new Error(data.error || 'Delete failed');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Delete failed: ' + error.message);
    });
} 