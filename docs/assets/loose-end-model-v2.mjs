// A browser draft is a visitor's words, never a generated diagnosis or estimate.
export const draftKey = 'mg-loose-end-v1';
export const roomKey = 'mg-workbench-v1';
export const fields = ['intent', 'making', 'difficulty', 'people', 'outcome', 'constraints', 'timing', 'budget', 'materials'];
export const followups = ['timing', 'budget', 'materials'];
export const briefLimit = 24000;
export const intents = ['I have an idea.', 'Something isn’t working.', 'I need another pair of eyes.', 'I can’t quite name it yet.'];
export const labels = ['Starting point', 'What I’m trying to make or change', 'Where it gets difficult', 'Who encounters it', 'A useful change would look like', 'Constraints', 'Timing', 'Working budget', 'Existing material'];
export function normalizeDraft(input) {
  const result = {};
  for (const key of fields) result[key] = typeof input?.[key] === 'string' ? input[key].trim().slice(0, 1800) : '';
  if (!intents.includes(result.intent)) result.intent = intents[3];
  return result;
}
export function readDraft(storage) {
  try {
    const value = JSON.parse(storage.getItem(draftKey));
    if (value?.version !== 1) return null;
    const draft = normalizeDraft(value.answers);
    return draft.making ? draft : null;
  } catch { return null; }
}
export function briefText(input) {
  const draft = normalizeDraft(input);
  return 'A LOOSE END — MOTH & GRAVEL\n\n' + fields.flatMap((key, i) => followups.includes(key) && !draft[key] ? [] : [labels[i] + '\n' + (draft[key] || 'Still open.')]).join('\n\n') +
    '\n\nThese are my words, ready for a conversation. This is not a quote or an agreed project.\n';
}
