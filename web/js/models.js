/**
 * models.js — model dropdown population and model info card rendering.
 * Also manages the audio toggle's enabled/disabled state per model.
 */

/**
 * Populate the model <select>, render the info card,
 * and wire the audio toggle sync on model change.
 *
 * @param {Array} models        list from GET /models
 * @param {string} defaultModel default model_id
 */
export function initModels(models, defaultModel) {
  _populateSelect(models, defaultModel);
  renderModelList(models);
  _syncAudioToggle(models, document.getElementById('model').value);

  document.getElementById('model').addEventListener('change', e =>
    _syncAudioToggle(models, e.target.value)
  );

  // Model info modal
  const modal = document.getElementById('modelModal');
  document.getElementById('modelInfoBtn').addEventListener('click', () =>
    modal.classList.remove('hidden')
  );
  document.getElementById('modelModalClose').addEventListener('click', () =>
    modal.classList.add('hidden')
  );
  modal.addEventListener('click', e => {
    if (e.target === modal) modal.classList.add('hidden');
  });
}

function _populateSelect(models, defaultModel) {
  const sel = document.getElementById('model');
  sel.innerHTML = '';
  models.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.model_id;
    opt.textContent = `${m.display_name}  (${m.model_id})`;
    if (!m.active_at_current_location) opt.textContent += '  ⚠ not at location';
    if (m.model_id === defaultModel) opt.selected = true;
    sel.appendChild(opt);
  });
}

/** Render the "Available Models" info card. */
export function renderModelList(models) {
  document.getElementById('modelList').innerHTML = models.map(m => `
    <div class="flex items-start gap-2 py-1.5 border-b border-gray-800 last:border-0">
      <span class="mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${m.active_at_current_location ? 'bg-green-500' : 'bg-gray-600'}"></span>
      <div>
        <span class="font-medium text-gray-300">${m.display_name}</span>
        <code class="ml-1.5 text-gray-500 text-xs">${m.model_id}</code>
        <span class="ml-2 text-xs text-yellow-500/80">$${m.price_per_second_usd.toFixed(2)}/s</span>
        ${m.supports_audio ? '<span class="ml-1 text-xs text-purple-400">♪ audio</span>' : ''}
        <p class="text-gray-600 mt-0.5 text-xs">${m.description}</p>
      </div>
    </div>`).join('');
}

function _syncAudioToggle(models, selectedId) {
  const m = models.find(x => x.model_id === selectedId);
  const checkbox = document.getElementById('generateAudio');
  const wrap = document.getElementById('audioToggleWrap');
  if (!m || !checkbox) return;

  const supported = !!m.supports_audio;
  checkbox.disabled = !supported;
  if (!supported) checkbox.checked = false;
  wrap.title = supported ? '' : `Audio not supported on ${m.display_name}`;
  wrap.classList.toggle('opacity-40', !supported);
  wrap.classList.toggle('cursor-not-allowed', !supported);
}
