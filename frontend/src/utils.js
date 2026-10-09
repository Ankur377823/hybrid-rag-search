/**
 * Shared utility functions: formatting, escaping, and text cleanup.
 */

export function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>'"]/g, (t) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;',
  }[t] || t));
}

export function formatBytes(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

export function formatReadableContent(rawText) {
  if (!rawText) return '<p class="evidence-paragraph">No content recorded.</p>';

  // Clean dingbats, corrupted font glyphs, and PUA characters
  let clean = rawText
    .replace(/[\u{1F56E}\u{1F56F}\u{1F4D6}\u{1F56D}]/gu, '\n• ')
    .replace(/[\uB6B1]+/g, '\n• ')
    .replace(/[\uE000-\uF8FF]/g, '\n• ')
    .replace(/[▪■●○◆◇►▶]/g, '\n• ')
    // De-hyphenate words broken by line endings (e.g. "transduc-\ntion" -> "transduction")
    .replace(/(\b[a-zA-Z]+)-\s*\n\s*([a-zA-Z]+\b)/g, '$1$2')
    // Remove isolated single-line page numbers like "\n2\n" or "\n 7 \n"
    .replace(/\n\s*\d{1,3}\s*\n/g, '\n\n')
    // Ensure newline before numbered list items
    .replace(/(\s+)(\d+\.\s+[A-Z])/g, '\n$2')
    .replace(/(\s+)(Step\s+\d+[:—\-])/gi, '\n$2')
    // Remove duplicate bullet markers
    .replace(/(•\s*){2,}/g, '• ')
    // Normalize newlines
    .replace(/\r\n/g, '\n');

  // Split into paragraphs by blank lines (double newlines)
  const blocks = clean.split(/\n\s*\n+/).map((b) => b.trim()).filter(Boolean);
  let html = '';

  for (const block of blocks) {
    const lines = block.split('\n').map((l) => l.trim()).filter(Boolean);
    if (!lines.length) continue;

    const hasBullets = lines.some((l) => l.startsWith('• ') || l.startsWith('- ') || l.startsWith('* '));
    if (hasBullets) {
      let inList = false;
      for (const line of lines) {
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
          if (line.endsWith(':') || /^Step\s+\d+/i.test(line) || /^\d+\.\s+[A-Z]/.test(line)) {
            html += `<div class="evidence-subheading">${escapeHtml(line)}</div>`;
          } else {
            html += `<p class="evidence-paragraph">${escapeHtml(line)}</p>`;
          }
        }
      }
      if (inList) html += '</ul>';
    } else {
      // Header detection: isolated short heading
      if (lines.length === 1 && (lines[0].endsWith(':') || /^(\d+(\.\d+)*)\s+[A-Z]/.test(lines[0]))) {
        html += `<div class="evidence-subheading">${escapeHtml(lines[0])}</div>`;
      } else {
        // Continuous prose: join lines with space
        const prose = lines.join(' ');
        html += `<p class="evidence-paragraph">${escapeHtml(prose)}</p>`;
      }
    }
  }

  return html || `<p class="evidence-paragraph">${escapeHtml(rawText)}</p>`;
}
