document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login');
    const registerForm = document.getElementById('register');
    const showRegisterLink = document.getElementById('show-register');
    const showLoginLink = document.getElementById('show-login');
    const loginFormContainer = document.getElementById('login-form');
    const registerFormContainer = document.getElementById('register-form');
    const messageBox = document.getElementById('message-box');

    // Check if user is already logged in
    const token = localStorage.getItem('accessToken');
    if (token) {
        window.location.href = 'index.html';
    }

    // Toggle between login and register forms
    showRegisterLink.addEventListener('click', (e) => {
        e.preventDefault();
        loginFormContainer.style.display = 'none';
        registerFormContainer.style.display = 'block';
        clearMessages();
    });

    showLoginLink.addEventListener('click', (e) => {
        e.preventDefault();
        registerFormContainer.style.display = 'none';
        loginFormContainer.style.display = 'block';
        clearMessages();
    });

    // Handle login form submission
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = e.target.username.value;
        const password = e.target.password.value;

        try {
            const data = await api.login(username, password);
            if (data.access_token) {
                localStorage.setItem('accessToken', data.access_token);
                localStorage.setItem('username', data.username);
                window.location.href = 'index.html';
            } else {
                showMessage(data.detail || 'Login failed.', 'error');
            }
        } catch (error) {
            console.error('Login API call failed:', error);
            showMessage('Login failed. Check browser console (F12) for details.', 'error');
        }
    });

    // Handle register form submission
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = e.target.username.value;
        const email = e.target.email.value;
        const password = e.target.password.value;

        try {
            const data = await api.register(username, email, password);
            if (data.access_token) {
                showMessage('Registration successful! Please log in.', 'success');
                // Switch to login form
                showLoginLink.click();
            } else {
                showMessage(data.detail || 'Registration failed.', 'error');
            }
        } catch (error) {
            console.error('Register API call failed:', error);
            showMessage('Registration failed. Check browser console (F12) for details.', 'error');
        }
    });

    function showMessage(message, type) {
        messageBox.textContent = message;
        messageBox.className = `message-box ${type}`;
    }

    function clearMessages() {
        messageBox.textContent = '';
        messageBox.className = 'message-box';
    }
});
