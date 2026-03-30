/**
 * dashboard.js — Cost Dashboard view.
 * Fetches /dashboard/stats and renders daily + model breakdown tables.
 */

let _days = 30;

export function initDashboard() {
  document.getElementById('dashDaysSelect')?.addEventListener('change', e => {
    _days = parseInt(e.target.value, 10);
    loadDashboard();
  });
  document.getElementById('dashRefreshBtn')?.addEventListener('click', loadDashboard);
}

export async function loadDashboard() {
  const panel = document.getElementById('dashboardPanel');
  if (!panel || panel.classList.contains('hidden')) return;

  _setLoading(true);
  try {
    const res = await fetch(`/dashboard/stats?days=${_days}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    _render(data);
  } catch (err) {
    _renderError(err.message);
  } finally {
    _setLoading(false);
  }
}

function _setLoading(on) {
  const spinner = document.getElementById('dashSpinner');
  const content = document.getElementById('dashContent');
  spinner?.classList.toggle('hidden', !on);
  content?.classList.toggle('hidden', on);
}

function _render(data) {
  // Summary cards
  _setText('dashTotalUsd',  `$${data.total_usd.toFixed(2)}`);
  _setText('dashTotalJobs', String(data.total_jobs));

  // Today cost
  const today = new Date().toISOString().slice(0, 10);
  const todayRow = (data.by_day || []).find(r => r.day === today);
  _setText('dashTodayUsd', todayRow ? `$${todayRow.cost_usd.toFixed(2)}` : '$0.00');

  // Window total
  const windowTotal = (data.by_day || []).reduce((s, r) => s + r.cost_usd, 0);
  _setText('dashWindowUsd', `$${windowTotal.toFixed(2)}`);
  _setText('dashWindowLabel', `Last ${data.window_days}d`);

  // By-day table
  const dayBody = document.getElementById('dashDayBody');
  if (dayBody) {
    if (!data.by_day?.length) {
      dayBody.innerHTML = '<tr><td colspan="3" class="px-4 py-6 text-center text-gray-500 text-xs">No data yet</td></tr>';
    } else {
      dayBody.innerHTML = data.by_day.map(r => `
        <tr class="border-t border-gray-800 hover:bg-gray-800/40 transition">
          <td class="px-4 py-2 text-xs text-gray-300 font-mono">${r.day}</td>
          <td class="px-4 py-2 text-xs text-gray-400 text-right">${r.job_count}</td>
          <td class="px-4 py-2 text-xs text-yellow-400 text-right font-mono">$${r.cost_usd.toFixed(3)}</td>
        </tr>
      `).join('');
    }
  }

  // By-model table
  const modelBody = document.getElementById('dashModelBody');
  if (modelBody) {
    if (!data.by_model?.length) {
      modelBody.innerHTML = '<tr><td colspan="3" class="px-4 py-6 text-center text-gray-500 text-xs">No data yet</td></tr>';
    } else {
      modelBody.innerHTML = data.by_model.map(r => `
        <tr class="border-t border-gray-800 hover:bg-gray-800/40 transition">
          <td class="px-4 py-2 text-xs text-gray-300 font-mono truncate max-w-[180px]" title="${r.model}">${r.model}</td>
          <td class="px-4 py-2 text-xs text-gray-400 text-right">${r.job_count}</td>
          <td class="px-4 py-2 text-xs text-yellow-400 text-right font-mono">$${r.cost_usd.toFixed(3)}</td>
        </tr>
      `).join('');
    }
  }

  // By-type badges
  const typeWrap = document.getElementById('dashTypeWrap');
  if (typeWrap) {
    typeWrap.innerHTML = (data.by_type || []).map(r => `
      <span class="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 text-xs">
        <span class="text-gray-300 capitalize">${r.job_type}</span>
        <span class="text-gray-500">${r.job_count} jobs</span>
        <span class="text-yellow-400 font-mono">$${r.cost_usd.toFixed(2)}</span>
      </span>
    `).join('');
  }
}

function _renderError(msg) {
  const dayBody = document.getElementById('dashDayBody');
  if (dayBody) dayBody.innerHTML = `<tr><td colspan="3" class="px-4 py-4 text-center text-red-400 text-xs">Error: ${msg}</td></tr>`;
}

function _setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}
