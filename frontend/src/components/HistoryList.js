/**
 * HistoryList Component
 * Displays recent query audit records with composite confidence, latency, and click-to-rerun.
 */

import { escapeHtml } from '../utils.js';

export class HistoryList {
  constructor(history, onSelectQuery) {
    this.history = history || [];
    this.onSelectQuery = onSelectQuery;
  }

  render() {
    return `
      <div class="card sidebar-card history-card">
        <div class="sidebar-header">
          <h4 class="sidebar-title">Audit History</h4>
          <span class="badge-subtle">${this.history.length} logged</span>
        </div>
        <div class="history-list">
          ${
            this.history.length === 0
              ? '<div class="history-empty">No recent queries recorded.</div>'
              : this.history
                  .map(
                    (h) => `
                <div class="history-item" data-q="${escapeHtml(h.question)}">
                  <div class="history-q-text">${escapeHtml(h.question)}</div>
                  <div class="history-meta-row">
                    <span class="history-badge ${h.composite_confidence >= 0.7 ? 'badge-good' : 'badge-fair'}">
                      ${(h.composite_confidence * 100).toFixed(0)}% conf
                    </span>
                    <span class="history-latency">${h.latency_ms} ms</span>
                  </div>
                </div>
              `
                  )
                  .join('')
          }
        </div>
      </div>
    `;
  }

  attachEvents(container) {
    container.querySelectorAll('.history-item').forEach((item) => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const q = item.getAttribute('data-q');
        if (q && this.onSelectQuery) {
          this.onSelectQuery(q);
        }
      });
    });
  }
}
