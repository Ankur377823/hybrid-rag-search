/**
 * AuthView Component
 * High-performance, minimalist enterprise sign-in console.
 * Clean, professional presentation without emojis or model names.
 */

import { login } from '../api.js';
import { store } from '../state.js';
import { escapeHtml } from '../utils.js';

export class AuthView {
  constructor(container) {
    this.container = container;
    this.loading = false;
    this.error = '';
  }

  render() {
    this.container.innerHTML = `
      <div class="enterprise-auth-wrapper">
        <div class="enterprise-auth-card">
          
          <div class="auth-brand-center">
            <div class="auth-logo-badge" aria-hidden="true">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                <polyline points="2 17 12 22 22 17"></polyline>
                <polyline points="2 12 12 17 22 12"></polyline>
              </svg>
            </div>
            <div class="auth-brand-title">HybridRAG</div>
            <div class="auth-console-pill">Enterprise Console</div>
          </div>

          <div class="auth-card-body">
            <div class="auth-box-header">
              <h2 class="auth-box-title">Sign In</h2>
              <p class="auth-box-subtitle">Enter your administrator credentials to continue.</p>
            </div>

            <form id="authForm" class="auth-panel-form" novalidate>
              ${
                this.error
                  ? `
                <div class="auth-alert-banner alert-error" role="alert">
                  <div class="alert-icon-wrap" aria-hidden="true">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10"></circle>
                      <line x1="12" y1="8" x2="12" y2="12"></line>
                      <line x1="12" y1="16" x2="12.01" y2="16"></line>
                    </svg>
                  </div>
                  <span class="alert-message">${escapeHtml(this.error)}</span>
                </div>
              `
                  : ''
              }

              <div class="auth-field-group">
                <label for="terminalEmail" class="field-label">Email</label>
                <div class="field-input-wrapper">
                  <span class="input-adornment-icon" aria-hidden="true">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                      <polyline points="22,6 12,13 2,6"></polyline>
                    </svg>
                  </span>
                  <input
                    type="email"
                    id="terminalEmail"
                    class="field-input-control"
                    placeholder="name@organization.com"
                    required
                    autocomplete="email"
                  >
                </div>
              </div>

              <div class="auth-field-group">
                <label for="terminalPassword" class="field-label">Password</label>
                <div class="field-input-wrapper password-field-wrap">
                  <span class="input-adornment-icon" aria-hidden="true">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                      <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                    </svg>
                  </span>
                  <input
                    type="password"
                    id="terminalPassword"
                    class="field-input-control"
                    placeholder="••••••••"
                    required
                    autocomplete="current-password"
                  >
                  <button type="button" id="togglePasswordBtn" class="visibility-toggle-btn" aria-label="Toggle password visibility">
                    <svg id="eyeIcon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                  </button>
                </div>
              </div>

              <div class="auth-submission-row">
                <button type="submit" id="submitAuthBtn" class="auth-submit-btn" ${this.loading ? 'disabled' : ''}>
                  ${
                    this.loading
                      ? '<span class="loading-spinner-ring" aria-hidden="true"></span> Signing in...'
                      : 'Sign In'
                  }
                </button>
              </div>
            </form>
          </div>

          <div class="auth-card-footer">
            <div class="auth-trust-item">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
              </svg>
              <span>SOC-2 Type II</span>
            </div>
            <span class="footer-dot">•</span>
            <div class="auth-trust-item">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
              </svg>
              <span>Tenant Isolation</span>
            </div>
            <span class="footer-dot">•</span>
            <div class="auth-trust-item">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 14 14"></polyline>
              </svg>
              <span>Audit Logging</span>
            </div>
          </div>

        </div>
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
        togglePasswordBtn.classList.toggle('active', isPassword);
      });
    }

    if (form) {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = this.container.querySelector('#terminalEmail').value.trim();
        const password = this.container.querySelector('#terminalPassword').value;

        if (!email || !password) {
          this.error = 'Please provide both email address and password.';
          this.render();
          return;
        }

        this.loading = true;
        this.error = '';
        this.render();

        try {
          const data = await login(email, password);
          store.setAuth(data.access_token, data.user);
        } catch (err) {
          this.error = err.message || 'Authentication failed. Please verify credentials.';
          this.loading = false;
          this.render();
        }
      });
    }
  }
}
