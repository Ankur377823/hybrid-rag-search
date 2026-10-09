/**
 * QueryView Component
 * Grounded Hybrid Query Studio with bracketed citation resolution and telemetry.
 */

import { askQuestion, getHistory, getUsage } from '../api.js';
import { store } from '../state.js';

export class QueryView {
  constructor(container) {
    this.container = container;
    this.loading = false;
    this.answer = null;
    this.history = [];
    this.usage = null;
    this.scopedDocId = '';

    window.addEventListener('query:scope', (e) => {
      if (e.detail && e.detail.documentId) {
        this.scopedDocId = e.detail.documentId;
        this.render();
      }
    });
  }

  setScopedDoc(docId) {
    this.scopedDocId = docId || '';
    this.render();
  }

  async loadHistory() {
    try {
      const [hist, usg] = await Promise.all([getHistory(), getUsage()]);
      this.history = hist || [];
      this.usage = usg || null;
      this.render();
    } catch {
      // Ignored
    }
  }

  render() {
    const docs = store.documents;
    const ans = this.answer;

    this.container.innerHTML = `
      <div class="workspace-page">
        <div class="query-layout-grid">
          <!-- Main Query & Answer Panel -->
          <div class="query-main-panel">
            <!-- Search Input Card -->
            <div class="card query-input-card">
              <div class="scope-selector-row">
                <label for="queryScopeSelect" class="scope-label">Corpus Scope:</label>
                <div class="select-wrapper">
                  <select id="queryScopeSelect" class="select-control">
                    <option value="">All Corpus Documents (${docs.length})</option>
                    ${docs
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

            <!-- Loading State -->
            ${
              this.loading
                ? `
              <div class="card query-loading-card">
                <div class="spinner-md"></div>
                <div class="loading-text-stack">
                  <div class="loading-bold">Executing Hybrid Retrieval Pipeline</div>
                  <div class="loading-sub">Dense vector cosine search &rarr; BM25 lexical match &rarr; Reciprocal Rank Fusion &rarr; LLM Grounded Answer</div>
                </div>
              </div>
            `
                : ''
            }

            <!-- Answer Section -->
            ${ans ? this._renderAnswerSection(ans) : ''}
          </div>

          <!-- Sidebar Analytics & Query History -->
          <aside class="query-sidebar">
            <!-- Quota Telemetry Card -->
            <div class="card sidebar-card">
              <div class="sidebar-header">
                <h4 class="sidebar-title">Usage &amp; Quotas</h4>
                <span class="badge-subtle">Active Tenant</span>
              </div>
              <div class="telemetry-grid">
                <div class="telemetry-cell">
                  <div class="telemetry-label">Queries Today</div>
                  <div class="telemetry-number">${this.usage ? this.usage.total_queries : 0}</div>
                </div>
                <div class="telemetry-cell">
                  <div class="telemetry-label">Tokens Processed</div>
                  <div class="telemetry-number">${this.usage ? this.usage.total_tokens_used.toLocaleString() : 0}</div>
                </div>
              </div>
            </div>

            <!-- Query Audit History Card -->
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
          </aside>
        </div>
      </div>
    `;

    this.attachEvents();
  }

  _renderAnswerSection(ans) {
    const isIdk = ans.is_idk;
    const formattedText = escapeHtml(ans.text).replace(/\[(\d+)\]/g, (match, num) => {
      return `<a class="citation-ref-badge" href="#chunk-${num}" title="Jump to audited passage [${num}]">[${num}]</a>`;
    });

    return `
      <div class="answer-container">
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
              <span class="badge-primary">Grounded Answer</span>
              <span class="badge-neutral">${escapeHtml(ans.model || 'gpt-4o')}</span>
            </div>
            <button id="copyAnswerBtn" class="btn btn-secondary btn-xs">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
              Copy
            </button>
          </div>

          <div id="answerProse" class="answer-body-prose">
            ${formattedText}
          </div>

          <!-- Quality Metrics Grid -->
          <div class="answer-metrics-bar">
            <div class="metric-gauge-cell">
              <div class="metric-gauge-label">Composite Confidence</div>
              <div class="metric-gauge-value">${(ans.composite_confidence * 100).toFixed(0)}%</div>
              <div class="metric-gauge-bar">
                <div class="metric-gauge-fill" style="width: ${ans.composite_confidence * 100}%;"></div>
              </div>
            </div>

            <div class="metric-gauge-cell">
              <div class="metric-gauge-label">Citation Accuracy</div>
              <div class="metric-gauge-value">${(ans.citation_accuracy * 100).toFixed(0)}%</div>
              <div class="metric-gauge-bar">
                <div class="metric-gauge-fill" style="width: ${ans.citation_accuracy * 100}%;"></div>
              </div>
            </div>

            <div class="metric-gauge-cell">
              <div class="metric-gauge-label">Retrieval Score</div>
              <div class="metric-gauge-value">${(ans.retrieval_confidence * 100).toFixed(0)}%</div>
              <div class="metric-gauge-bar">
                <div class="metric-gauge-fill" style="width: ${ans.retrieval_confidence * 100}%;"></div>
              </div>
            </div>

            <div class="metric-gauge-cell">
              <div class="metric-gauge-label">Pipeline Latency</div>
              <div class="metric-gauge-value">${ans.latency_ms} ms</div>
              <div class="metric-gauge-sub">Round-trip time</div>
            </div>
          </div>
        </div>

        <!-- Verified Citations Card -->
        ${
          ans.citations && ans.citations.length > 0
            ? `
          <div class="card citations-card">
            <div class="card-section-title">
              Verified Citations (${ans.citations.length})
            </div>
            <div class="citations-container">
              ${ans.citations
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
        `
            : ''
        }

        <!-- Evidence Chunks Card -->
        ${
          ans.used_chunks && ans.used_chunks.length > 0
            ? `
          <div class="card evidence-card">
            <div class="card-section-title">
              Retrieved Evidence Chunks (${ans.used_chunks.length})
            </div>
            <div class="chunks-accordion">
              ${ans.used_chunks
                .map((h, i) => {
                  const num = i + 1;
                  const chunk = h.chunk || {};
                  return `
                <div class="chunk-item chunk-expanded" id="chunk-${num}">
                  <div class="chunk-header" onclick="this.parentElement.classList.toggle('chunk-expanded')">
                    <div class="chunk-title-group">
                      <span class="chunk-index">[${num}]</span>
                      <span class="chunk-source-label">${escapeHtml(chunk.title || chunk.source || `Passage ${num}`)}</span>
                    </div>
                    <div class="chunk-scores-group">
                      <span class="score-badge">Match: <strong>${Math.round((h.score || 0) * 100)}%</strong></span>
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
        `
            : ''
        }
      </div>
    `;
  }

  attachEvents() {
    const form = this.container.querySelector('#queryForm');
    const input = this.container.querySelector('#queryInputText');
    const scopeSelect = this.container.querySelector('#queryScopeSelect');
    const copyBtn = this.container.querySelector('#copyAnswerBtn');

    if (scopeSelect) {
      scopeSelect.addEventListener('change', (e) => {
        this.scopedDocId = e.target.value;
      });
    }

    if (input) {
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          if (form) form.requestSubmit();
        }
      });
    }

    this.container.querySelectorAll('.sample-prompt-chip').forEach((chip) => {
      chip.addEventListener('click', (e) => {
        e.preventDefault();
        if (input && form) {
          input.value = chip.getAttribute('data-q');
          form.requestSubmit();
        }
      });
    });

    this.container.querySelectorAll('.history-item').forEach((item) => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        if (input && form) {
          input.value = item.getAttribute('data-q');
          form.requestSubmit();
        }
      });
    });

    if (copyBtn) {
      copyBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const prose = this.container.querySelector('#answerProse');
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

    if (form) {
      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = input.value.trim();
        if (!question) return;

        this.loading = true;
        this.render();

        try {
          const res = await askQuestion(question, this.scopedDocId || null);
          this.answer = res;
          store.addLog(`QUERY PROCESSED: "${question.substring(0, 30)}..." -> Latency: ${res.latency_ms}ms`);
          await this.loadHistory();
        } catch (err) {
          alert('Search query failed: ' + err.message);
        } finally {
          this.loading = false;
          this.render();
        }
      });
    }
  }
}

function formatReadableContent(rawText) {
  if (!rawText) return '<p class="evidence-paragraph">No content recorded.</p>';

  // Clean dingbats, book symbols, corrupted font glyphs, and PUA characters
  let clean = rawText
    // Replace 🕮 (book/bullet symbol in pdf fonts like Wingdings)
    .replace(/[\u{1F56E}\u{1F56F}\u{1F4D6}\u{1F56D}]/gu, '\n• ')
    // Replace 뚱 (broken font mapping bullet)
    .replace(/[\uB6B1]+/g, '\n• ')
    // Replace Private Use Area symbols often used as bullets in PDFs
    .replace(/[\uE000-\uF8FF]/g, '\n• ')
    // Replace odd diamond/square bullets
    .replace(/[▪■●○◆◇►▶]/g, '\n• ')
    // Ensure newline before numbered items like " 1. ", " 2. ", " Step 1: "
    .replace(/(\s+)(\d+\.\s+[A-Z])/g, '\n$2')
    .replace(/(\s+)(Step\s+\d+[:—\-])/gi, '\n$2')
    // Remove duplicate bullet markers
    .replace(/(•\s*){2,}/g, '• ')
    // Normalize newlines
    .replace(/\r\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  // Parse lines into structured paragraphs, subheadings, and bullet lists
  const rawLines = clean.split('\n').map((l) => l.trim()).filter(Boolean);
  let html = '';
  let inList = false;

  for (const line of rawLines) {
    if (line.startsWith('• ') || line.startsWith('- ') || line.startsWith('* ')) {
      if (!inList) {
        html += '<ul class="evidence-list">';
        inList = true;
      }
      const itemText = line.replace(/^[•\-*]\s*/, '');
      html += `<li class="evidence-list-item">${escapeHtml(itemText)}</li>`;
    } else {
      if (inList) {
        html += '</ul>';
        inList = false;
      }
      // Check if it's a sub-heading (short line ending in colon or Step X)
      if (line.endsWith(':') || /^Step\s+\d+/i.test(line) || /^\d+\.\s+[A-Z]/.test(line)) {
        html += `<div class="evidence-subheading">${escapeHtml(line)}</div>`;
      } else {
        html += `<p class="evidence-paragraph">${escapeHtml(line)}</p>`;
      }
    }
  }

  if (inList) {
    html += '</ul>';
  }

  return html || `<p class="evidence-paragraph">${escapeHtml(rawText)}</p>`;
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>'"]/g, 
    (t) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[t] || t)
  );
}
