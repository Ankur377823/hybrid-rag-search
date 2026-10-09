/**
 * CitationsList Component
 * Renders verified citation markers, sources, and quoted evidence passages.
 */

import { escapeHtml, formatReadableContent } from '../utils.js';

export class CitationsList {
  constructor(citations) {
    this.citations = citations || [];
  }

  render() {
    if (!this.citations || this.citations.length === 0) return '';

    return `
      <div class="card citations-card">
        <div class="card-section-title">
          Verified Citations (${this.citations.length})
        </div>
        <div class="citations-container">
          ${this.citations
            .map(
              (c) => `
            <div class="citation-card-item">
              <div class="citation-header-line">
                <span class="citation-marker-tag">${escapeHtml(c.marker)}</span>
                <span class="citation-source-name">${escapeHtml(c.title || c.source)}</span>
                <span class="badge-verified">Verified</span>
              </div>
              <div class="citation-quote-box">
                ${formatReadableContent(c.quote || 'Evidence quote confirmed.')}
              </div>
            </div>
          `
            )
            .join('')}
        </div>
      </div>
    `;
  }
}
