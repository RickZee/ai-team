"""Load and validate the failure-mode taxonomy (R4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

_TAXONOMY_DIR = Path(__file__).resolve().parent
_DEFAULT_PATH = _TAXONOMY_DIR / "failure_modes.yaml"

Layer = Literal["model", "framework", "harness", "provider"]
HarnessLayer = Literal[
    "tools",
    "verification",
    "context",
    "guardrails",
    "observability",
    "routing",
    "feedback",
]
Severity = Literal["blocker", "major", "minor"]
Detection = Literal["check", "judge", "manual"]
Status = Literal["active", "retired", "reserved"]

VALID_LAYERS = frozenset({"model", "framework", "harness", "provider"})
VALID_HARNESS_LAYERS = frozenset(
    {"tools", "verification", "context", "guardrails", "observability", "routing", "feedback"}
)
VALID_SEVERITIES = frozenset({"blocker", "major", "minor"})
VALID_DETECTIONS = frozenset({"check", "judge", "manual"})
VALID_STATUSES = frozenset({"active", "retired", "reserved"})


class ExampleRef(BaseModel):
    """A ``(trace_id, span_id)`` pair pointing at corpus evidence."""

    trace_id: str
    span_id: str


class FailureMode(BaseModel):
    """One versioned failure-mode entry from ``failure_modes.yaml``."""

    id: str
    slug: str
    title: str
    definition: str
    layer: Layer
    harness_layer: HarnessLayer | None = None
    severity: Severity
    detection: Detection
    implemented_by: list[str] = Field(default_factory=list)
    positive_examples: list[ExampleRef] = Field(default_factory=list)
    negative_examples: list[ExampleRef] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    introduced_in: str
    status: Status = "active"
    retired_reason: str | None = None


class Taxonomy(BaseModel):
    """Parsed taxonomy document."""

    version: str
    failure_modes: list[FailureMode]

    def by_id(self) -> dict[str, FailureMode]:
        """Index failure modes by ``FM-###`` id."""
        return {fm.id: fm for fm in self.failure_modes}

    def active(self) -> list[FailureMode]:
        """Return active (non-retired) failure modes."""
        return [fm for fm in self.failure_modes if fm.status == "active"]


class TaxonomyValidationError(ValueError):
    """Raised when taxonomy YAML fails structural or enum validation."""


def _require_str(entry: dict[str, Any], key: str, fm_hint: str) -> str:
    val = entry.get(key)
    if not isinstance(val, str) or not val.strip():
        raise TaxonomyValidationError(f"{fm_hint}: missing or empty field '{key}'")
    return val.strip()


def _parse_examples(raw: Any, field: str, fm_id: str) -> list[ExampleRef]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise TaxonomyValidationError(f"{fm_id}: {field} must be a list")
    out: list[ExampleRef] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise TaxonomyValidationError(f"{fm_id}: {field}[{i}] must be a mapping")
        tid = item.get("trace_id")
        sid = item.get("span_id")
        if not isinstance(tid, str) or not isinstance(sid, str):
            raise TaxonomyValidationError(
                f"{fm_id}: {field}[{i}] requires string trace_id and span_id"
            )
        out.append(ExampleRef(trace_id=tid, span_id=sid))
    return out


def _parse_failure_mode(entry: dict[str, Any]) -> FailureMode:
    fm_id = _require_str(entry, "id", "failure_mode")
    layer = _require_str(entry, "layer", fm_id)
    if layer not in VALID_LAYERS:
        raise TaxonomyValidationError(
            f"bad layer: {layer!r} for {fm_id} (expected one of {sorted(VALID_LAYERS)})"
        )
    harness_layer_raw = entry.get("harness_layer")
    harness_layer: str | None
    if harness_layer_raw is None or harness_layer_raw == "":
        harness_layer = None
    else:
        if not isinstance(harness_layer_raw, str):
            raise TaxonomyValidationError(f"bad harness_layer: {harness_layer_raw!r} for {fm_id}")
        harness_layer = harness_layer_raw.strip()
        if harness_layer not in VALID_HARNESS_LAYERS:
            raise TaxonomyValidationError(
                f"bad harness_layer: {harness_layer!r} for {fm_id} "
                f"(expected one of {sorted(VALID_HARNESS_LAYERS)})"
            )
    severity = _require_str(entry, "severity", fm_id)
    if severity not in VALID_SEVERITIES:
        raise TaxonomyValidationError(
            f"bad severity: {severity!r} for {fm_id} "
            f"(expected one of {sorted(VALID_SEVERITIES)})"
        )
    detection = _require_str(entry, "detection", fm_id)
    if detection not in VALID_DETECTIONS:
        raise TaxonomyValidationError(
            f"bad detection: {detection!r} for {fm_id} "
            f"(expected one of {sorted(VALID_DETECTIONS)})"
        )
    status = entry.get("status", "active")
    if not isinstance(status, str) or status not in VALID_STATUSES:
        raise TaxonomyValidationError(f"bad status: {status!r} for {fm_id}")

    implemented_by = entry.get("implemented_by") or []
    if not isinstance(implemented_by, list):
        raise TaxonomyValidationError(f"{fm_id}: implemented_by must be a list")
    implemented_by = [str(x) for x in implemented_by]

    if detection == "check" and not implemented_by and status != "reserved":
        raise TaxonomyValidationError(f"detection:check with empty implemented_by: {fm_id}")

    positive = _parse_examples(entry.get("positive_examples"), "positive_examples", fm_id)
    if detection == "judge" and not positive:
        raise TaxonomyValidationError(
            f"{fm_id}: detection:judge requires non-empty positive_examples"
        )

    retired_reason = entry.get("retired_reason")
    if status == "retired" and not retired_reason:
        raise TaxonomyValidationError(f"{fm_id}: retired_reason required when status=retired")

    return FailureMode(
        id=fm_id,
        slug=_require_str(entry, "slug", fm_id),
        title=_require_str(entry, "title", fm_id),
        definition=_require_str(entry, "definition", fm_id),
        layer=layer,  # type: ignore[arg-type]
        harness_layer=harness_layer,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        detection=detection,  # type: ignore[arg-type]
        implemented_by=implemented_by,
        positive_examples=positive,
        negative_examples=_parse_examples(
            entry.get("negative_examples"), "negative_examples", fm_id
        ),
        references=[str(r) for r in (entry.get("references") or [])],
        introduced_in=_require_str(entry, "introduced_in", fm_id),
        status=status,  # type: ignore[arg-type]
        retired_reason=str(retired_reason) if retired_reason else None,
    )


def default_example_trace_ids() -> set[str]:
    """Trace ids resolvable for taxonomy examples (fixtures + live corpus).

    Prefers redacted check fixtures under ``evals/fixtures/traces/``, then
    ``tests/fixtures/traces/``, then ``evals/traces/*.json``.
    """
    ids: set[str] = set()
    roots = [
        _TAXONOMY_DIR.parent / "fixtures" / "traces",
        Path("evals/fixtures/traces"),
        Path("tests/fixtures/traces"),
        Path("evals/traces"),
    ]
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.glob("*.json"):
            # Filename may be <trace_id>.json or <check>__<outcome>.json
            stem = path.stem
            if stem.endswith("__fixture") or "__" not in stem:
                ids.add(stem)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            tid = data.get("trace_id")
            if isinstance(tid, str) and tid:
                ids.add(tid)
    return ids


def load_taxonomy(
    path: Path | None = None,
    *,
    check_trace_refs: bool | None = None,
    require_examples: bool = False,
    corpus_trace_ids: set[str] | None = None,
) -> Taxonomy:
    """Parse and validate ``failure_modes.yaml``.

    Args:
        path: Taxonomy file path (defaults to package ``failure_modes.yaml``).
        check_trace_refs: When True, require every example ``trace_id`` to appear
            in *corpus_trace_ids* (or :func:`default_example_trace_ids`). When
            ``None`` (default), validation is enabled automatically if any FM
            has non-empty examples.
        require_examples: When True, every *active* FM must have ≥1 positive and
            ≥1 negative example.
        corpus_trace_ids: Known corpus ids used when trace-ref checking is on.

    Returns:
        Validated :class:`Taxonomy`.

    Raises:
        TaxonomyValidationError: On duplicate ids, bad enums, empty
            ``implemented_by`` for ``detection: check``, retired-id reuse,
            missing required examples, or dangling trace references.
    """
    tax_path = path or _DEFAULT_PATH
    try:
        raw_text = tax_path.read_text(encoding="utf-8")
    except OSError as e:
        raise TaxonomyValidationError(f"cannot read taxonomy: {tax_path}: {e}") from e

    data = yaml.safe_load(raw_text)
    if not isinstance(data, dict):
        raise TaxonomyValidationError("taxonomy root must be a mapping")

    version = data.get("version")
    if not isinstance(version, str) or not version.strip():
        raise TaxonomyValidationError("taxonomy version missing")

    raw_fms = data.get("failure_modes")
    if not isinstance(raw_fms, list) or not raw_fms:
        raise TaxonomyValidationError("failure_modes must be a non-empty list")

    modes: list[FailureMode] = []
    seen: dict[str, FailureMode] = {}
    for raw in raw_fms:
        if not isinstance(raw, dict):
            raise TaxonomyValidationError("each failure_mode must be a mapping")
        fm = _parse_failure_mode(raw)
        if fm.id in seen:
            prior = seen[fm.id]
            if prior.status == "retired" or fm.status == "retired":
                raise TaxonomyValidationError(f"retired id reused: {fm.id}")
            raise TaxonomyValidationError(f"duplicate id: {fm.id}")
        seen[fm.id] = fm
        modes.append(fm)

    if require_examples:
        for fm in modes:
            if fm.status != "active":
                continue
            if not fm.positive_examples:
                raise TaxonomyValidationError(
                    f"{fm.id}: require_examples but positive_examples is empty"
                )
            if not fm.negative_examples:
                raise TaxonomyValidationError(
                    f"{fm.id}: require_examples but negative_examples is empty"
                )

    has_examples = any(fm.positive_examples or fm.negative_examples for fm in modes)
    do_check_refs = has_examples if check_trace_refs is None else check_trace_refs
    if do_check_refs:
        known = corpus_trace_ids if corpus_trace_ids is not None else default_example_trace_ids()
        for fm in modes:
            for ex in [*fm.positive_examples, *fm.negative_examples]:
                if ex.trace_id not in known:
                    raise TaxonomyValidationError(
                        f"dangling trace reference: {ex.trace_id} (FM {fm.id})"
                    )

    return Taxonomy(version=version.strip(), failure_modes=modes)


def write_coverage_md(
    taxonomy: Taxonomy,
    *,
    check_ids_by_fm: dict[str, list[str]],
    judge_ids_by_fm: dict[str, list[str]] | None = None,
    label_counts: dict[str, int] | None = None,
    rates: dict[str, float | None] | None = None,
    out_path: Path | None = None,
) -> Path:
    """Emit ``COVERAGE.md`` listing every FM and its detection coverage (R4.6).

    Args:
        taxonomy: Loaded taxonomy.
        check_ids_by_fm: Registered check ids keyed by failure-mode id.
        judge_ids_by_fm: Optional judge ids keyed by failure-mode id.
        label_counts: Optional golden-set label counts per FM.
        rates: Optional measured failure rates per FM.
        out_path: Destination path (defaults to ``evals/taxonomy/COVERAGE.md``).

    Returns:
        Path written.
    """
    dest = out_path or (_TAXONOMY_DIR / "COVERAGE.md")
    judges = judge_ids_by_fm or {}
    labels = label_counts or {}
    measured = rates or {}

    lines = [
        "# Failure-mode coverage",
        "",
        f"Taxonomy version: `{taxonomy.version}`",
        "",
        "| ID | Slug | Layer | Harness layer | Detection | Checks | Judges | Labels | Rate | Status |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    uncovered: list[str] = []
    reserved: list[str] = []
    for fm in taxonomy.failure_modes:
        checks = check_ids_by_fm.get(fm.id, []) or list(fm.implemented_by)
        jlist = judges.get(fm.id, [])
        if fm.status == "reserved":
            reserved.append(fm.id)
        elif fm.detection == "check" and not checks:
            uncovered.append(fm.id)
        rate = measured.get(fm.id)
        rate_s = "—" if rate is None else f"{rate:.3f}"
        hl = fm.harness_layer or "—"
        lines.append(
            f"| {fm.id} | `{fm.slug}` | {fm.layer} | {hl} | {fm.detection} | "
            f"{', '.join(checks) or '—'} | {', '.join(jlist) or '—'} | "
            f"{labels.get(fm.id, 0)} | {rate_s} | {fm.status} |"
        )

    lines.extend(["", "## Uncovered (detection: check, no implementation)", ""])
    if uncovered:
        for uid in uncovered:
            lines.append(f"- {uid}")
    else:
        lines.append("_None — every check-detected FM has a named implementation._")

    lines.extend(["", "## Reserved (not yet implemented)", ""])
    if reserved:
        for rid in reserved:
            lines.append(f"- {rid} — reserved, unimplemented")
    else:
        lines.append("_None — no reserved failure modes._")

    lines.extend(
        [
            "",
            "## Example provenance",
            "",
            "Positive/negative examples currently reference **synthetic** check",
            "fixtures under `evals/fixtures/traces/` (fail/pass pairs from",
            "`tests/fixtures/traces/`). They are harness wiring evidence, **not**",
            "production open-coding labels from task 5.2 (human-only).",
            "",
            "All seeded FMs remain `active` with fixture examples. Retire an FM",
            "only with an explicit `retired_reason` when the corpus truly cannot",
            "support it — do not retire merely because live open-coding has not",
            "run yet.",
            "",
        ]
    )

    dest.write_text("\n".join(lines), encoding="utf-8")
    return dest
