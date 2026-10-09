/**
 * EvidenceChunks Component
 * Renders retrieved evidence passages with match scores and expandable accordions.
 */

import { escapeHtml, formatReadableContent } from '../utils.js';

export class EvidenceChunks {
  constructor(chunks) {
    this.chunks = chunks || [];
  }

  render() {
    if (!this.chunks || this.chunks.length === 0) return '';

    return `
      <div class="card evidence-card">
        <div class="card-section-title">
          Retrieved Evidence Chunks (${this.chunks.length})
        </div>
        <div class="chunks-accordion">
          ${this.chunks
            .map((h, i) => {
              const num = i + 1;
              const chunk = h.chunk || {};
              const scorePct = Math.round((h.score || 0) * 100);
              const badgeClass = scorePct >= 70 ? 'match-high' : scorePct >= 30 ? 'match-mid' : 'match-context';
              const badgeText = scorePct > 0 ? `Match: <strong>${scorePct}%</strong>` : `Context Passage`;
              return `
            <div class="chunk-item chunk-expanded" id="chunk-${num}">
              <div class="chunk-header">
                <div class="chunk-title-group">
                  <span class="chunk-index">[${num}]</span>
                  <span class="chunk-source-label">${escapeHtml(chunk.title || chunk.source || `Passage ${num}`)}</span>
                </div>
                <div class="chunk-scores-group">
                  <span class="score-badge ${badgeClass}">${badgeText}</span>
                  <svg class="chevron-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                </div>
              </div>
              <div class="chunk-body-text">
                ${formatReadableContent(chunk.text || '')}
              </div>
            </div>
          `;
            })
            .join('')}
        </div>
      </div>
    `;
  }

  attachEvents(container) {
    container.querySelectorAll('.chunk-header').forEach((header) => {
      header.addEventListener('click', () => {
        header.parentElement.classList.toggle('chunk-expanded');
      });
    });
  }
}
