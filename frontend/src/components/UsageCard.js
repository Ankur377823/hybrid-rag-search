/**
 * UsageCard Component
 * Displays tenant usage and quota metrics (queries today, tokens processed).
 */

export class UsageCard {
  constructor(usage) {
    this.usage = usage;
  }

  render() {
    const usage = this.usage;
    const queries = usage ? usage.total_queries : 0;
    const tokens = usage ? usage.total_tokens_used.toLocaleString() : '0';

    return `
      <div class="card sidebar-card">
        <div class="sidebar-header">
          <h4 class="sidebar-title">Usage &amp; Quotas</h4>
          <span class="badge-subtle">Active Tenant</span>
        </div>
        <div class="telemetry-grid">
          <div class="telemetry-cell">
            <div class="telemetry-label">Queries Today</div>
            <div class="telemetry-number">${queries}</div>
          </div>
          <div class="telemetry-cell">
            <div class="telemetry-label">Tokens Processed</div>
            <div class="telemetry-number">${tokens}</div>
          </div>
        </div>
      </div>
    `;
  }
}
