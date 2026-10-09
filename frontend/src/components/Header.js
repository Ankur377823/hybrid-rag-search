/**
 * Header Component
 * Top application navigation bar, telemetry status & session controls.
 */

import { store } from '../state.js';

export class Header {
  constructor(container) {
    this.container = container;
  }

  render() {
    const user = store.user;
    const activeTab = store.activeTab;
    const health = store.health;
    const docCount = store.documents.length;

    this.container.innerHTML = `
      <header class="app-header">
        <div class="header-left">
          <div class="brand-text-name">HybridRAG</div>
        </div>

        <nav class="nav-segmented-control">
          <button id="navDocsTab" class="nav-segment-btn ${activeTab === 'documents' ? 'active' : ''}">
            Documents <span class="nav-count-badge">${docCount}</span>
          </button>
          <button id="navQueryTab" class="nav-segment-btn ${activeTab === 'query' ? 'active' : ''}">
            Query Studio
          </button>
        </nav>

        <div class="header-right">
          <div class="user-profile-menu">
            <div class="user-avatar-badge" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
            </div>
            <span class="user-email-display">${escapeHtml(user ? user.email : 'user')}</span>
            <button id="navSignOutBtn" class="btn-signout" aria-label="Sign out">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
              </svg>
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </header>
    `;

    this.attachEvents();
  }

  attachEvents() {
    const docsBtn = this.container.querySelector('#navDocsTab');
    const queryBtn = this.container.querySelector('#navQueryTab');
    const signOutBtn = this.container.querySelector('#navSignOutBtn');

    if (docsBtn) {
      docsBtn.addEventListener('click', (e) => {
        e.preventDefault();
        store.setActiveTab('documents');
      });
    }

    if (queryBtn) {
      queryBtn.addEventListener('click', (e) => {
        e.preventDefault();
        store.setActiveTab('query');
      });
    }

    if (signOutBtn) {
      signOutBtn.addEventListener('click', (e) => {
        e.preventDefault();
        store.setAuth('', null);
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
