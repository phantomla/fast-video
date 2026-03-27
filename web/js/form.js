/**
 * form.js — form submit handler, price estimate, and result display.
 */

import { fetchEstimate, submitGeneration, saveHistoryEntry } from './api.js';
import { recordHistory } from './history.js';

// ── Price estimate ────────────────────────────────────────────────────────────

/** Wire all inputs that affect cost to refresh the estimate live. */
export function initPriceEstimate() {
  const ids = ['model', 'sampleCount'];
  ids.forEach(id => {
    document.getElementById(id)?.addEventListener('input', _refreshEstimate);
    document.getElementById(id)?.addEventListener('change', _refreshEstimate);
  });
  document.getElementById('generateAudio')?.addEventListener('change', _refreshEstimate);
  document.getElementById('durationGroup')?.addEventListener('change', _refreshEstimate);
  _refreshEstimate();
}

async function _refreshEstimate() {
  const model       = document.getElementById('model').value;
  const duration    = parseInt(document.querySelector('input[name="duration"]:checked')?.value ?? '8', 10);
  const sampleCount = parseInt(document.getElementById('sampleCount').value, 10);
  const audioOn     = document.getElementById('generateAudio').checked;
  const priceEl     = document.getElementById('priceEstimate');
  const spinner     = document.getElementById('priceSpinner');
  if (!model || !priceEl) return;
  // Show spinner, hide stale price
  spinner?.classList.remove('hidden');
  priceEl.classList.add('hidden');
  try {
    const est = await fetchEstimate(model, duration, sampleCount, audioOn);
    priceEl.textContent = `~$${est.estimated_usd.toFixed(3)} USD`;
    priceEl.title = est.note;
    priceEl.classList.remove('hidden');
  } catch {
    // leave price hidden on error
  } finally {
    spinner?.classList.add('hidden');
  }
}

// ── Form submit ───────────────────────────────────────────────────────────────

export async function handleSubmit(e) {
  e.preventDefault();

  const prompt = document.getElementById('prompt').value.trim();
  if (!prompt) { document.getElementById('prompt').focus(); return; }

  const task          = document.getElementById('task').value;
  const model         = document.getElementById('model').value;
  const duration      = parseInt(document.querySelector('input[name="duration"]:checked')?.value ?? '8', 10);
  const aspectRatio   = document.querySelector('input[name="aspectRatio"]:checked')?.value ?? '16:9';
  const sampleCount   = parseInt(document.getElementById('sampleCount').value, 10);
  const generateAudio = document.getElementById('generateAudio').checked;
  const resolution    = document.querySelector('input[name="resolution"]:checked')?.value ?? '720p';
  const seedRaw       = document.getElementById('seed').value.trim();
  const seed          = seedRaw !== '' ? parseInt(seedRaw, 10) : null;
  const storageUri    = document.getElementById('storageUri').value.trim() || null;
  const imageGcsUri   = document.getElementById('imageGcsUri').value.trim() || null;
  const subjectDesc   = document.getElementById('subjectDesc').value.trim() || null;
  const videoGcsUri   = document.getElementById('videoGcsUri').value.trim() || null;
  const maskGcsUri    = document.getElementById('maskGcsUri').value.trim() || null;

  // GCS URI validation
  for (const [label, val] of [
    ['Image GCS URI', imageGcsUri],
    ['Video GCS URI', videoGcsUri],
    ['Mask GCS URI',  maskGcsUri],
    ['Storage URI',   storageUri],
  ]) {
    if (val && !val.startsWith('gs://')) {
      alert(`${label} must start with gs://`);
      return;
    }
  }

  setGenerating(true);
  hideAll();
  document.getElementById('progressBox').classList.remove('hidden');

  const payload = {
    task,
    prompt,
    model,
    duration,
    image_gcs_uri:       imageGcsUri,
    subject_description: subjectDesc,
    video_gcs_uri:       videoGcsUri,
    mask_gcs_uri:        maskGcsUri,
    config: {
      aspect_ratio:   aspectRatio,
      sample_count:   sampleCount,
      generate_audio: generateAudio,
      resolution,
      seed,
      storage_uri:    storageUri,
    },
  };

  try {
    const { ok, data } = await submitGeneration(payload);
    document.getElementById('progressBox').classList.add('hidden');
    if (!ok) { showError(data.detail ?? JSON.stringify(data)); return; }
    // Record to history (localStorage + SQLite backend)
    const filename = data.file_path.split('/').pop();
    recordHistory(filename, { prompt, model, task, duration, aspectRatio });
    saveHistoryEntry({ filename, prompt, model, task, duration, aspect_ratio: aspectRatio }).catch(() => {});
    showVideo(data, { model, duration, aspectRatio, task });
  } catch (err) {
    document.getElementById('progressBox').classList.add('hidden');
    showError(err.message);
  } finally {
    setGenerating(false);
  }
}

// ── UI state helpers ──────────────────────────────────────────────────────────

export function setGenerating(on) {
  document.getElementById('submitBtn').disabled = on;
  document.getElementById('spinIcon').classList.toggle('hidden', !on);
  document.getElementById('submitLabel').textContent = on ? 'Generating…' : 'Generate Video';
}

export function hideAll() {
  ['placeholder', 'progressBox', 'errorBox'].forEach(id =>
    document.getElementById(id)?.classList.add('hidden')
  );
  const vid = document.getElementById('resultVideo');
  if (vid) { vid.classList.add('hidden'); vid.src = ''; }
}

export function showError(msg) {
  document.getElementById('errorMsg').textContent = msg;
  document.getElementById('errorBox').classList.remove('hidden');
}

export function showVideo(data, { model, duration, aspectRatio, task }) {
  const filename = data.file_path.split('/').pop();
  const url = `/exports/${filename}`;
  const vid = document.getElementById('resultVideo');
  vid.src = url;
  vid.load();
  vid.classList.remove('hidden');
  const dlBtn = document.getElementById('downloadBtn');
  dlBtn.href = url;
  dlBtn.download = filename;
  dlBtn.classList.remove('hidden');
  const meta = `Task: ${task} \u00b7 Model: ${model} \u00b7 ${duration}s \u00b7 ${aspectRatio}`;
  document.getElementById('resultMeta').textContent = meta;
  document.getElementById('previewMeta').textContent = meta;
  // Update draftBox aspect ratio to match
  _setDraftBoxRatio(aspectRatio);
}

function _setDraftBoxRatio(ratio) {
  const box = document.getElementById('draftBox');
  if (!box) return;
  const [w, h] = ratio.split(':').map(Number);
  const r = w / h;
  box.style.aspectRatio = `${w}/${h}`;
  box.style.maxWidth = `calc((100vh - 11rem) * ${r})`;
}
