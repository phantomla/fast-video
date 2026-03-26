/**
 * tasks.js — task type definitions and conditional field logic.
 * Mirrors backend GenerationTask enum and TASK_DESCRIPTIONS.
 */

export const TASK_DESCRIPTIONS = {
  text_to_video:     'Generate video from a text prompt only.',
  image_to_video:    'Animate a starting image with an optional text prompt.',
  reference_subject: 'Generate video keeping a subject consistent with reference images.',
  reference_style:   'Generate video in the visual style of reference images.',
  video_extension:   'Extend an existing video with new content.',
  inpaint_insert:    'Insert new content into a masked region of a video.',
  inpaint_remove:    'Remove content from a masked region of a video.',
};

/** Allowed duration values (seconds) per task, as enforced by the Vertex AI API. */
export const TASK_DURATIONS = {
  text_to_video:     [4, 6, 8],
  image_to_video:    [4, 6, 8],
  reference_subject: [4, 6, 8],
  reference_style:   [4, 6, 8],
  video_extension:   [4, 6, 8],
  inpaint_insert:    [4, 6, 8],
  inpaint_remove:    [4, 6, 8],
};

/** Which extra field divs to show for each task value. */
export const TASK_FIELDS = {
  text_to_video:     [],
  image_to_video:    ['fieldImageGcs'],
  reference_subject: ['fieldImageGcs', 'fieldSubjectDesc'],
  reference_style:   ['fieldImageGcs'],
  video_extension:   ['fieldVideoGcs'],
  inpaint_insert:    ['fieldVideoGcs', 'fieldMaskGcs'],
  inpaint_remove:    ['fieldVideoGcs', 'fieldMaskGcs'],
};

/** Dynamic label for the image GCS URI input. */
export const IMAGE_GCS_LABELS = {
  image_to_video:    'Input Image (GCS URI)',
  reference_subject: 'Reference Image (GCS URI)',
  reference_style:   'Style Reference Image (GCS URI)',
};

/** All conditional field div IDs (used to hide all before showing relevant ones). */
export const ALL_TASK_FIELDS = ['fieldImageGcs', 'fieldSubjectDesc', 'fieldVideoGcs', 'fieldMaskGcs'];

/**
 * Wire up the task <select> to show/hide conditional fields.
 * Must be called after DOM is ready.
 */
export function initTaskSelector() {
  const sel = document.getElementById('task');
  sel.addEventListener('change', _update);
  _update(); // run once on load
}

function _update() {
  const task = document.getElementById('task').value;

  // Update description hint
  document.getElementById('taskDesc').textContent = TASK_DESCRIPTIONS[task] ?? '';

  // Update image label if applicable
  const label = IMAGE_GCS_LABELS[task];
  if (label) document.getElementById('imageGcsLabel').textContent = label;

  // Show only the relevant fields for this task
  const show = new Set(TASK_FIELDS[task] ?? []);
  ALL_TASK_FIELDS.forEach(id =>
    document.getElementById(id).classList.toggle('hidden', !show.has(id))
  );

  // Re-render duration chips for this task
  _renderDurationChips(TASK_DURATIONS[task] ?? [4, 6, 8]);
}

function _renderDurationChips(durations) {
  const group = document.getElementById('durationGroup');
  if (!group) return;
  const current = parseInt(document.querySelector('input[name="duration"]:checked')?.value ?? '0', 10);
  const selected = durations.includes(current) ? current : durations[0];
  group.innerHTML = durations.map(d => `
    <label class="flex-1">
      <input type="radio" name="duration" value="${d}" ${d === selected ? 'checked' : ''} class="sr-only peer" />
      <span class="block text-center text-xs py-2 rounded-lg border border-gray-700
                   peer-checked:border-brand peer-checked:bg-brand/10 cursor-pointer transition">
        ${d}s
      </span>
    </label>`).join('');
}
