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
            <span class="user-email-display">${escapeHtml(user ? user.email : 'user')}</span>
            <button id="navSignOutBtn" class="btn-signout" title="Sign out">
              Sign Out
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
