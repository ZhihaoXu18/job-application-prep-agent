// Small DOM harness for editor state and pending-request regressions; no browser or network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {
    value: '', checked: false, disabled: false, hidden: false, textContent: '',
    listeners: {}, classList: {toggle() {}},
    addEventListener(name, listener) { (this.listeners[name] ||= []).push(listener); },
  });
  return nodes.get(id);
}
const context = vm.createContext({
  document: {getElementById: node, querySelectorAll: () => [], querySelector: () => ({value: 'url'})},
  fetch: () => new Promise(() => {}), window: {confirm: () => true},
});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname, 'web/app.js'), 'utf8'), context);
const run = (code) => vm.runInContext(code, context);
function ready() {
  run('activeJob = {job_id: "aaaaaaaaaaaa"}; activeReviewRevision = "saved"; reviewDirty = false;');
  node('editedDraft').value = 'Reviewed paragraph';
  node('reviewNotes').value = '';
  for (const id of ['checkPosting', 'checkTerm', 'checkClaims']) node(id).checked = true;
  run('updateReviewProgress()');
}
function input(id) { for (const listener of node(id).listeners.input || []) listener(); }

(async () => {
  ready();
  assert.equal(node('downloadApplication').disabled, false);
  node('editedDraft').value = 'Changed paragraph';
  input('editedDraft');
  assert.equal(node('checkClaims').checked, false);
  assert.equal(node('downloadApplication').disabled, true);

  ready();
  run('api = () => new Promise(resolve => { globalThis.resolveSave = resolve; });');
  const pendingSave = run('saveReview()');
  node('editedDraft').value = 'Edit while saving';
  input('editedDraft');
  run('resolveSave({review: {revision: "new", saved_at: "test time"}})');
  await pendingSave;
  assert.equal(run('reviewDirty'), true);
  assert.equal(run('activeReviewRevision'), 'new');
  assert.equal(node('downloadApplication').disabled, true);

  ready();
  const switchedSave = run('saveReview()');
  run('activeJob = {job_id: "bbbbbbbbbbbb"}; activeReviewRevision = "other";');
  run('resolveSave({review: {revision: "wrong job", saved_at: "test time"}})');
  await switchedSave;
  assert.equal(run('activeReviewRevision'), 'other');

  ready();
  run('downloadText = () => { globalThis.downloaded = true; }; globalThis.downloaded = false;');
  const pendingExport = run('downloadApplication()');
  node('editedDraft').value = 'Edit while exporting';
  input('editedDraft');
  run('resolveSave({filename: "application.txt", text: "Old text"})');
  await pendingExport;
  assert.equal(run('downloaded'), false);
  assert.equal(node('downloadApplication').disabled, true);
  console.log('4 editor/export state regressions passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
