document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('accessToken');
    const username = localStorage.getItem('username');

    // If no token, redirect to login page
    if (!token) {
        window.location.href = 'login.html';
        return;
    }

    const app = {
        token: token,
        username: username,
        fileList: [],

        init() {
            ui.displayUsername(this.username);
            this.addEventListeners();
            this.loadFiles();
        },

        addEventListeners() {
            // Logout button
            document.getElementById('logout-btn').addEventListener('click', () => {
                localStorage.removeItem('accessToken');
                localStorage.removeItem('username');
                window.location.href = 'login.html';
            });

            // Create folder button
            document.getElementById('create-folder-btn').addEventListener('click', () => {
                const folderName = prompt('Enter folder name:');
                if (folderName) {
                    this.createFolder(folderName);
                }
            });

            // File upload
            const fileUploadInput = document.getElementById('file-upload-input');
            fileUploadInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file) {
                    this.uploadFile(file);
                }
                // Reset input to allow uploading the same file again
                e.target.value = null;
            });

            // File actions (download/delete) using event delegation
            const fileListBody = document.getElementById('file-list-body');
            fileListBody.addEventListener('click', (e) => {
                const target = e.target;
                const row = target.closest('tr');
                if (!row) return;

                const fileId = row.dataset.fileId;

                if (target.classList.contains('download-btn') || target.classList.contains('file-name')) {
                    e.preventDefault();
                    this.downloadFile(fileId);
                } else if (target.classList.contains('delete-btn')) {
                    if (confirm('Are you sure you want to delete this file?')) {
                        this.deleteFile(fileId);
                    }
                }
            });
        },

        async loadFiles() {
            ui.showSpinner();
            try {
                const data = await api.getFiles(this.token);
                ui.hideSpinner();
                if (data.files) {
                    this.fileList = data.files;
                    ui.renderFileList(this.fileList);
                } else {
                    ui.showMessage(data.detail || 'Failed to load files.', 'error');
                }
            } catch (error) {
                ui.hideSpinner();
                ui.showMessage('An error occurred while loading files.', 'error');
            }
        },

        async uploadFile(file) {
            try {
                ui.updateUploadProgress(file.name, 0);
                const result = await api.uploadFile(file, this.token, (percentage) => {
                    ui.updateUploadProgress(file.name, percentage);
                });
                
                if (result.success) {
                    ui.showMessage('File uploaded successfully!', 'success');
                    this.loadFiles(); // Refresh file list
                } else {
                    ui.showMessage(result.message || 'Upload failed', 'error');
                }
            } catch (error) {
                ui.showMessage(error.detail || 'File upload failed.', 'error');
                ui.updateUploadProgress(file.name, 100); // Hide progress bar on error
            }
        },

        downloadFile(fileId) {
            const file = this.fileList.find(f => f.id == fileId);
            if (!file) return;

            ui.showMessage(`Preparing download for ${file.filename}...`, 'success');

            fetch(`${API_BASE_URL}/api/files/download/${fileId}`, {
                headers: { 'Authorization': `Bearer ${this.token}` }
            })
            .then(response => {
                if (!response.ok) {
                    // Try to read error message from JSON response
                    return response.json().then(err => { throw new Error(err.detail || 'Download failed.') });
                }
                return response.blob();
            })
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = file.filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();
                ui.clearMessage();
            })
            .catch(err => {
                ui.showMessage(err.message, 'error');
            });
        },

        async deleteFile(fileId) {
            try {
                const result = await api.deleteFile(fileId, this.token);
                if (result.success) {
                    ui.showMessage('File deleted successfully!', 'success');
                    this.loadFiles(); // Refresh file list
                } else {
                    ui.showMessage(result.message || 'Failed to delete file.', 'error');
                }
            } catch (error) {
                ui.showMessage(error.detail || 'An error occurred while deleting the file.', 'error');
            }
        },

        async createFolder(folderName) {
            try {
                const result = await api.createFolder(folderName, this.token);
                if (result.success) {
                    ui.showMessage('Folder created successfully!', 'success');
                    this.loadFiles(); // Refresh file list
                } else {
                    ui.showMessage(result.detail || 'Failed to create folder.', 'error');
                }
            } catch (error) {
                ui.showMessage(error.detail || 'An error occurred while creating the folder.', 'error');
            }
        }
    };

    app.init();
});