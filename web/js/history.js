/**
 * history.js — History panel: load past generations, restore prompt, preview video.
 *
 * History metadata (prompt, model, task, etc.) is stored in localStorage.
 * The actual video files are served from /exports (aliased to /assets/video).
 */

const HISTORY_KEY = 'fv_history';

/** @typedef {{ filename: string, prompt: string, model: string, task: string, duration: number, aspectRatio: string, createdAt: number }} HistoryEntry */

/** Save a completed generation to localStorage. */
export function recordHistory(filename, { prompt, model, task, duration, aspectRatio }) {
  const entries = loadLocalHistory();
  entries.unshift({ filename, prompt, model, task, duration, aspectRatio, createdAt: Date.now() });
  // Keep last 100
  localStorage.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, 100)));
}

/** Load history entries from localStorage. */
export function loadLocalHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) ?? '[]');
  } catch {
    return [];
  }
}

/**
 * Render the history panel by merging server-side file list with local metadata.
 * @param {Array} serverFiles   from GET /history  [{ filename, url, size_bytes, created_at }]
 * @param {function} onSelect   callback(entry) — called when user clicks a history item
 */
export function renderHistory(serverFiles, onSelect) {
  const container = document.getElementById('historyList');
  if (!container) return;

  const local = loadLocalHistory();
  const localMap = Object.fromEntries(local.map(e => [e.filename, e]));

  if (serverFiles.length === 0) {
    container.innerHTML = `<p class="text-xs text-gray-500 text-center py-8">No generations yet.</p>`;
    return;
  }

  container.innerHTML = serverFiles.map(f => {
    const meta = localMap[f.filename] ?? {};
    const date = new Date((f.created_at ?? meta.createdAt ?? 0) * 1000);
    const dateStr = isNaN(date) ? '' : date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    const prompt = meta.prompt ? escHtml(meta.prompt.slice(0, 80)) + (meta.prompt.length > 80 ? '…' : '') : '<span class="italic text-gray-600">No prompt saved</span>';
    const sizeMb = (f.size_bytes / 1_048_576).toFixed(1);
    return `
      <button type="button"
        data-filename="${escHtml(f.filename)}"
        class="history-item w-full text-left rounded-lg border border-gray-700 bg-gray-800/50
               hover:border-brand/50 hover:bg-gray-800 transition p-3 space-y-1.5">
        <div class="flex items-start gap-2">
          <svg class="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-brand/70" viewBox="0 0 24 24" fill="currentColor">
            <path d="M4 4l16 8-16 8V4z"/>
          </svg>
          <p class="text-xs text-gray-200 leading-snug">${prompt}</p>
        </div>
        <div class="flex items-center gap-2 text-xs text-gray-500">
          ${meta.model ? `<span class="truncate">${escHtml(meta.model)}</span> <span>·</span>` : ''}
          ${meta.task ? `<span>${escHtml(meta.task.replace(/_/g,' '))}</span> <span>·</span>` : ''}
          <span>${sizeMb} MB</span>
          ${dateStr ? `<span>·</span><span class="ml-auto">${dateStr}</span>` : ''}
        </div>
      </button>`;
  }).join('');

  // Wire click handlers
  container.querySelectorAll('.history-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const meta = localMap[btn.dataset.filename] ?? {};
      const serverFile = serverFiles.find(f => f.filename === btn.dataset.filename);
      onSelect({ ...meta, url: serverFile?.url ?? `/exports/${btn.dataset.filename}`, filename: btn.dataset.filename });
    });
  });
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
