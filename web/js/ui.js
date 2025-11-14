const ui = {
    fileListBody: document.getElementById('file-list-body'),
    loadingSpinner: document.getElementById('loading-spinner'),
    usernameDisplay: document.getElementById('username-display'),
    messageBox: document.getElementById('message-box'),
    uploadProgressContainer: document.getElementById('upload-progress-container'),
    uploadFilename: document.getElementById('upload-filename'),
    progressBarFill: document.getElementById('progress-bar-fill'),

    /**
     * Shows the loading spinner and clears the file list.
     */
    showSpinner() {
        if (this.loadingSpinner) {
            this.loadingSpinner.style.display = 'block';
        }
        if (this.fileListBody) {
            this.fileListBody.innerHTML = ''; // Clear the table while loading
        }
    },

    /**
     * Hides the loading spinner.
     */
    hideSpinner() {
        if (this.loadingSpinner) {
            this.loadingSpinner.style.display = 'none';
        }
    },

    /**
     * Displays the username in the header.
     * @param {string} username
     */
    displayUsername(username) {
        if (this.usernameDisplay) {
            this.usernameDisplay.textContent = `Welcome, ${username}`;
        }
    },

    /**
     * Renders the list of files in the table.
     * @param {Array<object>} files - The array of file objects.
     */
    renderFileList(files) {
        if (!this.fileListBody) return;

        this.fileListBody.innerHTML = ''; // Clear existing list

        if (files.length === 0) {
            this.fileListBody.innerHTML = '<tr><td colspan="4" style="text-align: center;">No files found.</td></tr>';
            return;
        }

        files.forEach(file => {
            const row = document.createElement('tr');
            row.dataset.fileId = file.id;

            const isDirectory = file.is_directory;
            const icon = isDirectory ? '📁' : '📄';
            const size = isDirectory ? '-' : this.formatFileSize(file.size);
            const modified = new Date(file.updated_at).toLocaleString();

            row.innerHTML = `
                <td>${icon} <a href="#" class="file-name" data-file-id="${file.id}">${file.filename}</a></td>
                <td>${size}</td>
                <td>${modified}</td>
                <td>
                    <button class="action-btn download-btn" title="Download">⬇️</button>
                    <button class="action-btn delete-btn" title="Delete">🗑️</button>
                </td>
            `;
            this.fileListBody.appendChild(row);
        });
    },

    /**
     * Formats file size into a human-readable string.
     * @param {number} bytes - The file size in bytes.
     * @returns {string}
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    /**
     * Shows a message to the user.
     * @param {string} message
     * @param {string} type - 'success' or 'error'.
     */
    showMessage(message, type) {
        if (this.messageBox) {
            this.messageBox.textContent = message;
            this.messageBox.className = `message-box ${type}`;
            setTimeout(() => this.clearMessage(), 5000);
        }
    },

    /**
     * Clears the message box.
     */
    clearMessage() {
        if (this.messageBox) {
            this.messageBox.textContent = '';
            this.messageBox.className = 'message-box';
        }
    },

    /**
     * Shows and updates the upload progress bar.
     * @param {string} filename
     * @param {number} percentage - The upload percentage (0-100).
     */
    updateUploadProgress(filename, percentage) {
        if (this.uploadProgressContainer) {
            this.uploadProgressContainer.style.display = 'block';
            this.uploadFilename.textContent = filename;
            this.progressBarFill.style.width = `${percentage}%`;

            if (percentage >= 100) {
                setTimeout(() => {
                    this.uploadProgressContainer.style.display = 'none';
                }, 1000);
            }
        }
    }
};
