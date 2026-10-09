/**
 * AuthView Component
 * Secure developer sign-in interface without registration or hardcoded credentials.
 */

import { login } from '../api.js';
import { store } from '../state.js';

export class AuthView {
  constructor(container) {
    this.container = container;
    this.loading = false;
    this.error = '';
  }

  render() {
    this.container.innerHTML = `
      <div class="auth-viewport">
        <!-- Top Header Minimal Brand -->
        <header class="auth-header">
          <div class="brand-text-name">HybridRAG</div>
        </header>

        <!-- Main Auth Stage -->
        <main class="auth-stage">
          <div class="auth-card">
            <div class="auth-card-header">
              <span class="auth-tag">Sign In</span>
            </div>

            <form id="authForm" class="auth-form">
              ${
                this.error
                  ? `
                <div class="alert-box alert-error">
                  <span>${escapeHtml(this.error)}</span>
                </div>
              `
                  : ''
              }

              <div class="form-group">
                <label for="terminalEmail" class="form-label">Email Address</label>
                <div class="input-wrap">
                  <input
                    type="email"
                    id="terminalEmail"
                    class="form-control"
                    placeholder="admin@domain.com"
                    required
                    autocomplete="email"
                  >
                </div>
              </div>

              <div class="form-group">
                <label for="terminalPassword" class="form-label">Password</label>
                <div class="input-wrap pwd-input-wrap">
                  <input
                    type="password"
                    id="terminalPassword"
                    class="form-control"
                    placeholder="••••••••••••"
                    required
                    autocomplete="current-password"
                  >
                  <button type="button" id="togglePasswordBtn" class="pwd-visibility-toggle" title="Show / Hide Password" aria-label="Toggle password visibility">
                    <svg id="eyeIcon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                  </button>
                </div>
              </div>

              <div class="auth-actions-group">
                <button type="submit" id="submitAuthBtn" class="btn btn-primary btn-block" ${this.loading ? 'disabled' : ''}>
                  ${this.loading ? '<span class="spinner-sm"></span> Authenticating...' : 'Sign In'}
                </button>
              </div>
            </form>
          </div>
        </main>
      </div>
    `;

    this.attachEvents();
  }

  attachEvents() {
    const form = this.container.querySelector('#authForm');
    const togglePasswordBtn = this.container.querySelector('#togglePasswordBtn');
    const pwdInput = this.container.querySelector('#terminalPassword');

    if (togglePasswordBtn && pwdInput) {
      togglePasswordBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const isPassword = pwdInput.type === 'password';
        pwdInput.type = isPassword ? 'text' : 'password';
        togglePasswordBtn.style.color = isPassword ? '#ffffff' : 'var(--text-dim)';
      });
    }

    if (form) {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = this.container.querySelector('#terminalEmail').value.trim();
        const password = this.container.querySelector('#terminalPassword').value;

        this.loading = true;
        this.error = '';
        this.render();

        try {
          const data = await login(email, password);
          store.setAuth(data.access_token, data.user);
        } catch (err) {
          this.error = err.message || 'Authentication failed. Please check credentials.';
          this.loading = false;
          this.render();
        }
      });
    }
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>'"]/g, 
    (t) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[t] || t)
  );
}
