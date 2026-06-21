/**
 * Authentication Module - Handles login and session management
 */
class Auth {
    constructor() {
        this.userEmail = localStorage.getItem('user_email') || '';
        this.userId = localStorage.getItem('user_id') || '';
    }
    
    /**
     * Handle form submission for login
     */
    async handleLogin(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData.entries());
        
        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            if (response.ok) {
                const result = await response.json();
                this.userEmail = data.email;
                this.userId = result.userId;
                localStorage.setItem('user_email', data.email);
                localStorage.setItem('user_id', result.userId);
                console.log('Logged in:', { email: this.userEmail, userId: this.userId });
            }
        } catch (error) {
            console.error('Login error:', error);
        }
    }
}

// Initialize auth handler when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('login-form');
    if (form && !this.userEmail) {
        new Auth().handleLogin(form);
    } else if (!this.userEmail) {
        // Auto-fill email field
        const emailInput = form.querySelector('[name="email"]');
        if (emailInput) emailInput.value = this.userEmail;
    }
});
