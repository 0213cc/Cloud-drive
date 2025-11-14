const API_BASE_URL = 'http://ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com:8000';

const api = {
    /**
     * Registers a new user.
     * @param {string} username
     * @param {string} email
     * @param {string} password
     * @returns {Promise<object>} The server response.
     */
    async register(username, email, password) {
        const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password }),
        });
        return response.json();
    },

    /**
     * Logs in a user.
     * @param {string} username
     * @param {string} password
     * @returns {Promise<object>} The server response with token info.
     */
    async login(username, password) {
        const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        return response.json();
    },

    /**
     * Fetches the list of files from the server.
     * @param {string} token - The JWT access token.
     * @returns {Promise<object>} The list of files.
     */
    async getFiles(token) {
        const response = await fetch(`${API_BASE_URL}/api/files/list`, {
            headers: { 'Authorization': `Bearer ${token}` },
        });
        return response.json();
    },

    /**
     * Creates a new folder.
     * @param {string} path - The full path of the new folder.
     * @param {string} token - The JWT access token.
     * @returns {Promise<object>} The server response.
     */
    async createFolder(path, token) {
        const response = await fetch(`${API_BASE_URL}/api/files/mkdir?path=${encodeURIComponent(path)}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` },
        });
        return response.json();
    },

    /**
     * Deletes a file from the server.
     * @param {number} fileId - The ID of the file to delete.
     * @param {string} token - The JWT access token.
     * @returns {Promise<object>} The server response.
     */
    async deleteFile(fileId, token) {
        const response = await fetch(`${API_BASE_URL}/api/files/delete/${fileId}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` },
        });
        return response.json();
    },

    /**
     * Provides a URL to download a file.
     * @param {number} fileId - The ID of the file to download.
     * @param {string} token - The JWT access token.
     * @returns {string} The download URL.
     */
    getDownloadUrl(fileId, token) {
        return `${API_BASE_URL}/api/files/download/${fileId}?token=${token}`; // A simple way to pass token for direct download
    },

    /**
     * Uploads a file to the server.
     * @param {File} file - The file to upload.
     * @param {string} token - The JWT access token.
     * @param {function} onProgress - Callback function for upload progress.
     * @returns {Promise<object>} The server response.
     */
    uploadFile(file, token, onProgress) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            const formData = new FormData();
            formData.append('file', file);

            xhr.open('POST', `${API_BASE_URL}/api/files/upload`, true);
            xhr.setRequestHeader('Authorization', `Bearer ${token}`);

            xhr.upload.onprogress = (event) => {
                if (event.lengthComputable) {
                    const percentComplete = (event.loaded / event.total) * 100;
                    onProgress(percentComplete);
                }
            };

            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(JSON.parse(xhr.responseText));
                } else {
                    reject(JSON.parse(xhr.responseText));
                }
            };

            xhr.onerror = () => {
                reject({ detail: 'Upload failed due to a network error.' });
            };

            xhr.send(formData);
        });
    }
};
