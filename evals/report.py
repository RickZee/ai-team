"""Emit suite reports: JSON, Markdown, HTML, summary.txt (R13).

HTML is self-contained (Jinja2, inline SVG, no CDN). Charts:
stacked failure incidence by taxonomy layer, and guardrail PR curves.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import BaseLoader, Environment, select_autoescape

from evals.aggregate import LayerIncidence, SuiteReport
from evals.metrics import format_scorecard as format_scorecard  # re-export R13.5

_RESULTS_ROOT = Path("evals/results")

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Eval report {{ report.run_id }}</title>
<style>
  :root { --fg: #1a1a1a; --muted: #555; --fail: #b00020; --pass: #0b6e4f; --bg: #f7f5f2; }
  body { font-family: "IBM Plex Sans", "Segoe UI", sans-serif; color: var(--fg);
         background: linear-gradient(160deg, #f7f5f2 0%, #e8eef2 100%);
         margin: 0; padding: 2rem; line-height: 1.45; }
  h1 { font-size: 1.6rem; margin: 0 0 0.25rem; }
  h2 { font-size: 1.15rem; margin-top: 1.75rem; border-bottom: 1px solid #ccc; padding-bottom: 0.25rem; }
  .headline { font-size: 1.1rem; font-weight: 600; }
  .verdict-pass { color: var(--pass); }
  .verdict-fail { color: var(--fail); }
  .muted { color: var(--muted); font-size: 0.9rem; }
  table { border-collapse: collapse; width: 100%; max-width: 960px; background: #fff; }
  th, td { border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.9rem; }
  th { background: #eef2f5; }
  svg.chart { background: #fff; border: 1px solid #ddd; margin: 0.5rem 0 1rem; }
  code { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 0.85rem; }
  ul.failed { padding-left: 1.2rem; }
</style>
</head>
<body>
  <h1>Eval suite report</h1>
  <p class="muted">run_id=<code>{{ report.run_id }}</code> · tier={{ report.tier }} ·
     generated_at={{ report.generated_at }}</p>
  <p class="headline verdict-{{ report.verdict }}">{{ report.headline }}</p>

  <h2>1. Headline verdict</h2>
  <p>Verdict: <strong>{{ report.verdict }}</strong></p>

  <h2>2. Scorecard</h2>
  <table>
    <thead><tr><th>Backend</th><th>Scenario</th><th>Outcome</th><th>pass^k</th>
    <th>pass_rate</th><th>n</th><th>95% CI</th></tr></thead>
    <tbody>
    {% for c in report.scorecard %}
      <tr>
        <td>{{ c.backend }}</td><td>{{ c.scenario_id }}</td>
        <td>{{ c.outcome }}</td>
        <td>{{ "%.3f"|format(c.pass_pow_k) }}</td>
        <td>{{ "%.3f"|format(c.pass_rate) }} (n={{ c.n }})</td>
        <td>{{ c.n }}</td>
        <td>[{{ "%.3f"|format(c.wilson_ci[0]) }}, {{ "%.3f"|format(c.wilson_ci[1]) }}]</td>
      </tr>
    {% else %}
      <tr><td colspan="7" class="muted">No scorecard cells</td></tr>
    {% endfor %}
    </tbody>
  </table>

  <h2>3. Regressions vs baseline</h2>
  <p class="muted">See gate output / CI summary for baseline diff.</p>

  <h2>4. Failure-mode incidence</h2>
  <table>
    <thead><tr><th>FM</th><th>Layer</th><th>Raw rate</th><th>Bias-corrected</th><th>Fails</th></tr></thead>
    <tbody>
    {% for fm in report.failure_mode_incidence %}
      <tr>
        <td>{{ fm.failure_mode_id }}</td><td>{{ fm.layer }}</td>
        <td>{{ fm.raw.format() }}</td>
        <td>{% if fm.raw.bias_corrected is not none %}{{ "%.3f"|format(fm.raw.bias_corrected) }}
            {% elif fm.raw.bias_corrected_suppressed %}suppressed{% else %}—{% endif %}</td>
        <td>{{ fm.fail_count }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>

  <h2>5. Reliability budget by layer</h2>
  {{ layer_svg | safe }}

  <h2>6. Judge alignment</h2>
  <table>
    <thead><tr><th>Judge</th><th>Eligible</th><th>TPR</th><th>TNR</th><th>κ</th></tr></thead>
    <tbody>
    {% for j in report.judges %}
      <tr>
        <td>{{ j.judge_id }}</td>
        <td>{{ j.eligible_to_gate }}</td>
        <td>{{ j.tpr if j.tpr is not none else "—" }}</td>
        <td>{{ j.tnr if j.tnr is not none else "—" }}</td>
        <td>{{ j.kappa if j.kappa is not none else "—" }}</td>
      </tr>
    {% else %}
      <tr><td colspan="5" class="muted">No judges in this run</td></tr>
    {% endfor %}
    </tbody>
  </table>
  {% if report.suppressed %}
  <h3>Suppressed</h3>
  <ul>{% for s in report.suppressed %}<li><code>{{ s }}</code></li>{% endfor %}</ul>
  {% endif %}

  <h2>7. Guardrail precision-recall</h2>
  {{ pr_svg | safe }}
  <table>
    <thead><tr><th>Guardrail</th><th>n</th><th>Precision</th><th>Recall</th><th>FPR</th><th>Provisional</th></tr></thead>
    <tbody>
    {% for g in report.guardrails %}
      <tr>
        <td>{{ g.name }}</td><td>{{ g.n }}</td>
        <td>{{ g.precision if g.precision is not none else "—" }}</td>
        <td>{{ g.recall if g.recall is not none else "—" }}</td>
        <td>{{ g.fpr if g.fpr is not none else "—" }}</td>
        <td>{{ g.provisional }}</td>
      </tr>
    {% else %}
      <tr><td colspan="6" class="muted">No guardrail metrics</td></tr>
    {% endfor %}
    </tbody>
  </table>

  <h2>8. Cost and latency</h2>
  <p>Cost: ${{ "%.4f"|format(report.cost.total_usd) }}
     {% if report.cost.ceiling_usd is not none %}(ceiling ${{ "%.2f"|format(report.cost.ceiling_usd) }}){% endif %}</p>
  <p>Latency p95:
     {% if report.latency.p95_s is not none %}{{ "%.2f"|format(report.latency.p95_s) }}s{% else %}n/a{% endif %}
     (n={{ report.latency.n }})</p>

  <h2>9. Flaky cells</h2>
  {% if report.flaky_cells %}
  <ul>{% for f in report.flaky_cells %}<li><code>{{ f }}</code></li>{% endfor %}</ul>
  {% else %}
  <p class="muted">None</p>
  {% endif %}

  <h2>10. Failed checks</h2>
  <ul class="failed">
  {% for f in report.failed_checks %}
    <li><code>{{ f.check_id }}</code> · trace=<code>{{ f.trace_id }}</code>
        · span=<code>{{ f.span_id or "n/a" }}</code>
        {% if f.evidence_text %} — {{ f.evidence_text[:120] }}{% endif %}</li>
  {% else %}
    <li class="muted">None</li>
  {% endfor %}
  </ul>

  <h2>11. Provenance</h2>
  <pre>{{ provenance_json }}</pre>
</body>
</html>
"""


def _layer_stacked_svg(layers: list[LayerIncidence], *, width: int = 520, height: int = 220) -> str:
    """Hand-built stacked bar: fail counts by taxonomy layer."""
    colors = {
        "model": "#3d5a80",
        "framework": "#ee6c4d",
        "harness": "#98c1d9",
        "provider": "#293241",
    }
    margin_l, margin_b, margin_t = 48, 36, 24
    chart_w = width - margin_l - 24
    chart_h = height - margin_b - margin_t
    max_fail = max((layer.fail_count for layer in layers), default=1) or 1
    bar_w = chart_w / max(len(layers), 1) * 0.6
    parts = [
        f'<svg class="chart" xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Failure incidence by layer">'
    ]
    total_fails = sum(layer.fail_count for layer in layers)
    parts.append(
        f'<text x="{margin_l}" y="16" font-size="12" fill="#333">'
        f"Failure incidence by taxonomy layer (total fails={total_fails})</text>"
    )
    for i, layer in enumerate(layers):
        x = margin_l + i * (chart_w / max(len(layers), 1)) + 12
        h = (layer.fail_count / max_fail) * chart_h
        y = margin_t + chart_h - h
        color = colors.get(layer.layer, "#888")
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{height - 12}" text-anchor="middle" '
            f'font-size="11" fill="#333">{layer.layer}</text>'
        )
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{y - 4:.1f}" text-anchor="middle" '
            f'font-size="10" fill="#333">{layer.fail_count}</text>'
        )
    parts.append(
        f'<line x1="{margin_l}" y1="{margin_t + chart_h}" x2="{width - 16}" '
        f'y2="{margin_t + chart_h}" stroke="#999"/>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _guardrail_pr_svg(report: SuiteReport, *, width: int = 520, height: int = 260) -> str:
    """Hand-built precision-recall curves per guardrail."""
    margin = 40
    plot_w = width - 2 * margin
    plot_h = height - 2 * margin
    parts = [
        f'<svg class="chart" xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Guardrail precision-recall">'
    ]
    parts.append(
        f'<text x="{margin}" y="16" font-size="12" fill="#333">Guardrail precision-recall</text>'
    )
    # axes
    parts.append(
        f'<line x1="{margin}" y1="{margin + plot_h}" x2="{margin + plot_w}" '
        f'y2="{margin + plot_h}" stroke="#999"/>'
    )
    parts.append(
        f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{margin + plot_h}" stroke="#999"/>'
    )
    parts.append(
        f'<text x="{margin + plot_w / 2}" y="{height - 8}" text-anchor="middle" '
        f'font-size="10" fill="#555">recall</text>'
    )
    parts.append(
        f'<text x="12" y="{margin + plot_h / 2}" text-anchor="middle" font-size="10" '
        f'fill="#555" transform="rotate(-90 12 {margin + plot_h / 2})">precision</text>'
    )

    palette = ["#3d5a80", "#ee6c4d", "#0b6e4f", "#7b2d8e"]
    any_curve = False
    for idx, g in enumerate(report.guardrails):
        if not g.pr_curve:
            # single point from precision/recall if available
            if g.precision is None or g.recall is None:
                continue
            pts = [{"recall": g.recall, "precision": g.precision}]
        else:
            pts = g.pr_curve
        any_curve = True
        color = palette[idx % len(palette)]
        coords: list[str] = []
        for p in pts:
            rx = float(p.get("recall", 0.0))
            py = float(p.get("precision", 0.0))
            x = margin + rx * plot_w
            y = margin + plot_h - py * plot_h
            coords.append(f"{x:.1f},{y:.1f}")
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>')
        if len(coords) >= 2:
            parts.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{" ".join(coords)}"/>'
            )
        parts.append(
            f'<text x="{margin + plot_w - 4}" y="{margin + 14 + idx * 14}" '
            f'text-anchor="end" font-size="10" fill="{color}">{g.name}</text>'
        )
    if not any_curve:
        parts.append(
            f'<text x="{margin + 8}" y="{margin + plot_h / 2}" font-size="11" fill="#888">'
            f"No PR curve data (guardrail corpus empty or provisional)</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def _md_rate(rate: Any) -> str:
    return rate.format() if hasattr(rate, "format") else str(rate)


def render_markdown(report: SuiteReport) -> str:
    """Render the human Markdown report in R13.2 section order."""
    lines: list[str] = [
        f"# Eval suite report — `{report.run_id}`",
        "",
        f"**Verdict:** {report.verdict} — {report.headline}",
        "",
        f"Tier `{report.tier}` · generated_at `{report.generated_at.isoformat()}`",
        "",
        "## 1. Headline verdict",
        "",
        report.headline,
        "",
        "## 2. Scorecard",
        "",
        "| Backend | Scenario | Outcome | pass^k | pass_rate | n | 95% CI |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for c in report.scorecard:
        lo, hi = c.wilson_ci
        lines.append(
            f"| {c.backend} | {c.scenario_id} | {c.outcome} | {c.pass_pow_k:.3f} | "
            f"{c.pass_rate:.3f} | {c.n} | [{lo:.3f}, {hi:.3f}] |"
        )
    if not report.scorecard:
        lines.append("| — | — | — | — | — | 0 | — |")

    lines.extend(["", "## 3. Regressions vs baseline", "", "_See gate / CI summary._", ""])

    lines.extend(
        [
            "## 4. Failure-mode incidence",
            "",
            "| FM | Layer | Raw rate | Bias-corrected | Fails |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for fm in report.failure_mode_incidence:
        bc = (
            f"{fm.raw.bias_corrected:.3f}"
            if fm.raw.bias_corrected is not None
            else ("suppressed" if fm.raw.bias_corrected_suppressed else "—")
        )
        lines.append(
            f"| {fm.failure_mode_id} | {fm.layer} | {_md_rate(fm.raw)} | {bc} | {fm.fail_count} |"
        )

    lines.extend(["", "## 5. Reliability budget by layer", ""])
    for layer in report.layer_incidence:
        lines.append(f"- **{layer.layer}**: {_md_rate(layer.rate)} (fails={layer.fail_count})")

    lines.extend(["", "## 6. Judge alignment", ""])
    if report.judges:
        lines.append("| Judge | Eligible | TPR | TNR | κ |")
        lines.append("| --- | --- | --- | --- | --- |")
        for j in report.judges:
            lines.append(f"| {j.judge_id} | {j.eligible_to_gate} | {j.tpr} | {j.tnr} | {j.kappa} |")
    else:
        lines.append("_No judges in this run._")
    if report.suppressed:
        lines.extend(["", "### Suppressed", ""])
        for s in report.suppressed:
            lines.append(f"- `{s}`")

    lines.extend(["", "## 7. Guardrail precision-recall", ""])
    if report.guardrails:
        lines.append("| Guardrail | n | Precision | Recall | FPR | Provisional |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for g in report.guardrails:
            lines.append(
                f"| {g.name} | {g.n} | {g.precision} | {g.recall} | {g.fpr} | {g.provisional} |"
            )
    else:
        lines.append("_No guardrail metrics._")

    lines.extend(
        [
            "",
            "## 8. Cost and latency",
            "",
            f"- Cost: `${report.cost.total_usd:.4f}`",
            f"- Latency p95: "
            f"{f'{report.latency.p95_s:.2f}s' if report.latency.p95_s is not None else 'n/a'} "
            f"(n={report.latency.n})",
            "",
            "## 9. Flaky cells",
            "",
        ]
    )
    if report.flaky_cells:
        for cell_name in report.flaky_cells:
            lines.append(f"- `{cell_name}`")
    else:
        lines.append("_None._")

    lines.extend(["", "## 10. Failed checks", ""])
    if report.failed_checks:
        for failed in report.failed_checks:
            lines.append(
                f"- `{failed.check_id}` · trace=`{failed.trace_id}` · "
                f"span=`{failed.span_id or 'n/a'}`"
            )
    else:
        lines.append("_None._")

    lines.extend(
        [
            "",
            "## 11. Provenance",
            "",
            "```json",
            json.dumps(report.provenance.model_dump(mode="json"), indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def render_html(report: SuiteReport) -> str:
    """Render a self-contained HTML report (no CDN, inline SVG)."""
    env = Environment(loader=BaseLoader(), autoescape=select_autoescape(["html", "xml"]))
    template = env.from_string(_HTML_TEMPLATE)
    return template.render(
        report=report,
        layer_svg=_layer_stacked_svg(report.layer_incidence),
        pr_svg=_guardrail_pr_svg(report),
        provenance_json=json.dumps(
            report.provenance.model_dump(mode="json"), indent=2, sort_keys=True
        ),
    )


def render_summary(report: SuiteReport, *, max_lines: int = 20) -> str:
    """Emit ≤ *max_lines* summary suitable for Slack / commit messages (R13.6)."""
    lines = [
        f"eval[{report.tier}] {report.verdict}: {report.headline}",
        f"run_id={report.run_id} cost=${report.cost.total_usd:.4f}",
        f"failed_checks={len(report.failed_checks)} flaky={len(report.flaky_cells)}",
    ]
    for f in report.failed_checks[:8]:
        lines.append(f"  FAIL {f.check_id} trace={f.trace_id} span={f.span_id or 'n/a'}")
    for layer in report.layer_incidence:
        if layer.fail_count:
            lines.append(f"  layer[{layer.layer}] fails={layer.fail_count} {_md_rate(layer.rate)}")
    lines.append(f"git={report.provenance.git_sha[:12]} dirty={report.provenance.git_dirty}")
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + ["  …"]
    return "\n".join(lines) + "\n"


def write_report(
    report: SuiteReport,
    out_dir: Path | None = None,
) -> dict[str, Path]:
    """Write report.json / report.md / report.html / summary.txt under *out_dir*.

    Returns:
        Mapping of artifact name → path.
    """
    base = out_dir or (_RESULTS_ROOT / report.run_id)
    base.mkdir(parents=True, exist_ok=True)

    json_path = base / "report.json"
    # Stable key order for determinism (R11.5) — only generated_at is expected to differ.
    payload = report.model_dump(mode="json")
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    md_path = base / "report.md"
    md_path.write_text(render_markdown(report), encoding="utf-8")

    html_path = base / "report.html"
    html_path.write_text(render_html(report), encoding="utf-8")

    summary_path = base / "summary.txt"
    summary_text = render_summary(report)
    assert summary_text.count("\n") <= 20
    summary_path.write_text(summary_text, encoding="utf-8")

    return {
        "report.json": json_path,
        "report.md": md_path,
        "report.html": html_path,
        "summary.txt": summary_path,
    }


def report_json_without_generated_at(path: Path) -> str:
    """Load report.json and return canonical JSON with ``generated_at`` removed."""
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("generated_at", None)
    return json.dumps(data, indent=2, sort_keys=True) + "\n"
