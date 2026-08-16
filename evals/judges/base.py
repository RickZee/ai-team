"""Binary, versioned LLM judges (R7).

Transport reuses ``LLMJudge._check_once_anthropic`` /
``LLMJudge._check_once_openrouter`` plumbing via ``LLMJudge._raw_complete``.
Parsing and the error contract differ: three failures → ``verdict: error``, never
coerced to ``fail`` (R7.9).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, field_validator

from evals.golden import LabelingUnit
from evals.judges.evidence import EVIDENCE
from evals.judges.exceptions import TierAMissingVerdict
from evals.trace.models import Trace

# LLMJudge is imported lazily inside BinaryJudge to avoid
# fixtures ↔ judges circular imports at module load time.

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
CACHE_DIR = Path(__file__).resolve().parent / "cache"

VerdictLabel = Literal["pass", "fail", "error"]
ProviderName = Literal["anthropic", "openrouter"]


class JudgeSpec(BaseModel):
    """Parsed judge prompt front matter plus content hash (R7.2)."""

    judge_id: str
    version: int
    failure_mode_id: str | None = None
    question: str
    pass_means: str
    fail_means: str
    model: str
    provider: ProviderName
    evidence_builder: str
    prompt_hash: str
    body: str = Field(default="", description="Markdown body after front matter.")
    path: str | None = None

    @field_validator("question")
    @classmethod
    def _single_question(cls, value: str) -> str:
        # Reject rubrics that smuggle a second decision (R7.1).
        if value.count("?") > 1:
            msg = "judge question must be a single binary decision (R7.1)"
            raise ValueError(msg)
        return value


class Verdict(BaseModel):
    """Binary judge outcome with grounding metadata (R7.4)."""

    judge_id: str
    prompt_hash: str
    model_id: str
    provider: str
    trace_id: str
    labeling_unit_id: str
    verdict: VerdictLabel
    reason: str
    evidence_quote: str
    evidence_sha256: str
    single_vendor: bool
    ensemble: dict[str, Any] | None = None
    cached: bool = False
    latency_ms: int | None = None


class VerdictCache:
    """Git-trackable verdict cache under ``evals/judges/cache/<key[:2]>/<key>.json``."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or CACHE_DIR

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> Verdict | None:
        path = self._path(key)
        if not path.is_file():
            return None
        return Verdict.model_validate_json(path.read_text(encoding="utf-8"))

    def put(self, key: str, verdict: Verdict) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(verdict.model_dump_json(indent=2) + "\n", encoding="utf-8")


def cache_key(prompt_hash: str, model_id: str, evidence: str) -> str:
    """sha256(prompt_hash + model_id + evidence) per R7.7."""
    blob = f"{prompt_hash}{model_id}{evidence}".encode()
    return hashlib.sha256(blob).hexdigest()


def _parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        msg = "prompt file must start with YAML front matter"
        raise ValueError(msg)
    parts = text.split("---", 2)
    if len(parts) < 3:
        msg = "prompt file front matter not terminated"
        raise ValueError(msg)
    import yaml

    meta = yaml.safe_load(parts[1]) or {}
    if not isinstance(meta, dict):
        msg = "front matter must be a mapping"
        raise ValueError(msg)
    return meta, parts[2].lstrip("\n")


def load_judge_spec(path: Path) -> JudgeSpec:
    """Load and validate a prompt file; enforce version ↔ filename (R7.3)."""
    raw = path.read_bytes()
    prompt_hash = hashlib.sha256(raw).hexdigest()
    meta, body = _parse_front_matter(raw.decode("utf-8"))
    version = int(meta["version"])
    judge_id = str(meta["judge_id"])
    expected_name = f"{judge_id}.v{version}.md"
    if path.name != expected_name:
        msg = (
            f"prompt filename {path.name!r} does not match " f"judge_id/version ({expected_name!r})"
        )
        raise ValueError(msg)
    return JudgeSpec(
        judge_id=judge_id,
        version=version,
        failure_mode_id=meta.get("failure_mode_id"),
        question=str(meta["question"]),
        pass_means=str(meta["pass_means"]),
        fail_means=str(meta["fail_means"]),
        model=str(meta["model"]),
        provider=meta["provider"],
        evidence_builder=str(meta["evidence_builder"]),
        prompt_hash=prompt_hash,
        body=body,
        path=str(path),
    )


def validate_prompts(prompts_dir: Path | None = None) -> list[JudgeSpec]:
    """Parse every prompt file; raise on version/filename mismatch."""
    root = prompts_dir or PROMPTS_DIR
    specs: list[JudgeSpec] = []
    for path in sorted(root.glob("*.md")):
        specs.append(load_judge_spec(path))
    return specs


def assert_prompt_version_tracks_body(path: Path, *, altered_body: str) -> None:
    """Fail when body changes without a version bump (R7.3 validation helper).

    Writes a temporary sibling with the same version/filename stem semantics
    would break — callers mutate body in place and expect ``load_judge_spec``
    to succeed only when the version field and filename stay consistent; the
    body-hash change is detected by comparing ``prompt_hash`` to the original.
    """
    original = load_judge_spec(path)
    raw = path.read_text(encoding="utf-8")
    meta, _body = _parse_front_matter(raw)
    rebuilt = "---\n" + _dump_front_matter(meta) + "---\n\n" + altered_body
    new_hash = hashlib.sha256(rebuilt.encode()).hexdigest()
    if new_hash != original.prompt_hash and int(meta["version"]) == original.version:
        msg = (
            f"prompt body changed for {original.judge_id} but version "
            f"remained {original.version}; bump version (R7.3)"
        )
        raise ValueError(msg)


def _dump_front_matter(meta: dict[str, Any]) -> str:
    import yaml

    return yaml.safe_dump(meta, sort_keys=False)


def _render_user_prompt(spec: JudgeSpec, evidence: str) -> str:
    text = spec.body.replace("{evidence}", evidence).replace("{question}", spec.question)
    return text


def _parse_binary_json(raw_text: str) -> dict[str, Any]:
    if not raw_text.strip():
        raise ValueError("empty judge response")
    text = raw_text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
        text = text.rstrip("`").strip()
    data = json.loads(text)
    if "score" in data:
        raise ValueError("numeric score field is not accepted (R7.4)")
    verdict = data.get("verdict")
    if verdict not in {"pass", "fail"}:
        raise ValueError(f"invalid verdict {verdict!r}")
    return {
        "verdict": verdict,
        "reason": str(data.get("reason", "")),
        "evidence_quote": str(data.get("evidence_quote", "")),
    }


class BinaryJudge:
    """One binary question, versioned prompt, cached verdicts."""

    MAX_ATTEMPTS = 3

    def __init__(
        self,
        spec: JudgeSpec,
        *,
        cache: VerdictCache | None = None,
        allow_network: bool = False,
        backend_vendor: str | None = None,
    ) -> None:
        self.spec = spec
        self.cache = cache or VerdictCache()
        self.allow_network = allow_network
        self.backend_vendor = backend_vendor
        from evals.fixtures import LLMJudge

        self._llm = LLMJudge(model=spec.model, provider=spec.provider)

    def judge(self, unit: LabelingUnit, trace: Trace) -> Verdict:
        """Score one labeling unit; cache hit skips the network."""
        builder = EVIDENCE.get(self.spec.evidence_builder)
        if builder is None:
            msg = f"unknown evidence_builder {self.spec.evidence_builder!r}"
            raise KeyError(msg)
        evidence = builder(trace, unit)
        evidence_sha = hashlib.sha256(evidence.encode()).hexdigest()
        key = cache_key(self.spec.prompt_hash, self.spec.model, evidence)
        hit = self.cache.get(key)
        if hit is not None:
            return hit.model_copy(update={"cached": True})

        if not self.allow_network:
            raise TierAMissingVerdict(key, judge_id=self.spec.judge_id)

        single_vendor = bool(
            self.backend_vendor
            and self.backend_vendor.lower() in {self.spec.provider.lower(), "anthropic"}
            and self.spec.provider == "anthropic"
            and self.backend_vendor in {"claude-agent-sdk", "anthropic"}
        )
        # Prefer explicit vendor match: backend name shares provider family.
        if self.backend_vendor == "claude-agent-sdk" and self.spec.provider == "anthropic":
            single_vendor = True

        user_prompt = _render_user_prompt(self.spec, evidence)
        last_err: Exception | None = None
        t0 = time.perf_counter()
        for _attempt in range(self.MAX_ATTEMPTS):
            try:
                raw = self._llm._raw_complete(user_prompt)  # noqa: SLF001 — transport reuse
                parsed = _parse_binary_json(raw)
                quote = parsed["evidence_quote"]
                if quote and quote not in evidence:
                    return self._error_verdict(
                        unit,
                        trace,
                        evidence_sha,
                        reason="ungrounded",
                        evidence_quote=quote,
                        single_vendor=single_vendor,
                        latency_ms=int((time.perf_counter() - t0) * 1000),
                        key=key,
                    )
                if not quote:
                    return self._error_verdict(
                        unit,
                        trace,
                        evidence_sha,
                        reason="ungrounded",
                        evidence_quote="",
                        single_vendor=single_vendor,
                        latency_ms=int((time.perf_counter() - t0) * 1000),
                        key=key,
                    )
                verdict = Verdict(
                    judge_id=self.spec.judge_id,
                    prompt_hash=self.spec.prompt_hash,
                    model_id=self.spec.model,
                    provider=self.spec.provider,
                    trace_id=trace.trace_id,
                    labeling_unit_id=unit.labeling_unit_id,
                    verdict=parsed["verdict"],
                    reason=parsed["reason"],
                    evidence_quote=quote,
                    evidence_sha256=evidence_sha,
                    single_vendor=single_vendor,
                    cached=False,
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                )
                self.cache.put(key, verdict)
                return verdict
            except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError) as exc:
                last_err = exc
            except httpx.HTTPError as exc:
                last_err = exc
            except Exception as exc:  # noqa: BLE001 — anthropic SDK error types vary
                last_err = exc

        return self._error_verdict(
            unit,
            trace,
            evidence_sha,
            reason=f"judge error after {self.MAX_ATTEMPTS} attempts: {last_err}",
            evidence_quote="",
            single_vendor=single_vendor,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            key=key,
        )

    def _error_verdict(
        self,
        unit: LabelingUnit,
        trace: Trace,
        evidence_sha: str,
        *,
        reason: str,
        evidence_quote: str,
        single_vendor: bool,
        latency_ms: int,
        key: str,
    ) -> Verdict:
        """Record ``verdict: error`` — never coerce to fail (R7.9)."""
        verdict = Verdict(
            judge_id=self.spec.judge_id,
            prompt_hash=self.spec.prompt_hash,
            model_id=self.spec.model,
            provider=self.spec.provider,
            trace_id=trace.trace_id,
            labeling_unit_id=unit.labeling_unit_id,
            verdict="error",
            reason=reason,
            evidence_quote=evidence_quote,
            evidence_sha256=evidence_sha,
            single_vendor=single_vendor,
            cached=False,
            latency_ms=latency_ms,
        )
        self.cache.put(key, verdict)
        return verdict


class EnsembleBinaryJudge:
    """Majority-vote ensemble across providers (R7.5 / R7.6 reporting)."""

    def __init__(self, judges: list[BinaryJudge]) -> None:
        if not judges:
            msg = "EnsembleBinaryJudge requires at least one BinaryJudge"
            raise ValueError(msg)
        self.judges = judges

    @property
    def is_single_vendor(self) -> bool:
        return len({j.spec.provider for j in self.judges}) < 2

    def judge(self, unit: LabelingUnit, trace: Trace) -> Verdict:
        verdicts = [j.judge(unit, trace) for j in self.judges]
        usable = [v for v in verdicts if v.verdict in {"pass", "fail"}]
        if not usable:
            base = verdicts[0]
            return base.model_copy(
                update={
                    "verdict": "error",
                    "reason": "all ensemble members errored",
                    "ensemble": {
                        "spread": 1.0,
                        "contested": True,
                        "single_vendor": self.is_single_vendor,
                        "members": [v.model_dump() for v in verdicts],
                    },
                }
            )
        fail_votes = sum(1 for v in usable if v.verdict == "fail")
        pass_votes = len(usable) - fail_votes
        majority: VerdictLabel = "fail" if fail_votes > pass_votes else "pass"
        labels = {v.verdict for v in usable}
        contested = len(labels) > 1
        spread = (len(labels) - 1) / max(len(usable), 1)
        primary = usable[0]
        return primary.model_copy(
            update={
                "verdict": majority,
                "single_vendor": self.is_single_vendor,
                "ensemble": {
                    "spread": spread,
                    "contested": contested,
                    "single_vendor": self.is_single_vendor,
                    "members": [
                        {"judge_id": v.judge_id, "verdict": v.verdict, "provider": v.provider}
                        for v in verdicts
                    ],
                },
            }
        )


def load_tier_a_judges() -> list[Any]:
    """Load BinaryJudge adapters for Tier A (cache-only scoring).

    Returns an empty list when no prompt files are present. Each adapter
    exposes ``judge_trace(trace, allow_network=...)`` expected by ``tier_a``.
    """
    from evals.aggregate import JudgeAlignmentSummary, JudgeVerdictRecord
    from evals.alignment import ADVISORY_NO_LIVE_REASON, ALIGNMENT_DIR
    from evals.golden import LabelingUnit

    specs = validate_prompts()
    adapters: list[Any] = []

    class _TierAJudgeAdapter:
        def __init__(self, spec: JudgeSpec) -> None:
            self.spec = spec
            self.id = spec.judge_id
            self._judge = BinaryJudge(spec, allow_network=False)
            self.alignment_summary: JudgeAlignmentSummary | None = None
            align_path = ALIGNMENT_DIR / f"{spec.judge_id}.json"
            if align_path.is_file():
                import json

                raw = json.loads(align_path.read_text(encoding="utf-8"))
                self.alignment_summary = JudgeAlignmentSummary(
                    judge_id=spec.judge_id,
                    eligible_to_gate=bool(raw.get("eligible_to_gate", False)),
                    tpr=raw.get("tpr"),
                    tnr=raw.get("tnr"),
                    kappa=raw.get("kappa"),
                    suppressed=not bool(raw.get("eligible_to_gate", False)),
                    suppression_reason=(
                        None
                        if raw.get("eligible_to_gate")
                        else "; ".join(
                            raw.get("ineligibility_reasons") or [ADVISORY_NO_LIVE_REASON]
                        )
                    ),
                )

        def judge_trace(self, trace: Trace, *, allow_network: bool = False) -> JudgeVerdictRecord:
            self._judge.allow_network = allow_network
            unit = LabelingUnit(
                labeling_unit_id=f"{trace.trace_id}|run|{self.spec.failure_mode_id or 'FM'}",
                trace_id=trace.trace_id,
                span_id="run",
                failure_mode_id=self.spec.failure_mode_id or "FM-001",
            )
            verd = self._judge.judge(unit, trace)
            eligible = bool(self.alignment_summary and self.alignment_summary.eligible_to_gate)
            return JudgeVerdictRecord(
                judge_id=self.spec.judge_id,
                trace_id=trace.trace_id,
                verdict=verd.verdict,
                single_vendor=verd.single_vendor,
                vendor=self.spec.provider,
                eligible_to_gate=eligible,
                cached=verd.cached,
            )

    for spec in specs:
        adapters.append(_TierAJudgeAdapter(spec))
    return adapters
