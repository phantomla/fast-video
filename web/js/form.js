/**
 * form.js — form submit handler, price estimate, and result display.
 */

import { fetchEstimate, submitGeneration } from './api.js';

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
  if (!model || !priceEl) return;
  try {
    const est = await fetchEstimate(model, duration, sampleCount, audioOn);
    priceEl.textContent = `~$${est.estimated_usd.toFixed(3)} USD`;
    priceEl.title = est.note;
    priceEl.classList.remove('invisible');
  } catch {
    priceEl.classList.add('invisible');
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
  ['placeholder', 'progressBox', 'errorBox', 'resultBox'].forEach(id =>
    document.getElementById(id).classList.add('hidden')
  );
}

export function showError(msg) {
  document.getElementById('errorMsg').textContent = msg;
  document.getElementById('errorBox').classList.remove('hidden');
  document.getElementById('placeholder').classList.remove('hidden');
}

export function showVideo(data, { model, duration, aspectRatio, task }) {
  const filename = data.file_path.split('/').pop();
  const url = `/exports/${filename}`;
  const vid = document.getElementById('resultVideo');
  vid.src = url;
  vid.load();
  document.getElementById('downloadBtn').href = url;
  document.getElementById('downloadBtn').download = filename;
  document.getElementById('resultMeta').textContent =
    `Task: ${task} · Model: ${model} · ${duration}s · ${aspectRatio}`;
  document.getElementById('resultBox').classList.remove('hidden');
}
