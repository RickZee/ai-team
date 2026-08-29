"""Map guardrail catalog onto ``risk_class`` (R13). Spend ceiling stays global."""

from __future__ import annotations

from typing import Any

from ai_team.tools.kinds import RiskClass

# Named checks. ``*`` means the full existing chain.
GUARDRAIL_BY_RISK: dict[RiskClass, frozenset[str]] = {
    "low": frozenset({"path_traversal", "secrets"}),
    "write": frozenset({"path_traversal", "secrets", "scope", "code_quality"}),
    "irreversible": frozenset({"*"}),
    "customer-visible": frozenset({"*"}),
}


def checks_for_risk(risk_class: RiskClass | str) -> frozenset[str]:
    """Return the check names that should run for *risk_class*."""
    key: RiskClass = risk_class if risk_class in GUARDRAIL_BY_RISK else "write"  # type: ignore[assignment]
    return GUARDRAIL_BY_RISK[key]


def should_run(check_name: str, risk_class: RiskClass | str) -> bool:
    """True if *check_name* is in the risk-class subset (or full chain)."""
    names = checks_for_risk(risk_class)
    if "*" in names:
        return True
    return check_name in names


def build_guardrail_evidence(
    *,
    policy_version: str = "1",
    events: list[Any] | None = None,
    overrides: list[str] | None = None,
    permission_set: list[str] | None = None,
) -> dict[str, Any]:
    """Build a serializable evidence bundle from monitor events.

    Overrides MUST be listed; silent skip is a harness bug (R14.3).
    """
    from ai_team.harness.receipt import GuardrailEvidence

    checks: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for evt in events or []:
        payload = {
            "name": getattr(evt, "name", None)
            or (evt.get("name") if isinstance(evt, dict) else ""),
            "status": getattr(evt, "status", None)
            or (evt.get("status") if isinstance(evt, dict) else ""),
            "message": getattr(evt, "message", None)
            or (evt.get("message") if isinstance(evt, dict) else ""),
            "category": getattr(evt, "category", None)
            or (evt.get("category") if isinstance(evt, dict) else ""),
        }
        checks.append(payload)
        outcomes.append({"name": payload["name"], "status": payload["status"]})
    bundle = GuardrailEvidence(
        policy_version=policy_version,
        checks=checks,
        overrides=list(overrides or []),
        outcomes=outcomes,
        tool_permission_set=list(permission_set or []),
    )
    return bundle.model_dump(mode="json")
