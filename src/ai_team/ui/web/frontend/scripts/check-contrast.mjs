#!/usr/bin/env node
/**
 * Assert token contrast pairs meet WCAG floors (R14.5).
 * Text pairs ≥ 4.5:1; boundary pairs ≥ 3:1.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const css = readFileSync(join(root, "src/styles/tokens.css"), "utf8");

function token(name) {
  const m = css.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{3,8})`));
  if (!m) throw new Error(`token ${name} not found`);
  return m[1];
}

function hexToRgb(hex) {
  const h = hex.replace("#", "");
  const n = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  return [0, 2, 4].map((i) => parseInt(n.slice(i, i + 2), 16) / 255);
}

function lin(c) {
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function luminance(hex) {
  const [r, g, b] = hexToRgb(hex).map(lin);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a, b) {
  const l1 = luminance(a);
  const l2 = luminance(b);
  const [hi, lo] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (hi + 0.05) / (lo + 0.05);
}

const canvas = token("--bg-canvas");
const surface = token("--bg-surface");
const raised = token("--bg-raised");
const fg = token("--fg-default");
const muted = token("--fg-muted");
const border = token("--border-default");
const accent = token("--intent-accent");
const success = token("--intent-success");
const danger = token("--intent-danger");
const warning = token("--intent-warning");
const special = token("--intent-special");

const textPairs = [
  ["--fg-default on --bg-canvas", fg, canvas, 4.5],
  ["--fg-muted on --bg-canvas", muted, canvas, 4.5],
  ["--fg-muted on --bg-raised", muted, raised, 4.5],
  ["--intent-accent on --bg-canvas", accent, canvas, 4.5],
  ["--intent-success on --bg-canvas", success, canvas, 4.5],
  ["--intent-danger on --bg-canvas", danger, canvas, 4.5],
  ["--intent-warning on --bg-canvas", warning, canvas, 4.5],
  ["--intent-special on --bg-canvas", special, canvas, 4.5],
  ["--bg-canvas on --intent-accent (primary button)", canvas, accent, 4.5],
  ["--bg-canvas on --intent-danger (danger button)", canvas, danger, 4.5],
];

const boundaryPairs = [
  ["--border-default on --bg-canvas", border, canvas, 3],
  ["--border-default on --bg-surface", border, surface, 3],
  ["--border-default on --bg-raised", border, raised, 3],
];

let failed = 0;
for (const [label, a, b, min] of [...textPairs, ...boundaryPairs]) {
  const ratio = contrast(a, b);
  if (ratio < min) {
    console.error(`FAIL ${label}: ${ratio.toFixed(2)}:1 < ${min}:1 (${a} vs ${b})`);
    failed += 1;
  } else {
    console.log(`ok   ${label}: ${ratio.toFixed(2)}:1`);
  }
}

if (failed) {
  process.exit(1);
}
