/**
 * UpdateModal Component
 * Document Versioning & Atomic Re-indexing Modal
 */

import { updateDocument, uploadDocument } from '../api.js';
import { store } from '../state.js';
import { formatBytes, escapeHtml } from '../utils.js';

export class UpdateModal {
  constructor(container, onComplete) {
    this.container = container;
    this.onComplete = onComplete;
    this.isOpen = false;
    this.activeDoc = null; // null = new document, object = update existing
    this.selectedFile = null;
    this.step = 'idle'; // 'idle' | 'processing' | 'success' | 'error'
    this.progressPct = 0;
    this.statusMessage = '';
    this.errorMessage = '';
  }

  open(doc = null) {
    this.isOpen = true;
    this.activeDoc = doc;
    this.selectedFile = null;
    this.step = 'idle';
    this.progressPct = 0;
    this.statusMessage = '';
    this.errorMessage = '';
    this.render();
  }

  close() {
    this.isOpen = false;
    this.container.innerHTML = '';
  }

  render() {
    if (!this.isOpen) {
      this.container.innerHTML = '';
      return;
    }

    const isUpdate = Boolean(this.activeDoc);
    const title = isUpdate ? `Update ${this.activeDoc.filename}` : 'Upload New Document';
    const currentVer = isUpdate ? `v${this.activeDoc.version}` : 'New (v1)';
    const nextVer = isUpdate ? `v${this.activeDoc.version + 1}` : 'v1';

    this.container.innerHTML = `
      <div class="modal-backdrop" id="modalBackdrop">
        <div class="modal-dialog">
          <div class="modal-header">
            <div>
              <h3 class="modal-title">${escapeHtml(title)}</h3>
              <p class="modal-subtitle">
                ${isUpdate ? `Replace with new version (${nextVer})` : 'Upload a document to index'}
              </p>
            </div>
            <button id="closeModalBtn" class="modal-close-btn" title="Close">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>

          <div class="modal-body">
            <!-- Dropzone -->
            <div id="modalDropzone" class="dropzone ${this.selectedFile ? 'dropzone-active' : ''}">
              <input type="file" id="modalFileInput" class="file-input-hidden" accept=".pdf,.md,.txt,.html,.htm">
              <div class="dropzone-inner">
                <div class="dropzone-text">
                  ${
                    this.selectedFile
                      ? `<div class="dropzone-filename">${escapeHtml(this.selectedFile.name)}</div>
                         <div class="dropzone-filesize">${formatBytes(this.selectedFile.size)}</div>`
                      : `<div class="dropzone-primary-text">Click or drag a file to upload</div>
                         <div class="dropzone-secondary-text">Supported formats: PDF, Markdown, TXT, HTML</div>`
                  }
                </div>
              </div>
            </div>

            <!-- Animated Stepper -->
            ${
              this.step === 'processing'
                ? `
              <div class="stepper-card">
                <div class="stepper-header-row">
                  <span class="stepper-msg">${escapeHtml(this.statusMessage || 'Processing...')}</span>
                  <span class="stepper-pct">${this.progressPct}%</span>
                </div>
                <div class="progress-bar-track">
                  <div class="progress-bar-fill" style="width: ${this.progressPct}%;"></div>
                </div>
                <div class="stepper-stage-labels">
                  <span class="${this.progressPct >= 20 ? 'stage-done' : ''}">Upload</span>
                  <span class="${this.progressPct >= 40 ? 'stage-done' : ''}">Extract</span>
                  <span class="${this.progressPct >= 65 ? 'stage-done' : ''}">Chunk</span>
                  <span class="${this.progressPct >= 85 ? 'stage-done' : ''}">Embed</span>
                  <span class="${this.progressPct >= 100 ? 'stage-done' : ''}">Atomic Swap</span>
                </div>
              </div>
            `
                : ''
            }

            <!-- Error Rollback Banner -->
            ${
              this.errorMessage
                ? `
              <div class="alert-box alert-error">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="15" y1="9" x2="9" y2="15"></line>
                  <line x1="9" y1="9" x2="15" y2="15"></line>
                </svg>
                <div>
                  <strong>Update Failed</strong>
                  <p>${escapeHtml(this.errorMessage)}</p>
                </div>
              </div>
            `
                : ''
            }

            <!-- Success Banner -->
            ${
              this.step === 'success'
                ? `
              <div class="alert-box alert-success">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                  <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </svg>
                <div>
                  <strong>Indexing Successful</strong>
                  <p>${escapeHtml(this.statusMessage)}</p>
                </div>
              </div>
            `
                : ''
            }
          </div>

          <div class="modal-footer">
            <button id="modalCancelBtn" class="btn btn-secondary">
              ${this.step === 'success' ? 'Close' : 'Cancel'}
            </button>
            ${
              this.step !== 'success'
                ? `
              <button id="modalSubmitBtn" class="btn btn-primary" ${!this.selectedFile || this.step === 'processing' ? 'disabled' : ''}>
                ${
                  this.step === 'processing'
                    ? '<span class="spinner-sm"></span> Processing...'
                    : (isUpdate ? 'Deploy Atomic Update' : 'Index Document')
                }
              </button>
            `
                : ''
            }
          </div>
        </div>
      </div>
    `;

    this.attachEvents();
  }

  attachEvents() {
    const backdrop = this.container.querySelector('#modalBackdrop');
    const closeBtn = this.container.querySelector('#closeModalBtn');
    const cancelBtn = this.container.querySelector('#modalCancelBtn');
    const submitBtn = this.container.querySelector('#modalSubmitBtn');
    const dropzone = this.container.querySelector('#modalDropzone');
    const fileInput = this.container.querySelector('#modalFileInput');

    const handleClose = () => {
      if (this.step !== 'processing') {
        this.close();
      }
    };

    if (backdrop) {
      backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) handleClose();
      });
    }
    if (closeBtn) closeBtn.addEventListener('click', handleClose);
    if (cancelBtn) cancelBtn.addEventListener('click', handleClose);

    if (dropzone && fileInput) {
      dropzone.addEventListener('click', () => fileInput.click());

      dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dropzone-drag-over');
      });

      dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dropzone-drag-over');
      });

      dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dropzone-drag-over');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          this.selectedFile = e.dataTransfer.files[0];
          this.render();
        }
      });

      fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
          this.selectedFile = e.target.files[0];
          this.render();
        }
      });
    }

    if (submitBtn) {
      submitBtn.addEventListener('click', async () => {
        if (!this.selectedFile) return;

        this.step = 'processing';
        this.errorMessage = '';
        this.progressPct = 20;
        this.statusMessage = 'Uploading document bytes...';
        this.render();

        try {
          const file = this.selectedFile;
          const isUpdate = Boolean(this.activeDoc);

          // Simulated smooth progress for user feedback
          const timer1 = setTimeout(() => {
            if (this.step === 'processing') {
              this.progressPct = 45;
              this.statusMessage = 'Parsing text & document structure...';
              this.render();
            }
          }, 350);

          const timer2 = setTimeout(() => {
            if (this.step === 'processing') {
              this.progressPct = 70;
              this.statusMessage = 'Computing token chunks & generating embeddings...';
              this.render();
            }
          }, 900);

          let res;
          if (isUpdate) {
            res = await updateDocument(this.activeDoc.id, file);
          } else {
            res = await uploadDocument(file);
          }

          clearTimeout(timer1);
          clearTimeout(timer2);

          this.progressPct = 100;
          this.step = 'success';
          this.statusMessage = res.message || 'Atomic re-indexing completed successfully.';
          this.render();

          store.addLog(`DOCUMENT INDEXED: "${file.name}" (version: ${res.document ? res.document.version : 1})`);

          if (this.onComplete) {
            this.onComplete();
          }

          setTimeout(() => {
            this.close();
          }, 1400);
        } catch (err) {
          this.step = 'error';
          this.progressPct = 0;
          this.errorMessage = err.message || 'Failed to index document.';
          this.render();
        }
      });
    }
  }
}
