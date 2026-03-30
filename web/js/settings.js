/**
 * settings.js — Theme and app preferences panel.
 *
 * Preferences are persisted to localStorage under 'fv_settings'.
 */

import { deleteHistory } from './api.js';

const SETTINGS_KEY = 'fv_settings';

const THEMES = [
  // Dark base themes
  { id: 'dark',    label: 'Dark',      bg: '#030712', navBg: '#111827', accent: '#6366f1' },
  { id: 'darker',  label: 'Darker',    bg: '#000000', navBg: '#0a0a0a', accent: '#6366f1' },
  // Colour accent themes
  { id: 'indigo',  label: 'Indigo',    bg: '#030712', navBg: '#1e1b4b', accent: '#818cf8' },
  { id: 'rose',    label: 'Rose',      bg: '#0f0505', navBg: '#1c0a0a', accent: '#f43f5e' },
  { id: 'teal',    label: 'Teal',      bg: '#030d0d', navBg: '#0d2424', accent: '#14b8a6' },
  { id: 'amber',   label: 'Amber',     bg: '#0d0800', navBg: '#1a1000', accent: '#f59e0b' },
  { id: 'emerald', label: 'Emerald',   bg: '#020d06', navBg: '#0a1f10', accent: '#10b981' },
  { id: 'violet',  label: 'Violet',    bg: '#06030f', navBg: '#130a2a', accent: '#a855f7' },
  { id: 'sky',     label: 'Sky',       bg: '#020810', navBg: '#061828', accent: '#38bdf8' },
  // Claude-inspired theme (warm off-white tones, rust/orange accent)
  { id: 'claude',  label: 'Claude',    bg: '#1a1410', navBg: '#252018', accent: '#d97706' },
  // High-contrast midnight blue
  { id: 'midnight',label: 'Midnight',  bg: '#010409', navBg: '#0d1117', accent: '#58a6ff' },
  // Soft carbon (near-neutral dark with subtle warm cast)
  { id: 'carbon',  label: 'Carbon',    bg: '#0e0e10', navBg: '#1a1a1e', accent: '#e879f9' },
];

export function loadSettings() {
  try {
    return { theme: 'dark', ...JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? '{}') };
  } catch {
    return { theme: 'dark' };
  }
}

export function saveSettings(prefs) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(prefs));
}

export function applyTheme(themeId) {
  const theme = THEMES.find(t => t.id === themeId) ?? THEMES[0];
  if (window.tailwind) {
    window.tailwind.config = {
      theme: { extend: { colors: { brand: { DEFAULT: theme.accent, dark: theme.accent } } } }
    };
  }
  document.documentElement.style.setProperty('--color-brand', theme.accent);
  document.documentElement.style.setProperty('--color-bg', theme.bg);
  document.documentElement.style.setProperty('--color-nav-bg', theme.navBg);
  document.documentElement.style.backgroundColor = theme.bg;
  document.body.style.backgroundColor = theme.bg;
  const mainCol = document.querySelector('.flex-1.flex.flex-col.overflow-hidden');
  if (mainCol) mainCol.style.backgroundColor = theme.bg;
  const nav = document.querySelector('nav');
  if (nav) nav.style.backgroundColor = theme.navBg;
  const centerPanel = document.getElementById('center-panel');
  if (centerPanel) centerPanel.style.backgroundColor = theme.navBg + 'cc';
}

export function renderSettings(onSave) {
  const container = document.getElementById('settingsPanel');
  if (!container) return;

  const current = loadSettings();

  container.innerHTML = `
    <div class="space-y-6">

      <!-- Theme -->
      <div>
        <h3 class="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">Theme</h3>
        <div class="grid grid-cols-2 gap-2">
          ${THEMES.map(t => `
            <label class="relative cursor-pointer">
              <input type="radio" name="fv_theme" value="${t.id}"
                     ${current.theme === t.id ? 'checked' : ''} class="sr-only peer" />
              <span class="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-700
                           peer-checked:border-brand peer-checked:bg-brand/10 transition text-sm
                           hover:bg-gray-800">
                <span class="w-3 h-3 rounded-full flex-shrink-0 ring-1 ring-white/10"
                      style="background:${t.accent}"></span>
                ${t.label}
              </span>
            </label>`).join('')}
        </div>
      </div>

      <!-- Save theme -->
      <button type="button" id="saveSettingsBtn"
        class="w-full py-2 rounded-lg bg-brand hover:opacity-90 text-sm font-semibold transition">
        Apply Theme
      </button>

      <!-- Divider -->
      <div class="border-t border-gray-800"></div>

      <!-- Data management -->
      <div>
        <h3 class="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-3">Data</h3>
        <div class="space-y-2">

          <button type="button" id="clearHistoryBtn"
            class="w-full py-2 rounded-lg border border-red-800 text-red-400 hover:bg-red-900/30
                   text-sm font-medium transition flex items-center justify-center gap-2">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            Clear Generation History
          </button>

          <button type="button" id="resetAllBtn"
            class="w-full py-2 rounded-lg border border-red-700 text-red-300 hover:bg-red-900/40
                   text-sm font-medium transition flex items-center justify-center gap-2">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0
                   l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7
                   l3.181 3.182m0-4.991v4.99"/>
            </svg>
            Reset All App Data
          </button>

        </div>
        <p id="dataStatusMsg" class="mt-2 text-xs text-center text-gray-600 min-h-[1.25rem]"></p>
      </div>

    </div>`;

  // Apply theme
  document.getElementById('saveSettingsBtn')?.addEventListener('click', () => {
    const selected = container.querySelector('input[name="fv_theme"]:checked')?.value ?? 'dark';
    saveSettings({ ...current, theme: selected });
    applyTheme(selected);
    onSave?.();
  });

  // Clear server history + localStorage history
  document.getElementById('clearHistoryBtn')?.addEventListener('click', async () => {
    const msg = document.getElementById('dataStatusMsg');
    const btn = document.getElementById('clearHistoryBtn');
    if (!confirm('Delete all generation history? This cannot be undone.')) return;
    btn.disabled = true;
    try {
      const { deleted } = await deleteHistory();
      localStorage.removeItem('fv_history');
      msg.textContent = `Cleared ${deleted} history entries.`;
      msg.className = 'mt-2 text-xs text-center text-green-400 min-h-[1.25rem]';
    } catch (e) {
      msg.textContent = 'Error clearing history.';
      msg.className = 'mt-2 text-xs text-center text-red-400 min-h-[1.25rem]';
    } finally {
      btn.disabled = false;
    }
  });

  // Reset everything: server history + all localStorage keys for this app
  document.getElementById('resetAllBtn')?.addEventListener('click', async () => {
    const msg = document.getElementById('dataStatusMsg');
    const btn = document.getElementById('resetAllBtn');
    if (!confirm('Reset ALL app data (history, settings, preferences)? This cannot be undone.')) return;
    btn.disabled = true;
    try {
      await deleteHistory();
      ['fv_history', 'fv_settings', 'fv_batch_queue'].forEach(k => localStorage.removeItem(k));
      msg.textContent = 'All data reset. Reloading...';
      msg.className = 'mt-2 text-xs text-center text-green-400 min-h-[1.25rem]';
      setTimeout(() => location.reload(), 1200);
    } catch (e) {
      msg.textContent = 'Error resetting data.';
      msg.className = 'mt-2 text-xs text-center text-red-400 min-h-[1.25rem]';
      btn.disabled = false;
    }
  });
}
