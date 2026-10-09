/**
 * QueryView Component
 * High-level workspace orchestrator composing modular subcomponents:
 * - QueryInput
 * - AnswerCard
 * - CitationsList
 * - EvidenceChunks
 * - UsageCard
 * - HistoryList
 */

import { askQuestion, getHistory, getUsage } from '../api.js';
import { store } from '../state.js';
import { QueryInput } from './QueryInput.js';
import { AnswerCard } from './AnswerCard.js';
import { CitationsList } from './CitationsList.js';
import { EvidenceChunks } from './EvidenceChunks.js';
import { UsageCard } from './UsageCard.js';
import { HistoryList } from './HistoryList.js';

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

  async executeQuery(question) {
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
  }

  render() {
    const docs = store.documents;
    const ans = this.answer;

    const queryInputComponent = new QueryInput({
      docs,
      scopedDocId: this.scopedDocId,
      loading: this.loading,
      onSubmit: (q) => this.executeQuery(q),
      onScopeChange: (scopeId) => {
        this.scopedDocId = scopeId;
      },
      onSampleClick: (q) => {
        this.executeQuery(q);
      },
    });

    const answerCardComponent = new AnswerCard(ans);
    const citationsComponent = new CitationsList(ans?.citations);
    const chunksComponent = new EvidenceChunks(ans?.used_chunks);
    const usageComponent = new UsageCard(this.usage);
    const historyComponent = new HistoryList(this.history, (q) => {
      this.executeQuery(q);
    });

    this.container.innerHTML = `
      <div class="workspace-page">
        <div class="query-layout-grid">
          <!-- Main Query & Answer Panel -->
          <div class="query-main-panel">
            ${queryInputComponent.render()}

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
            ${
              ans
                ? `
              <div class="answer-container">
                ${answerCardComponent.render()}
                ${citationsComponent.render()}
                ${chunksComponent.render()}
              </div>
            `
                : ''
            }
          </div>

          <!-- Sidebar Analytics & Query History -->
          <aside class="query-sidebar">
            ${usageComponent.render()}
            ${historyComponent.render()}
          </aside>
        </div>
      </div>
    `;

    // Attach component events
    queryInputComponent.attachEvents(this.container);
    if (ans) {
      answerCardComponent.attachEvents(this.container);
      chunksComponent.attachEvents(this.container);
    }
    historyComponent.attachEvents(this.container);
  }
}
