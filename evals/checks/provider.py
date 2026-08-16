"""Provider error-rate check: FM-009."""

from __future__ import annotations

from evals.checks._helpers import scenario_config
from evals.checks.base import CheckResult, failed, na, passed
from evals.checks.registry import check
from evals.trace.models import Trace


def _is_provider_4xx(span_payload: dict) -> bool:
    status = span_payload.get("status_code") or span_payload.get("http_status")
    if status is not None:
        try:
            code = int(status)
            return 400 <= code < 500
        except (TypeError, ValueError):
            pass
    msg = str(span_payload.get("message") or span_payload.get("error") or "")
    lower = msg.lower()
    if "http 4" in lower or "status 4" in lower:
        return True
    if ("400" in msg or "401" in msg or "403" in msg or "404" in msg) and (
        "provider" in lower or "openrouter" in lower or "anthropic" in lower
    ):
        return True
    return bool(span_payload.get("provider_error"))


@check(id="CHK-provider-error-rate", failure_mode_id="FM-009", tier="A")
def provider_error_rate(trace: Trace) -> CheckResult:
    """Fail when HTTP 4xx provider errors exceed ``max_provider_errors`` (default 0)."""
    cid = "CHK-provider-error-rate"
    fm = "FM-009"

    cfg = scenario_config(trace)
    max_errors = int(cfg.get("max_provider_errors", 0))

    candidates = [
        *trace.spans_of("error"),
        *trace.spans_of("llm_call"),
        *trace.spans_of("retry"),
    ]
    provider_errs = [s for s in candidates if _is_provider_4xx(s.payload)]

    # Also accept explicit count from raw_result for synthetic fixtures
    explicit = trace.raw_result.get("provider_4xx_count")
    if explicit is not None:
        try:
            count = int(explicit)
            if count > max_errors:
                return failed(
                    cid,
                    trace,
                    failure_mode_id=fm,
                    evidence_text=f"provider_4xx_count={count} > max={max_errors}",
                    detail={"provider_4xx_count": count, "max_provider_errors": max_errors},
                )
            return passed(
                cid,
                trace,
                failure_mode_id=fm,
                evidence_text=f"provider_4xx_count={count} ≤ {max_errors}",
            )
        except (TypeError, ValueError):
            pass

    if not provider_errs and not candidates:
        return na(cid, trace, "no error/llm_call/retry spans to score", failure_mode_id=fm)

    if len(provider_errs) > max_errors:
        return failed(
            cid,
            trace,
            failure_mode_id=fm,
            evidence_span_ids=[s.span_id for s in provider_errs],
            evidence_text=f"{len(provider_errs)} provider 4xx errors > max={max_errors}",
            detail={
                "provider_4xx_count": len(provider_errs),
                "max_provider_errors": max_errors,
            },
        )
    return passed(
        cid,
        trace,
        failure_mode_id=fm,
        evidence_text=f"{len(provider_errs)} provider 4xx ≤ {max_errors}",
        detail={"provider_4xx_count": len(provider_errs)},
    )
