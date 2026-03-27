/**
 * settings.js — Theme and app preferences panel.
 *
 * Preferences are persisted to localStorage under 'fv_settings'.
 */

const SETTINGS_KEY = 'fv_settings';

const THEMES = [
  { id: 'dark',   label: 'Dark',   bg: '#030712', navBg: '#111827', accent: '#6366f1' },
  { id: 'darker', label: 'Darker', bg: '#000000', navBg: '#0a0a0a', accent: '#6366f1' },
  { id: 'indigo', label: 'Indigo', bg: '#030712', navBg: '#1e1b4b', accent: '#818cf8' },
  { id: 'rose',   label: 'Rose',   bg: '#0f0505', navBg: '#1c0a0a', accent: '#f43f5e' },
  { id: 'teal',   label: 'Teal',   bg: '#030d0d', navBg: '#0d2424', accent: '#14b8a6' },
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
  // Update Tailwind config accent (brand colour)
  if (window.tailwind) {
    window.tailwind.config = {
      theme: { extend: { colors: { brand: { DEFAULT: theme.accent, dark: theme.accent } } } }
    };
  }
  // Store CSS variables for JS-driven usage
  document.documentElement.style.setProperty('--color-brand', theme.accent);
  document.documentElement.style.setProperty('--color-bg', theme.bg);
  document.documentElement.style.setProperty('--color-nav-bg', theme.navBg);
  // Apply background colors directly via inline styles
  document.documentElement.style.backgroundColor = theme.bg;
  document.body.style.backgroundColor = theme.bg;
  // Right main column
  const mainCol = document.querySelector('.flex-1.flex.flex-col.overflow-hidden');
  if (mainCol) mainCol.style.backgroundColor = theme.bg;
  // Left nav and center panel
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

      <!-- Divider -->
      <div class="border-t border-gray-800"></div>

      <!-- Save -->
      <button type="button" id="saveSettingsBtn"
        class="w-full py-2 rounded-lg bg-brand hover:bg-brand-dark text-sm font-semibold transition">
        Apply
      </button>
    </div>`;

  document.getElementById('saveSettingsBtn')?.addEventListener('click', () => {
    const selected = container.querySelector('input[name="fv_theme"]:checked')?.value ?? 'dark';
    saveSettings({ ...current, theme: selected });
    applyTheme(selected);
    onSave?.();
  });
}
