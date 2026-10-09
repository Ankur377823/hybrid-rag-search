/**
 * AuthView Component
 * High-performance, enterprise-grade sign-in console.
 * Strictly professional typography and iconography (no emojis).
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
      <div class="enterprise-auth-wrapper">
        <div class="enterprise-auth-container">
          
          <!-- Left Column: Enterprise Platform Overview -->
          <section class="auth-showcase">
            <header class="showcase-header">
              <div class="brand-lockup">
                <div class="brand-logo-symbol" aria-hidden="true">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                    <polyline points="2 17 12 22 22 17"></polyline>
                    <polyline points="2 12 12 17 22 12"></polyline>
                  </svg>
                </div>
                <div class="brand-meta">
                  <span class="brand-name">HybridRAG</span>
                  <span class="brand-badge">Enterprise Console</span>
                </div>
              </div>
            </header>

            <div class="showcase-body">
              <div class="showcase-tag">Version 0.2.0 • Production Ready</div>
              <h1 class="showcase-title">Production-Grade Hybrid Search &amp; Grounded Retrieval</h1>
              <p class="showcase-description">
                High-throughput enterprise retrieval infrastructure integrating dense neural vectors, 
                lexical BM25 ranking, and real-time LLM-as-judge citation verification.
              </p>

              <div class="architecture-specs-list">
                <article class="spec-card">
                  <div class="spec-icon" aria-hidden="true">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="11" cy="11" r="8"></circle>
                      <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                    </svg>
                  </div>
                  <div class="spec-content">
                    <h2 class="spec-heading">Dual-Index Fusion Engine</h2>
                    <p class="spec-detail">
                      Reciprocal Rank Fusion (RRF, k=60) merges cosine semantic embeddings and BM25Okapi matches without requiring score calibration.
                    </p>
                  </div>
                </article>

                <article class="spec-card">
                  <div class="spec-icon" aria-hidden="true">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                      <polyline points="9 12 11 14 15 10"></polyline>
                    </svg>
                  </div>
                  <div class="spec-content">
                    <h2 class="spec-heading">Automated Citation Verification</h2>
                    <p class="spec-detail">
                      Every claim is audited against retrieved chunks via an asynchronous LLM-as-judge. Queries below confidence threshold trigger a calibrated refusal.
                    </p>
                  </div>
                </article>

                <article class="spec-card">
                  <div class="spec-icon" aria-hidden="true">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>
                      <rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>
                      <line x1="6" y1="6" x2="6.01" y2="6"></line>
                      <line x1="6" y1="18" x2="6.01" y2="18"></line>
                    </svg>
                  </div>
                  <div class="spec-content">
                    <h2 class="spec-heading">Multi-Tenant PostgreSQL Isolation</h2>
                    <p class="spec-detail">
                      Row-level tenant security, SHA-256 deduplication for zero-cost skips, and atomic vector store swaps for zero-downtime document updates.
                    </p>
                  </div>
                </article>
              </div>
            </div>

            <footer class="showcase-footer">
              <div class="status-indicator">
                <span class="status-pulse-dot" aria-hidden="true"></span>
                <span class="status-label">System Operational</span>
                <span class="status-divider">•</span>
                <span class="status-detail">PostgreSQL Active</span>
                <span class="status-divider">•</span>
                <span class="status-detail">Rate-Limiting Enforced</span>
              </div>
            </footer>
          </section>

          <!-- Right Column: Sign-In Console -->
          <section class="auth-panel">
            <div class="auth-box">
              <div class="auth-box-header">
                <h2 class="auth-box-title">Sign In to Console</h2>
                <p class="auth-box-subtitle">
                  Authenticate with administrator credentials to manage documents and run grounded retrieval queries.
                </p>
              </div>

              <form id="authForm" class="auth-panel-form" novalidate>
                ${
                  this.error
                    ? `
                  <div class="auth-alert-banner alert-error" role="alert">
                    <div class="alert-icon-wrap" aria-hidden="true">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
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
                  <div class="field-label-row">
                    <label for="terminalEmail" class="field-label">Email Address</label>
                    <span class="field-constraint-tag">Required</span>
                  </div>
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
                      placeholder="admin@hybridrag.io"
                      required
                      autocomplete="email"
                    >
                  </div>
                </div>

                <div class="auth-field-group">
                  <div class="field-label-row">
                    <label for="terminalPassword" class="field-label">Password</label>
                    <span class="field-constraint-tag">Required</span>
                  </div>
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
                      placeholder="••••••••••••"
                      required
                      autocomplete="current-password"
                    >
                    <button type="button" id="togglePasswordBtn" class="visibility-toggle-btn" title="Toggle password visibility" aria-label="Toggle password visibility">
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
                        ? '<span class="loading-spinner-ring" aria-hidden="true"></span> Authenticating...'
                        : 'Sign In to Console'
                    }
                  </button>
                </div>
              </form>

              <div class="auth-deployment-hint">
                <div class="hint-header">
                  <span class="hint-badge">Access Configuration</span>
                </div>
                <p class="hint-text">
                  Sign in using credentials configured via <code>RAG_ADMIN_EMAIL</code> and <code>RAG_ADMIN_PASSWORD</code> in your deployment environment variables.
                </p>
              </div>

              <div class="auth-security-footer">
                <span>Encrypted JWT Sessions</span>
                <span class="security-sep">•</span>
                <span>Audit Logged</span>
                <span class="security-sep">•</span>
                <span>SHA-256 Storage</span>
              </div>
            </div>
          </section>

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

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>'"]/g, 
    (t) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[t] || t)
  );
}
