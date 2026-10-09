/**
 * DocumentCard Component
 * Displays a single document catalog item with metadata, version, and action controls.
 */

import { formatBytes, escapeHtml } from '../utils.js';

export class DocumentCard {
  constructor(doc) {
    this.doc = doc;
  }

  render() {
    const doc = this.doc;
    const sizeStr = formatBytes(doc.size_bytes);
    const updatedDate = new Date(doc.updated_at || doc.created_at).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });

    return `
      <div class="doc-card" data-id="${doc.id}">
        <div class="doc-card-main">
          <div class="doc-header-row">
            <div class="doc-title-box">
              <div class="doc-name" title="${escapeHtml(doc.filename)}">${escapeHtml(doc.filename)}</div>
              <div class="doc-meta-line">
                <span>Version ${doc.version}</span>
                <span class="meta-sep">&middot;</span>
                <span>${doc.chunk_count} chunks</span>
                <span class="meta-sep">&middot;</span>
                <span>${sizeStr}</span>
                <span class="meta-sep">&middot;</span>
                <span>${updatedDate}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="doc-actions-row">
          <button class="btn btn-secondary btn-sm ask-btn" data-id="${doc.id}">
            Ask Questions
          </button>
          <button class="btn btn-secondary btn-sm update-btn" data-id="${doc.id}">
            Update
          </button>
          <button class="btn btn-secondary btn-sm delete-btn" data-id="${doc.id}">
            Delete
          </button>
        </div>
      </div>
    `;
  }
}
