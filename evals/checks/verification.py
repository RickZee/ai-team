"""Runtime verification and gate-env checks: FM-006, FM-010."""

from __future__ import annotations

from evals.checks._helpers import (
    module_not_found_names,
    normalize_pkg,
    parse_requirements_packages,
)
from evals.checks.base import CheckResult, failed, na, passed
from evals.checks.registry import check
from evals.trace.models import Trace


@check(id="CHK-runtime-smoke-present", failure_mode_id="FM-006", tier="A")
def runtime_smoke_present(trace: Trace) -> CheckResult:
    """Fail when a complete run lacks a passing smoke_probe span."""
    cid = "CHK-runtime-smoke-present"
    fm = "FM-006"

    if trace.status != "complete":
        return na(
            cid,
            trace,
            f"status={trace.status}; smoke gate only required on complete runs",
            failure_mode_id=fm,
        )

    probes = trace.spans_of("smoke_probe")
    if not probes:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_text="complete run has no smoke_probe span",
        )

    # Prefer overview spans (have ran/success); fall back to any probe
    overview = [s for s in probes if "success" in s.payload or "ran" in s.payload]
    candidates = overview or probes
    failing = []
    for s in candidates:
        success = s.payload.get("success")
        ran = s.payload.get("ran")
        ok = s.payload.get("ok")
        if success is False or ok is False or (ran is False and success is not True):
            failing.append(s.span_id)
        elif success is None and ok is None and ran is None:
            # Ambiguous probe row without outcome — ignore for overview logic
            continue

    if failing:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_span_ids=failing,
            evidence_text="smoke_probe reported failure",
        )

    # If we have probes but none carried success=True explicitly, still fail
    # when every overview says success is missing/falsey on complete.
    any_success = any(s.payload.get("success") is True for s in candidates)
    if not any_success and any("success" in s.payload for s in candidates):
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_span_ids=[s.span_id for s in candidates],
            evidence_text="smoke_probe present but success is not true",
        )

    if not any_success and not any("success" in s.payload for s in candidates):
        return na(cid, trace, "smoke_probe spans lack success field", failure_mode_id=fm)

    return passed(cid, trace, failure_mode_id=fm, evidence_text="smoke_probe succeeded")


@check(id="CHK-gate-env-fidelity", failure_mode_id="FM-010", tier="A")
def gate_env_fidelity(trace: Trace) -> CheckResult:
    """Fail when ModuleNotFoundError names a package listed in requirements.txt."""
    cid = "CHK-gate-env-fidelity"
    fm = "FM-010"

    req_art = next((a for a in trace.artifacts if a.path.endswith("requirements.txt")), None)
    req_text = None
    if req_art is not None:
        req_text = trace.read_artifact(req_art.path)
    if req_text is None:
        # Allow inline fixture content
        inline = trace.raw_result.get("requirements_txt")
        if isinstance(inline, str):
            req_text = inline

    if not req_text:
        return na(cid, trace, "no requirements.txt artifact", failure_mode_id=fm)

    required = parse_requirements_packages(req_text)
    if not required:
        return na(cid, trace, "requirements.txt has no packages", failure_mode_id=fm)

    # Scan error / tool_result / phase payloads for ModuleNotFoundError
    hits: list[tuple[str, str]] = []
    for s in trace.spans:
        blob = " ".join(
            str(s.payload.get(k) or "")
            for k in ("message", "output", "stderr", "stdout", "error", "detail")
        )
        for mod in module_not_found_names(blob):
            hits.append((s.span_id, mod))

    if not hits:
        return na(
            cid,
            trace,
            "no ModuleNotFoundError in span payloads",
            failure_mode_id=fm,
        )

    mismatches: list[dict[str, str]] = []
    for span_id, mod in hits:
        norm = normalize_pkg(mod)
        if norm in required or mod.lower() in required:
            mismatches.append({"span_id": span_id, "module": mod})

    if mismatches:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_span_ids=[m["span_id"] for m in mismatches],
            evidence_text="ModuleNotFoundError for package listed in requirements.txt",
            detail={"mismatches": mismatches, "required": sorted(required)},
        )
    return passed(
        cid,
        trace,
        failure_mode_id=fm,
        evidence_text="ModuleNotFoundError modules not listed in requirements.txt",
        detail={"hits": [{"span_id": s, "module": m} for s, m in hits]},
    )
