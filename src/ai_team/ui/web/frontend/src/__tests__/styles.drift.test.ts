import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..");
const STYLES = join(SRC, "styles");

/** Dynamic className patterns — the allowlist is the documentation (R22.5). */
const DYNAMIC_CLASS_ALLOWLIST = [
  // statusIntent.ts → chip-${intent}
  /^chip-(accent|success|danger|warning|special|neutral)$/,
  /^log-(info|warn|error|success)$/,
  /^alert-(error|warning|info)$/,
  /^phase-(active|done|dim|error|step|arrow|retry)$/,
  /^status-(active|done|error|idle)$/,
  /^(crewai|langgraph|claude)-title$/,
  /^gr-(pass|fail|warn)$/,
  /^compare-col-fold$/,
];

const STRUCTURAL_ALLOWLIST = new Set([
  "run-config-form",
  "run-detail-header",
  "tests-panel",
  "activity-log-wrap",
  "home-empty",
  "home-run-list",
  "home-page",
  "run-detail-page",
  "run-detail-meta",
  "run-tab-overview",
  "run-tab-activity",
  "run-summary-demo-note",
  "panel-inner",
  "run-list-panel",
  "run-list-day-group",
  "coverage-chart",
  "test-failures",
  "command-palette-overlay",
  "arch-panel",
  "form-grid-backend",
  "download-hint",
  "pytest-raw",
  "adr-block",
  "code-view-modes",
  "btn",
  "active",
  "done",
  "compact",
]);

const SPACE_PROPS =
  /^(padding|padding-top|padding-right|padding-bottom|padding-left|padding-inline|padding-block|margin|margin-top|margin-right|margin-bottom|margin-left|margin-inline|margin-block|gap|row-gap|column-gap|border-radius)$/;

function stripCssComments(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, " ");
}

function cssFiles(): { path: string; rel: string; text: string }[] {
  const files = [{ path: join(SRC, "App.css"), rel: "App.css", text: readFileSync(join(SRC, "App.css"), "utf8") }];
  for (const name of readdirSync(STYLES)) {
    if (!name.endsWith(".css")) continue;
    const path = join(STYLES, name);
    files.push({ path, rel: `styles/${name}`, text: readFileSync(path, "utf8") });
  }
  return files;
}

function tsxFiles(): string[] {
  const out: string[] = [];
  const walk = (dir: string) => {
    for (const name of readdirSync(dir, { withFileTypes: true })) {
      const p = join(dir, name.name);
      if (name.isDirectory()) walk(p);
      else if (name.name.endsWith(".tsx")) out.push(p);
    }
  };
  walk(SRC);
  return out;
}

describe("stylesheet drift", () => {
  it("contains no raw spacing or radius values outside tokens.css", () => {
    const failures: string[] = [];
    for (const file of cssFiles()) {
      if (file.rel === "styles/tokens.css") continue;
      file.text.split("\n").forEach((line, i) => {
        const m = line.match(/^\s*([\w-]+)\s*:\s*([^;]+);/);
        if (!m) return;
        const [, prop, val] = m;
        if (!SPACE_PROPS.test(prop)) return;
        if (/var\(--/.test(val)) return;
        if (/^\s*(0|auto|100%|[\d.]+%|1px|2px|-1px)\s*$/.test(val)) return;
        if (!/\d/.test(val)) return;
        if (/\d*\.?\d+(rem|px|em)/.test(val)) {
          const hint = val.includes("px") || val.includes("0.35") ? "var(--space-1)" : "a --space-* or --radius-* token";
          failures.push(`${file.rel}:${i + 1}  ${prop}: ${val.trim()}  → use ${hint}`);
        }
      });
    }
    expect(failures, failures.join("\n")).toEqual([]);
  });

  it("contains no raw font-size values outside tokens.css", () => {
    const failures: string[] = [];
    for (const file of cssFiles()) {
      if (file.rel === "styles/tokens.css") continue;
      file.text.split("\n").forEach((line, i) => {
        const m = line.match(/font-size\s*:\s*([^;]+);/);
        if (!m) return;
        const val = m[1].trim();
        if (val === "inherit" || val === "100%" || val.startsWith("var(--text")) return;
        failures.push(`${file.rel}:${i + 1}  font-size: ${val}  → use var(--text-*)`);
      });
    }
    expect(failures, failures.join("\n")).toEqual([]);
  });

  it("contains no colour literals outside tokens.css", () => {
    const failures: string[] = [];
    for (const file of cssFiles()) {
      if (file.rel === "styles/tokens.css") continue;
      file.text.split("\n").forEach((line, i) => {
        if (/^\s*\/\*/.test(line)) return;
        if (/#[0-9a-fA-F]{3,8}|rgba?\(/.test(line)) {
          failures.push(`${file.rel}:${i + 1}  ${line.trim()}  → use a role/intent/--tint-* token`);
        }
      });
    }
    expect(failures, failures.join("\n")).toEqual([]);
  });

  it("defines no selector twice in one file", () => {
    const failures: string[] = [];
    for (const file of cssFiles()) {
      const counts = new Map<string, number>();
      let depth = 0;
      for (const line of file.text.split("\n")) {
        if (depth === 0 && line.includes("{") && !line.trim().startsWith("@") && !line.trim().startsWith("/*")) {
          const sel = line.split("{")[0].trim();
          if (sel) counts.set(sel, (counts.get(sel) ?? 0) + 1);
        }
        depth += (line.match(/{/g) ?? []).length - (line.match(/}/g) ?? []).length;
      }
      for (const [sel, n] of counts) {
        if (n > 1) failures.push(`${file.rel}  ${sel} defined ${n} times`);
      }
    }
    expect(failures, failures.join("\n")).toEqual([]);
  });

  it("has no CSS class that no component renders", () => {
    const defined = new Set<string>();
    for (const file of cssFiles()) {
      for (const m of stripCssComments(file.text).matchAll(/\.([a-zA-Z][\w-]*)/g)) {
        if (m[1] === "css") continue;
        defined.add(m[1]);
      }
    }
    const used = new Set<string>();
    for (const p of tsxFiles()) {
      const text = readFileSync(p, "utf8");
      for (const m of text.matchAll(/\b([a-zA-Z][\w-]*)\b/g)) {
        if (defined.has(m[1])) used.add(m[1]);
      }
    }
    used.add("chip-accent");
    used.add("chip-success");
    used.add("chip-danger");
    used.add("chip-warning");
    used.add("chip-special");
    used.add("chip-neutral");
    const unused: string[] = [];
    for (const d of defined) {
      if (used.has(d) || STRUCTURAL_ALLOWLIST.has(d)) continue;
      if (DYNAMIC_CLASS_ALLOWLIST.some((re) => re.test(d))) continue;
      if (["before", "after", "where", "not", "root", "hover", "focus", "disabled"].includes(d)) continue;
      unused.push(d);
    }
    expect(unused, unused.sort().join(", ")).toEqual([]);
  });

  it("has no rendered className that no CSS defines", () => {
    const defined = new Set<string>();
    for (const file of cssFiles()) {
      for (const m of stripCssComments(file.text).matchAll(/\.([a-zA-Z][\w-]*)/g)) {
        if (m[1] === "css") continue;
        defined.add(m[1]);
      }
    }
    const missing: string[] = [];
    for (const p of tsxFiles()) {
      if (p.includes("__tests__")) continue;
      const text = readFileSync(p, "utf8");
      const literals = [...text.matchAll(/className="([^"]+)"/g)].flatMap((m) => m[1].split(/\s+/));
      for (const c of literals) {
        if (!c || c.includes("$")) continue;
        if (defined.has(c) || STRUCTURAL_ALLOWLIST.has(c)) continue;
        if (DYNAMIC_CLASS_ALLOWLIST.some((re) => re.test(c))) continue;
        missing.push(`${p.replace(SRC + "/", "")}  .${c}`);
      }
    }
    expect(missing, missing.join("\n")).toEqual([]);
  });

  it("keeps App.css under the line budget", () => {
    const lines = readFileSync(join(SRC, "App.css"), "utf8").split("\n").length;
    expect(lines, `App.css is ${lines} lines (budget 1600)`).toBeLessThanOrEqual(1600);
  });

  it("token contrast pairs meet WCAG floors", () => {
    execFileSync(process.execPath, [join(SRC, "../scripts/check-contrast.mjs")], {
      encoding: "utf8",
    });
  });
});
