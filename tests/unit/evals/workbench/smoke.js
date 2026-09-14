/**
 * Headless smoke test for evals/ui/workbench.html.
 *
 * The page is static and has no build step, so there is no bundler to type-check
 * it and no browser in CI to open it. This shims just enough DOM to prove the
 * render path executes against a real bundle: a page that throws on
 * `loadBundle` is a page nobody can annotate with, and that failure should not
 * wait to be discovered by a human at the start of a sitting.
 *
 * Run via tests/unit/evals/test_workbench_smoke.py, or directly:
 *   node tests/unit/evals/workbench/smoke.js <bundle.json>
 *
 * Exits non-zero with a message on the first failed assertion.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const PAGE = path.join(__dirname, '..', '..', '..', '..', 'evals', 'ui', 'workbench.html');
const bundlePath = process.argv[2];
if (!bundlePath) {
  console.error('usage: node smoke.js <bundle.json>');
  process.exit(2);
}

const failures = [];
const check = (name, cond) => {
  if (cond) console.log(`  ok   ${name}`);
  else { console.log(`  FAIL ${name}`); failures.push(name); }
};

/* ── minimal DOM ────────────────────────────────────────────────────────── */
const mkEl = () => {
  const el = {
    _children: [], value: '', textContent: '', innerHTML: '',
    hidden: false, disabled: false, title: '', style: {}, dataset: {}, files: null,
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    appendChild(c) { this._children.push(c); return c; },
    insertBefore(c) { this._children.push(c); return c; },
    removeChild() {}, remove() {}, addEventListener() {},
    setAttribute() {}, getAttribute: () => null,
    querySelector: () => null, querySelectorAll: () => [],
    focus() {}, blur() {}, scrollIntoView() {}, click() {},
    get closest() { return () => el; },
  };
  return el;
};
const nodes = new Map();
global.document = {
  documentElement: mkEl(),
  body: mkEl(),
  createElement: mkEl,
  addEventListener() {},
  querySelector(sel) {
    const key = sel.replace(/^#/, '');
    if (!nodes.has(key)) nodes.set(key, mkEl());
    return nodes.get(key);
  },
  querySelectorAll: () => [],
};
global.window = { addEventListener() {} };
global.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
global.matchMedia = () => ({ matches: false });
global.setInterval = () => 0;
global.setTimeout = () => 0;
global.Blob = class {};
global.URL = { createObjectURL: () => 'blob:x', revokeObjectURL() {} };
// navigator is getter-only on modern Node; define it rather than assign.
Object.defineProperty(global, 'navigator', {
  value: { clipboard: { writeText: () => Promise.resolve() } },
  configurable: true, writable: true,
});
global.prompt = () => null;

/* ── load the page's script ─────────────────────────────────────────────── */
const html = fs.readFileSync(PAGE, 'utf8');
const js = html.slice(html.indexOf('<script>') + 8, html.lastIndexOf('</script>'));
const api = (0, eval)(
  js.replace("'use strict';", '') +
  ';({loadBundle, renderCard, saveCurrent, clusterCodes, gateState, buildYaml, ' +
  'normalizeTag, wilson, saturationStreak, S})'
);
const { loadBundle, renderCard, saveCurrent, clusterCodes, gateState, buildYaml,
        normalizeTag, wilson, saturationStreak, S } = api;

console.log('workbench smoke');

/* ── bundle loading ─────────────────────────────────────────────────────── */
const loaded = loadBundle(fs.readFileSync(bundlePath, 'utf8'));
check('loadBundle accepts a bundle from `annotate bundle`', loaded === true);
check('all traces are loaded', S.traces.length > 0 && S.order.length === S.traces.length);

/* ── refusals ───────────────────────────────────────────────────────────── */
check('refuses a bundle with no sample_id', loadBundle('{"traces":[{"trace_id":"x"}]}') !== true);
check('refuses a bundle with no traces', loadBundle('{"sample_id":"s","traces":[]}') !== true);
check('refuses malformed JSON', loadBundle('{nope') !== true);
loadBundle(fs.readFileSync(bundlePath, 'utf8'));  // reload the good one

/* ── the card ───────────────────────────────────────────────────────────── */
renderCard();
const card = document.querySelector('#cardBody').innerHTML;
check('card renders something', card.length > 200);

const withSpans = S.traces.find(t => (t.spans || []).length);
const withoutSpans = S.traces.find(t => !(t.spans || []).length);
if (withSpans) {
  S.idx = S.order.indexOf(withSpans.trace_id);
  renderCard();
  const c = document.querySelector('#cardBody').innerHTML;
  check('a trace with spans renders the phase timeline', c.includes('Phase timeline'));
  check('a trace with spans renders the span picker', c.includes('ev selectable'));
  check('a trace with spans shows no starvation panel', !c.includes('No spans.'));
}
if (withoutSpans) {
  S.idx = S.order.indexOf(withoutSpans.trace_id);
  renderCard();
  const c = document.querySelector('#cardBody').innerHTML;
  // Starvation is a finding, not an empty state (eval-coverage README).
  check('a trace with no spans names the absence', c.includes('No spans.'));
}

/* ── coding and the mechanical stages ───────────────────────────────────── */
S.idx = 0;
S.draft.tags = ['Retry Storm', 'retry-storm'];
document.querySelector('#noteInput').value = 'smoke note';
saveCurrent(false);
check('saveCurrent records the trace', S.records.size === 1);

const clusters = clusterCodes();
check('two spellings collapse to one category', clusters.length === 1 && clusters[0].count === 2);
check('cluster keeps both spellings', clusters[0].variants.length === 2);
check('normalizeTag matches propose.normalize_tag', normalizeTag('Retry Storm') === 'retry_storm');
check('normalizeTag handles punctuation-only input', normalizeTag('!!!') === 'unnamed');

const w = wilson(10, 100);
check('wilson matches reliability.wilson_ci',
  Math.abs(w[0] - 0.055229) < 1e-6 && Math.abs(w[1] - 0.174367) < 1e-6);
check('saturationStreak matches annotate.saturation_streak',
  saturationStreak([['a'], [], [], ['b'], [], [], []].map(tags => ({ tags }))) === 3);

/* ── gates ──────────────────────────────────────────────────────────────── */
check('stage 2 is locked below 30 unaided records', gateState().s2.open === false);
for (let i = 0; i < 30; i++) {
  S.records.set('syn-' + i, { trace_id: 'syn-' + i, tags: ['a'], note: '', coded_at: i, unaided: true });
}
check('stage 2 unlocks at 30 unaided records', gateState().s2.open === true);
check('stage 3 stays locked with no accepted category', gateState().s3.open === false);
check('stage 4 is never open by default', gateState().s4.open === false);
check('buildYaml degrades safely with nothing accepted',
  buildYaml().startsWith('# No accepted categories.'));

/* ── R7.3: the page must not ship taxonomy vocabulary as suggestions ───── */
const stage1 = html.slice(html.indexOf('id="stage1"'), html.indexOf('id="stage2"'));
check('no FM ids inside the open-coding stage', !/FM-\d{3}/.test(stage1));
check('no taxonomy slugs embedded anywhere', !html.includes('tool_call_omission'));

console.log(failures.length ? `\n${failures.length} failed` : '\nall passed');
process.exit(failures.length ? 1 : 0);
