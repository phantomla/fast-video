/**
 * app.js — entry point. Boots the UI, wires up all modules.
 *
 * Load order: this module imports all others; browser loads via
 *   <script type="module" src="/js/app.js"></script>
 */

import { fetchModels } from './api.js';
import { initTaskSelector } from './tasks.js';
import { initModels } from './models.js';
import { initPriceEstimate, handleSubmit } from './form.js';

async function boot() {
  // ── Task selector ──────────────────────────────────────────
  initTaskSelector();

  // ── Range display labels ───────────────────────────────────
  document.getElementById('sampleCount').addEventListener('input', () => {
    document.getElementById('sampleVal').textContent =
      document.getElementById('sampleCount').value;
  });
  document.getElementById('prompt').addEventListener('input', () => {
    document.getElementById('promptLen').textContent =
      document.getElementById('prompt').value.length;
  });

  // ── Models ─────────────────────────────────────────────────
  const badge = document.getElementById('locationBadge');
  try {
    const { models, default_model, current_location } = await fetchModels();
    badge.innerHTML =
      `<span class="w-2 h-2 rounded-full bg-green-500 inline-block"></span> ${current_location}`;
    initModels(models, default_model);
    initPriceEstimate();
  } catch (err) {
    badge.innerHTML =
      `<span class="w-2 h-2 rounded-full bg-red-500 inline-block"></span> error`;
    document.getElementById('modelList').innerHTML =
      `<p class="text-red-400 text-xs">Failed to load models: ${err.message}</p>`;
  }

  // ── Form ───────────────────────────────────────────────────
  document.getElementById('genForm').addEventListener('submit', handleSubmit);
}

boot();
