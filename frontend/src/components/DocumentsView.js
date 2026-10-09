/**
 * DocumentsView Component
 * Professional enterprise document catalog with versioning controls.
 */

import { deleteDocument, listDocuments } from '../api.js';
import { store } from '../state.js';
import { DocumentCard } from './DocumentCard.js';

export class DocumentsView {
  constructor(container, onOpenUpdateModal) {
    this.container = container;
    this.onOpenUpdateModal = onOpenUpdateModal;
    this.loading = false;
  }

  async loadData() {
    this.loading = true;
    this.render();
    try {
      const docs = await listDocuments();
      store.setDocuments(docs);
    } catch (err) {
      console.error('Failed to list documents:', err);
    } finally {
      this.loading = false;
      this.render();
    }
  }

  render() {
    const docs = store.documents;

    let contentHtml = '';
    if (this.loading && docs.length === 0) {
      contentHtml = `
        <div class="empty-state-panel">
          <div class="spinner-lg"></div>
          <div class="empty-state-title">Loading Indexed Corpus...</div>
          <p class="empty-state-desc">Fetching document records and versions from database.</p>
        </div>
      `;
    } else if (docs.length === 0) {
      contentHtml = `
        <div class="empty-state-panel">
          <h3 class="empty-state-title">No documents yet</h3>
          <p class="empty-state-desc">Upload a PDF or document to start querying.</p>
          <button id="uploadFirstDocBtn" class="btn btn-primary mt-4">
            Upload Document
          </button>
        </div>
      `;
    } else {
      contentHtml = `
        <div class="document-cards-grid">
          ${docs.map((doc) => new DocumentCard(doc).render()).join('')}
        </div>
      `;
    }

    this.container.innerHTML = `
      <div class="workspace-page">
        <!-- Top Action Bar -->
        <div class="page-header">
          <div>
            <h2 class="page-title">Documents</h2>
            <p class="page-subtitle">Manage your uploaded files and search corpus</p>
          </div>
          <button id="uploadNewDocTopBtn" class="btn btn-primary">
            + Upload Document
          </button>
        </div>

        ${contentHtml}
      </div>
    `;

    this.attachEvents();
  }

  attachEvents() {
    const uploadTop = this.container.querySelector('#uploadNewDocTopBtn');
    const uploadFirst = this.container.querySelector('#uploadFirstDocBtn');

    if (uploadTop) {
      uploadTop.addEventListener('click', (e) => {
        e.preventDefault();
        this.onOpenUpdateModal(null);
      });
    }

    if (uploadFirst) {
      uploadFirst.addEventListener('click', (e) => {
        e.preventDefault();
        this.onOpenUpdateModal(null);
      });
    }

    this.container.querySelectorAll('.ask-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const docId = btn.getAttribute('data-id');
        store.setActiveTab('query');
        window.dispatchEvent(new CustomEvent('query:scope', { detail: { documentId: docId } }));
      });
    });

    this.container.querySelectorAll('.update-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const docId = btn.getAttribute('data-id');
        const doc = store.documents.find((d) => d.id === docId);
        if (doc) {
          this.onOpenUpdateModal(doc);
        }
      });
    });

    this.container.querySelectorAll('.delete-btn').forEach((btn) => {
      btn.addEventListener('click', async (e) => {
        e.preventDefault();
        const docId = btn.getAttribute('data-id');
        const doc = store.documents.find((d) => d.id === docId);
        const name = doc ? doc.filename : 'this document';

        if (confirm(`Are you sure you want to delete "${name}"? This will atomically remove all chunks from the vector and sparse index.`)) {
          try {
            await deleteDocument(docId);
            store.addLog(`DOCUMENT DELETED: doc_id=${docId}`);
            await this.loadData();
          } catch (err) {
            alert('Failed to delete document: ' + err.message);
          }
        }
      });
    });
  }
}
