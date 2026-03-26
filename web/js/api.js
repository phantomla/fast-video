/**
 * api.js — all network calls to the backend.
 * Import this module wherever you need to talk to the server.
 */

/** Load the full model list + location metadata. */
export async function fetchModels() {
  const res = await fetch('/models');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/**
 * Fetch a cost estimate from the backend.
 * @param {string} model
 * @param {number} duration   seconds
 * @param {number} sampleCount
 * @param {boolean} generateAudio
 */
export async function fetchEstimate(model, duration, sampleCount, generateAudio) {
  const params = new URLSearchParams({
    model,
    duration,
    sample_count: sampleCount,
    generate_audio: generateAudio ? 'true' : 'false',
  });
  const res = await fetch(`/estimate?${params}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/**
 * Submit a generation job. Returns { ok: bool, data: object }.
 * @param {object} payload  matches VideoGenerationRequest schema
 */
export async function submitGeneration(payload) {
  const res = await fetch('/generate-one', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  return { ok: res.ok, data };
}
