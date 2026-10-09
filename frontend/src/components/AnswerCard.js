/**
 * AnswerCard Component
 * Renders the grounded answer text with citations, safety refusal warnings, and confidence metrics.
 */

import { escapeHtml } from '../utils.js';

export class AnswerCard {
  constructor(answer) {
    this.ans = answer;
  }

  render() {
    const ans = this.ans;
    if (!ans) return '';

    const isIdk = ans.is_idk;
    const formattedText = escapeHtml(ans.text).replace(/\[(\d+)\]/g, (match, num) => {
      return `<a class="citation-pill" href="#chunk-${num}" title="View source evidence [${num}]"><span class="pill-hash">#</span>${num}</a>`;
    });

    const compScore = Math.round((ans.composite_confidence || 0) * 100);
    const citeScore = Math.round((ans.citation_accuracy || 0) * 100);
    const retScore = Math.round((ans.retrieval_confidence || 0) * 100);

    const compClass = compScore >= 75 ? 'metric-emerald' : compScore >= 50 ? 'metric-blue' : 'metric-amber';
    const citeClass = citeScore >= 75 ? 'metric-indigo' : citeScore >= 50 ? 'metric-blue' : 'metric-amber';
    const retClass = retScore >= 75 ? 'metric-cyan' : retScore >= 50 ? 'metric-blue' : 'metric-amber';

    return `
      <!-- Safety Refusal Alert -->
      ${
        isIdk
          ? `
        <div class="alert-box alert-warning">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
          <div>
            <strong>Safety Threshold Gate Activated</strong>
            <p>Retrieval confidence (${(ans.retrieval_confidence || 0).toFixed(2)}) is below the required 0.35 threshold. The pipeline returned "I don't know" to prevent hallucination.</p>
          </div>
        </div>
      `
          : ''
      }

      <!-- Answer Card -->
      <div class="card answer-card">
        <div class="answer-header">
          <div class="answer-badge-group">
            <span class="badge-primary">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                <polyline points="9 12 11 14 15 10"></polyline>
              </svg>
              Grounded Answer
            </span>
            <span class="badge-neutral">${escapeHtml(ans.model || 'gpt-4o')}</span>
          </div>
          <button id="copyAnswerBtn" class="btn btn-secondary btn-xs btn-copy-action">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
            <span>Copy</span>
          </button>
        </div>

        <div id="answerProse" class="answer-body-prose">
          ${formattedText}
        </div>

        <!-- Quality Metrics Grid -->
        <div class="answer-metrics-bar">
          <div class="metric-gauge-cell ${compClass}">
            <div class="metric-gauge-top">
              <span class="metric-gauge-label">Composite Confidence</span>
              <span class="metric-gauge-value">${compScore}%</span>
            </div>
            <div class="metric-gauge-bar">
              <div class="metric-gauge-fill" style="width: ${compScore}%;"></div>
            </div>
          </div>

          <div class="metric-gauge-cell ${citeClass}">
            <div class="metric-gauge-top">
              <span class="metric-gauge-label">Citation Accuracy</span>
              <span class="metric-gauge-value">${citeScore}%</span>
            </div>
            <div class="metric-gauge-bar">
              <div class="metric-gauge-fill" style="width: ${citeScore}%;"></div>
            </div>
          </div>

          <div class="metric-gauge-cell ${retClass}">
            <div class="metric-gauge-top">
              <span class="metric-gauge-label">Retrieval Score</span>
              <span class="metric-gauge-value">${retScore}%</span>
            </div>
            <div class="metric-gauge-bar">
              <div class="metric-gauge-fill" style="width: ${retScore}%;"></div>
            </div>
          </div>

          <div class="metric-gauge-cell metric-latency">
            <div class="metric-gauge-top">
              <span class="metric-gauge-label">Pipeline Latency</span>
              <span class="metric-gauge-value">${ans.latency_ms} ms</span>
            </div>
            <div class="metric-gauge-sub">Round-trip time</div>
          </div>
        </div>
      </div>
    `;
  }

  attachEvents(container) {
    const copyBtn = container.querySelector('#copyAnswerBtn');
    if (copyBtn) {
      copyBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const prose = container.querySelector('#answerProse');
        if (prose) {
          navigator.clipboard.writeText(prose.innerText);
          copyBtn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg> Copied!
          `;
          setTimeout(() => {
            copyBtn.innerHTML = `
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg> Copy
            `;
          }, 1800);
        }
      });
    }
  }
}
