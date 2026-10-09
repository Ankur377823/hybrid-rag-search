/**
 * Application Entry Point & Root Component Controller
 * 
 * Strictly modular architecture:
 * - Unauthenticated: Renders AuthView directly (minimalist terminal aesthetic)
 * - Authenticated: Renders Header, DocumentsView / QueryView, and UpdateModal
 */

import { getHealth, listDocuments } from './api.js';
import { store } from './state.js';
import { AuthView } from './components/AuthView.js';
import { Header } from './components/Header.js';
import { DocumentsView } from './components/DocumentsView.js';
import { QueryView } from './components/QueryView.js';
import { UpdateModal } from './components/UpdateModal.js';

class App {
  constructor(rootEl) {
    this.root = rootEl;
    this.currentMode = null; // 'auth' | 'app'
    this.authComponent = null;
    this.headerComponent = null;
    this.docsComponent = null;
    this.queryComponent = null;
    this.modalComponent = null;

    // Subscribe to state updates
    store.subscribe((state) => this.handleStateChange(state));
  }

  async init() {
    this.render();
    await this.refreshHealth();
    if (store.token) {
      await this.refreshDocuments();
    }
  }

  async refreshHealth() {
    try {
      const h = await getHealth();
      store.setHealth(h);
    } catch {
      store.setHealth({ status: 'offline', database: 'disconnected', chunks: 0 });
    }
  }

  async refreshDocuments() {
    try {
      const docs = await listDocuments();
      store.setDocuments(docs);
    } catch (err) {
      if (err.message && err.message.includes('401')) {
        store.setAuth('', null);
      }
    }
  }

  handleStateChange(state) {
    const shouldBeMode = state.token ? 'app' : 'auth';

    if (shouldBeMode !== this.currentMode) {
      this.render();
      if (shouldBeMode === 'app') {
        this.refreshDocuments();
      }
      return;
    }

    // If staying in app mode, re-render appropriate components
    if (this.currentMode === 'app') {
      if (this.headerContainer) {
        this.headerComponent?.render();
      }
      this.renderActiveTab();
    }
  }

  render() {
    const isAuth = Boolean(store.token);
    this.currentMode = isAuth ? 'app' : 'auth';

    if (!isAuth) {
      // Direct Terminal Login Screen
      this.root.innerHTML = `<div id="authContainer"></div>`;
      const authContainer = this.root.querySelector('#authContainer');
      this.authComponent = new AuthView(authContainer);
      this.authComponent.render();
    } else {
      // Authenticated Studio Workspace
      this.root.innerHTML = `
        <div class="studio-root">
          <div id="headerStage"></div>
          <main id="contentStage" class="studio-main"></main>
          <div id="modalStage"></div>
        </div>
      `;

      const headerStage = this.root.querySelector('#headerStage');
      const contentStage = this.root.querySelector('#contentStage');
      const modalStage = this.root.querySelector('#modalStage');

      this.headerContainer = headerStage;
      this.contentContainer = contentStage;
      this.modalContainer = modalStage;

      this.headerComponent = new Header(headerStage);
      this.headerComponent.render();

      this.modalComponent = new UpdateModal(modalStage, () => {
        this.refreshDocuments();
      });

      this.docsComponent = new DocumentsView(contentStage, (doc) => {
        this.modalComponent.open(doc);
      });

      this.queryComponent = new QueryView(contentStage);

      this.renderActiveTab();
    }
  }

  renderActiveTab() {
    if (!this.contentContainer) return;

    if (store.activeTab === 'documents') {
      this.docsComponent?.render();
    } else if (store.activeTab === 'query') {
      this.queryComponent?.render();
      this.queryComponent?.loadHistory();
    }
  }
}

// Bootstrap when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('app');
  if (root) {
    const app = new App(root);
    app.init();
  }
});
