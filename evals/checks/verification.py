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

    if _scenario_has_ui(trace):
        ui_ok = any(
            s.payload.get("kind") == "ui" and s.payload.get("success") is True for s in probes
        )
        if not ui_ok:
            return failed(
                cid,
                trace,
                failure_mode_id=fm,
                evidence_text="UI scenario requires a passing ui_smoke result; HTTP-only probe is not enough",
            )

    return passed(cid, trace, failure_mode_id=fm, evidence_text="smoke_probe succeeded")


def _scenario_has_ui(trace: Trace) -> bool:
    raw = trace.raw_result or {}
    if raw.get("ui"):
        return True
    scenario = raw.get("scenario")
    if isinstance(scenario, dict) and scenario.get("ui"):
        return True
    for art in trace.artifacts:
        if art.path.endswith("ui_smoke_results.json") or art.path.endswith("scenario.json"):
            body = trace.read_artifact(art.path)
            if body and '"ui"' in body and "base_url" in body:
                return True
    return False


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


_INDEPENDENT = frozenset({"smoke", "ui_smoke", "test"})


def _identity_key(identity: dict[str, object] | None) -> tuple[str, str] | None:
    if not isinstance(identity, dict):
        return None
    role = str(identity.get("agent_role") or "")
    sub = str(identity.get("subagent_id") or "")
    if not role:
        return None
    return (role, sub)


@check(id="CHK-verifier-independence", failure_mode_id="FM-016", tier="A")
def verifier_independence(trace: Trace) -> CheckResult:
    """Fail when the writer of an item is also the thing that passed it."""
    cid = "CHK-verifier-independence"
    fm = "FM-016"
    transitions = trace.raw_result.get("acceptance_passes")
    if not isinstance(transitions, list) or not transitions:
        return na(cid, trace, "no passes transitions", failure_mode_id=fm)

    offenders: list[str] = []
    for row in transitions:
        if not isinstance(row, dict):
            continue
        verified_by = str(row.get("verified_by") or "")
        if verified_by in _INDEPENDENT:
            continue
        writer = _identity_key(
            row.get("writer_identity") if isinstance(row.get("writer_identity"), dict) else None
        )
        verifier = _identity_key(
            row.get("verifier_identity") if isinstance(row.get("verifier_identity"), dict) else None
        )
        if writer and verifier and writer == verifier:
            offenders.append(str(row.get("item_id") or "?"))

    if offenders:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_text=f"self-graded items: {offenders}",
            detail={"items": offenders},
        )
    return passed(
        cid, trace, failure_mode_id=fm, evidence_text="verifier independent or deterministic"
    )


def _has_remediation(
    trace: Trace, item_id: str, detected_at: str | None, verdict_at: str | None
) -> bool:
    del detected_at, verdict_at
    for s in trace.spans_of("tool_result", "tool_use"):
        refs = s.payload.get("artifact_refs") or s.payload.get("item_id")
        blob = str(refs) + str(s.payload.get("path") or "")
        matched = item_id in blob or (isinstance(refs, list) and item_id in [str(x) for x in refs])
        if matched and (s.payload.get("kind") == "write" or s.type == "tool_use"):
            return True
    remediations = trace.raw_result.get("remediation_spans") or []
    if isinstance(remediations, list):
        return any(str(r.get("item_id")) == item_id for r in remediations if isinstance(r, dict))
    return False


@check(id="CHK-evaluator-capitulation", failure_mode_id="FM-017", tier="A")
def evaluator_capitulation(trace: Trace) -> CheckResult:
    """Fail when QA accepts while recording a major/blocker with no remediation."""
    cid = "CHK-evaluator-capitulation"
    fm = "FM-017"
    verdicts = trace.raw_result.get("qa_verdicts")
    if not isinstance(verdicts, list) or not verdicts:
        if not any(a.path.endswith("qa_verdicts.jsonl") for a in trace.artifacts):
            return na(cid, trace, "no qa verdicts", failure_mode_id=fm)
        verdicts = []
        text = trace.read_artifact("docs/qa_verdicts.jsonl")
        if text:
            import json

            for line in text.splitlines():
                if line.strip():
                    try:
                        verdicts.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        if not verdicts:
            return na(cid, trace, "no qa verdicts", failure_mode_id=fm)

    caps: list[str] = []
    for v in verdicts:
        if not isinstance(v, dict):
            continue
        if str(v.get("verdict") or "") != "accept":
            continue
        issues = v.get("issues") or []
        serious = [
            i
            for i in issues
            if isinstance(i, dict) and str(i.get("severity") or "") in {"major", "blocker"}
        ]
        if not serious:
            continue
        item_id = str(v.get("item_id") or "")
        if _has_remediation(trace, item_id, None, None):
            continue
        caps.append(item_id or "?")

    if caps:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_text=f"QA accepted with open major/blocker: {caps}",
            detail={"items": caps},
        )
    return passed(cid, trace, failure_mode_id=fm, evidence_text="no evaluator capitulation")


def qa_false_negative_rate(trace: Trace) -> float | None:
    """Items QA accepted that a deterministic verifier later failed (R16.4)."""
    verdicts = trace.raw_result.get("qa_verdicts")
    later = trace.raw_result.get("deterministic_failures")
    if not isinstance(verdicts, list) or not isinstance(later, list):
        return None
    accepted = {
        str(v.get("item_id"))
        for v in verdicts
        if isinstance(v, dict) and v.get("verdict") == "accept"
    }
    if not accepted:
        return None
    failed_ids = {str(x) for x in later}
    misses = accepted & failed_ids
    return len(misses) / len(accepted)
