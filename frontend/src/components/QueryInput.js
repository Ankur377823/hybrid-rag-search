/**
 * QueryInput Component
 * Renders the question input bar, corpus scope dropdown, and sample question prompts.
 */

import { escapeHtml } from '../utils.js';

export class QueryInput {
  constructor({ docs, scopedDocId, loading, onSubmit, onScopeChange, onSampleClick }) {
    this.docs = docs || [];
    this.scopedDocId = scopedDocId || '';
    this.loading = Boolean(loading);
    this.onSubmit = onSubmit;
    this.onScopeChange = onScopeChange;
    this.onSampleClick = onSampleClick;
  }

  render() {
    return `
      <div class="card query-input-card">
        <div class="scope-selector-row">
          <label for="queryScopeSelect" class="scope-label">Corpus Scope:</label>
          <div class="select-wrapper">
            <select id="queryScopeSelect" class="select-control">
              <option value="">All Corpus Documents (${this.docs.length})</option>
              ${this.docs
                .map(
                  (d) =>
                    `<option value="${d.id}" ${this.scopedDocId === d.id ? 'selected' : ''}>${escapeHtml(d.filename)} (v${d.version})</option>`
                )
                .join('')}
            </select>
          </div>
        </div>

        <form id="queryForm" class="query-form">
          <div class="textarea-container">
            <textarea
              id="queryInputText"
              class="query-textarea"
              placeholder="Ask a factual question about your indexed documents..."
              rows="3"
              required
            ></textarea>
          </div>

          <div class="query-submit-bar">
            <div class="sample-prompts-row">
              <span class="sample-label">Try asking:</span>
              <button type="button" class="sample-prompt-chip" data-q="What is the primary topic of the uploaded documents?">Overview of documents</button>
              <button type="button" class="sample-prompt-chip" data-q="What are the key policy requirements or procedures?">Key requirements</button>
              <button type="button" class="sample-prompt-chip" data-q="What are the main technical guidelines or rules?">Guidelines & rules</button>
            </div>

            <button type="submit" id="submitQueryBtn" class="btn btn-primary btn-search" ${this.loading ? 'disabled' : ''}>
              ${
                this.loading
                  ? '<span class="spinner-sm"></span> Searching...'
                  : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                       <circle cx="11" cy="11" r="8"></circle>
                       <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                     </svg> Execute Query`
              }
            </button>
          </div>
        </form>
      </div>
    `;
  }

  attachEvents(container) {
    const form = container.querySelector('#queryForm');
    const input = container.querySelector('#queryInputText');
    const scopeSelect = container.querySelector('#queryScopeSelect');

    if (scopeSelect && this.onScopeChange) {
      scopeSelect.addEventListener('change', (e) => {
        this.onScopeChange(e.target.value);
      });
    }

    container.querySelectorAll('.sample-prompt-chip').forEach((chip) => {
      chip.addEventListener('click', (e) => {
        e.preventDefault();
        const promptText = chip.getAttribute('data-q');
        if (input) {
          input.value = promptText;
          input.focus();
        }
        if (this.onSampleClick) {
          this.onSampleClick(promptText);
        }
      });
    });

    if (form && this.onSubmit) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const question = input ? input.value.trim() : '';
        if (question) {
          this.onSubmit(question);
        }
      });
    }
  }
}
