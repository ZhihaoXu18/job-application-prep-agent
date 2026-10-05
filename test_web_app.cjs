// Small DOM harness for editor state and pending-request regressions; no browser or network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {
    value: '', checked: false, disabled: false, hidden: false, textContent: '',
    files: [], children: [], listeners: {}, classList: {toggle() {}},
    append(...items) { this.children.push(...items); },
    replaceChildren(...items) { this.children = items; },
    addEventListener(name, listener) { (this.listeners[name] ||= []).push(listener); },
  });
  return nodes.get(id);
}
const context = vm.createContext({
  document: {getElementById: node, querySelectorAll: () => [], querySelector: () => ({value: 'url'}),
    createElement: () => node(Symbol()), createTextNode: text => ({textContent: text})},
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

  // A delayed status response must not change the currently opened job.
  ready();
  run('activeJob.status_revision = "old status";');
  node('statusSelect').value = 'applied';
  const pendingStatus = run('saveStatus()');
  assert.equal(node('saveStatus').disabled, true);
  run('activeJob = {job_id: "bbbbbbbbbbbb", status: "interview"};');
  run('resolveSave({job: {job_id: "aaaaaaaaaaaa", status: "applied"}})');
  await pendingStatus;
  assert.equal(run('activeJob.job_id'), 'bbbbbbbbbbbb');
  assert.equal(run('activeJob.status'), 'interview');
  assert.equal(node('saveStatus').disabled, false);

  // Catalog refresh retains selection, category changes discard confirmation.
  node('roleFamily').value = 'data';
  run('renderRoleFamilies([{id:"data", label:"数据"}, {id:"finance", label:"金融"}]);');
  assert.equal(node('roleFamily').value, 'data');
  run('directionFingerprint = "fingerprint"; confirmedRoles = ["old"];');
  for (const listener of node('roleFamily').listeners.change) listener();
  assert.equal(run('confirmedRoles'), null);
  assert.equal(run('directionFingerprint'), '');
  assert.equal(node('directionPanel').hidden, true);

  // Presets seed a draft only; no confirmation and no invented resume evidence.
  node('resumeText').value = 'Synthetic resume';
  run('api = (path, options) => { globalThis.directionPayload = JSON.parse(options.body); return new Promise(resolve => { globalThis.resolveDirections = resolve; }); };');
  const presetRequest = run('suggestDirections()');
  await Promise.resolve();
  run('resolveDirections({role_family:{label:"数据",roles:["Data Analyst Co-op"]},suggestions:[],current_roles:[],resume_fingerprint:"test"});');
  await presetRequest;
  assert.equal(run('directionPayload.role_family'), 'data');
  assert.equal(node('directionRoles').value, 'Data Analyst Co-op');
  assert.equal(run('confirmedRoles'), null);
  assert.equal(node('familyResults').hidden, false);
  assert.match(node('directionResults').children[0].textContent, /没有足够明确/);

  // Advanced profile roles retain priority; adding a preset is an unconfirmed edit.
  const profileRequest = run('suggestDirections()');
  await Promise.resolve();
  run('resolveDirections({role_family:{label:"数据",roles:["Data Analyst Co-op"]},suggestions:[],current_roles:["Existing role"],resume_fingerprint:"test"});');
  await profileRequest;
  assert.equal(node('directionRoles').value, 'Existing role');
  run('confirmDirections(); addExplorationRole("Data Analyst Co-op"); addExplorationRole("data analyst co-op");');
  assert.equal(node('directionRoles').value, 'Existing role\nData Analyst Co-op');
  assert.equal(run('confirmedRoles'), null);
  assert.equal(node('directionSearch').hidden, true);

  // Stale responses cannot restore a draft after changing categories.
  const staleRequest = run('suggestDirections()');
  await Promise.resolve();
  for (const listener of node('roleFamily').listeners.change) listener();
  run('resolveDirections({role_family:null,suggestions:[],current_roles:[],resume_fingerprint:"stale"});');
  await staleRequest;
  assert.equal(node('directionPanel').hidden, true);
  assert.equal(run('directionFingerprint'), '');

  // Undecided keeps the existing resume-only path; manual roles stay optional.
  node('roleFamily').value = '';
  const undecidedRequest = run('suggestDirections()');
  await Promise.resolve();
  run('resolveDirections({role_family:null,suggestions:[{role:"Resume role",evidence:["Exact quote"]}],current_roles:[],resume_fingerprint:"test"});');
  await undecidedRequest;
  assert.equal(node('familyResults').hidden, true);
  assert.equal(node('directionRoles').value, 'Resume role');
  assert.equal(run('confirmedRoles'), null);
  console.log('10 editor/export/status/direction state regressions passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
