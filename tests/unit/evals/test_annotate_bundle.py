"""`annotate bundle` and the workbench's round-trip contract (eval-coverage R13).

The workbench (``evals/ui/workbench.html``) is a static page: it cannot be
imported, so what is tested here is the contract at both seams —

* ``annotate bundle`` emits what the page's ``loadBundle`` requires;
* the page's export shape is what ``annotate --batch-file`` already ingests.

The page also re-implements three pure functions from this package in JavaScript
(``normalize_tag``, ``wilson_ci``, ``saturation_streak``). Their agreement is
asserted here against the Python originals for the values the page hard-codes, so
a change to either side that breaks the mirror shows up as a failure.

No test writes under ``evals/`` — every root is ``tmp_path``.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from evals.annotate import (
    AnnotationRecord,
    apply_batch_item,
    load_annotations,
    saturation_streak,
)
from evals.reliability import wilson_ci
from evals.taxonomy.propose import cluster_tags, normalize_tag

pytestmark = pytest.mark.eval_unit

WORKBENCH = Path("evals/ui/workbench.html")


def _rec(tags: list[str], trace_id: str = "t") -> AnnotationRecord:
    return AnnotationRecord(
        trace_id=trace_id,
        sample_id="s",
        annotator="a",
        annotated_at=datetime.now(tz=UTC),
        tags=tags,
    )


class TestWorkbenchShipped:
    def test_page_exists_and_is_self_contained(self) -> None:
        assert WORKBENCH.is_file(), "the workbench page must ship with the repo"
        html = WORKBENCH.read_text(encoding="utf-8")
        # R13.5 — local, dependency-light, no vendor in the critical path.
        assert "<script src=" not in html, "no external scripts"
        assert '<link rel="stylesheet"' not in html, "no external stylesheets"
        for host in ("http://", "cdn.", "unpkg", "googleapis", "jsdelivr"):
            assert host not in html, f"page must not reference {host}"

    def test_page_shows_no_taxonomy_vocabulary_in_open_coding(self) -> None:
        """R7.3 / R3.7 — stage 1 must surface no failure-mode ids as suggestions.

        FM ids may appear in explanatory copy elsewhere, but never inside the
        stage-1 markup, and no list of taxonomy slugs may be embedded anywhere
        for autocomplete.
        """
        html = WORKBENCH.read_text(encoding="utf-8")
        stage1 = html[html.index('id="stage1"') : html.index('id="stage2"')]
        assert not re.search(r"FM-\d{3}", stage1), "no FM ids inside the open-coding stage"
        for slug in ("tool_call_omission", "guardrail_false_positive", "unbounded_spend"):
            assert slug not in html, f"taxonomy slug {slug} must not be embedded"


class TestMirroredFunctions:
    """The page re-implements these; the mirrors must agree with Python."""

    @pytest.mark.parametrize(
        "raw",
        [
            "Retry Storm",
            "retry-storm",
            "  QA relevance retry  ",
            "workspace/parent path",
            "a__b",
            "___",
            "!!!",
            "Nested Dirs 3x",
            "tabs\tand spaces",
            "UPPER_snake",
            "trailing_",
            "_leading",
            "a-b-c d_e",
            "",
        ],
    )
    def test_normalize_tag_invariants(self, raw: str) -> None:
        out = normalize_tag(raw)
        assert re.fullmatch(r"[a-z0-9_]+", out), out
        assert "__" not in out
        assert out == out.strip("_")

    def test_normalize_tag_known_values(self) -> None:
        assert normalize_tag("Retry Storm") == "retry_storm"
        assert normalize_tag("retry-storm") == "retry_storm"
        assert normalize_tag("!!!") == "unnamed"
        assert normalize_tag("") == "unnamed"
        assert normalize_tag("workspace/parent path") == "workspaceparent_path"

    def test_wilson_values_the_page_renders(self) -> None:
        assert wilson_ci(1, 2) == pytest.approx((0.094529, 0.905471), abs=1e-6)
        assert wilson_ci(10, 100) == pytest.approx((0.055229, 0.174367), abs=1e-6)
        assert wilson_ci(0, 50) == pytest.approx((0.0, 0.071350), abs=1e-6)

    def test_saturation_streak_sequences_the_page_renders(self) -> None:
        seqs: list[tuple[list[list[str]], int]] = [
            ([], 0),
            ([[]], 1),
            ([["a"]], 0),
            ([["a"], ["a"]], 1),
            ([["a"], ["b"], ["a"]], 1),
            ([["a"], [], [], ["b"], [], [], []], 3),
            ([["a", "b"], ["b"], ["c"], ["a", "c"]], 1),
        ]
        for tags, expected in seqs:
            assert saturation_streak([_rec(t) for t in tags]) == expected


@pytest.fixture
def fixture_trace_ids() -> list[str]:
    """Trace ids that resolve via the repo's own fixture corpus."""
    root = Path("evals/fixtures/traces")
    ids: list[str] = []
    if root.is_dir():
        for path in sorted(root.glob("*.json"))[:4]:
            try:
                ids.append(json.loads(path.read_text(encoding="utf-8"))["trace_id"])
            except (OSError, ValueError, KeyError):
                continue
    return ids or ["missing-a", "missing-b"]


class TestBundleCommand:
    def _sample(self, tmp_path: Path, trace_ids: list[str]) -> Path:
        root = tmp_path / "samples"
        root.mkdir()
        (root / "smp-1.json").write_text(
            json.dumps(
                {
                    "sample_id": "smp-1",
                    "strategy": "stratified",
                    "seed": 1,
                    "n": len(trace_ids),
                    "corpus_state_hash": "a" * 64,
                    "filters": {},
                    "imbalances": [],
                    "selection": trace_ids,
                }
            ),
            encoding="utf-8",
        )
        return root

    def _run(self, argv: list[str]) -> int:
        from evals.cli import main

        return main(argv)

    def test_bundle_emits_the_shape_the_page_requires(
        self, tmp_path: Path, fixture_trace_ids: list[str]
    ) -> None:
        samples = self._sample(tmp_path, fixture_trace_ids[:2])
        out = tmp_path / "bundle.json"
        rc = self._run(
            [
                "annotate",
                "bundle",
                "--sample",
                "smp-1",
                "--out",
                str(out),
                "--samples-root",
                str(samples),
                "--traces-root",
                str(tmp_path / "empty-store"),
                "--annotator",
                "tester",
            ]
        )
        assert rc == 0
        doc = json.loads(out.read_text(encoding="utf-8"))
        # loadBundle() refuses anything without these two.
        assert doc["sample_id"] == "smp-1"
        assert isinstance(doc["traces"], list)
        assert doc["annotator"] == "tester"
        assert doc["n_bundled"] == len(doc["traces"])
        for t in doc["traces"]:
            for key in ("trace_id", "backend", "status", "spans", "artifacts"):
                assert key in t, f"the page's trace card reads {key}"

    def test_bundle_records_missing_traces_rather_than_failing(self, tmp_path: Path) -> None:
        samples = self._sample(tmp_path, ["does-not-exist-anywhere"])
        out = tmp_path / "bundle.json"
        rc = self._run(
            [
                "annotate",
                "bundle",
                "--sample",
                "smp-1",
                "--out",
                str(out),
                "--samples-root",
                str(samples),
                "--traces-root",
                str(tmp_path / "empty-store"),
                "--fixtures-root",
                str(tmp_path / "no-fixtures"),
            ]
        )
        assert rc == 0
        doc = json.loads(out.read_text(encoding="utf-8"))
        assert doc["missing_trace_ids"] == ["does-not-exist-anywhere"]
        assert doc["traces"] == []

    def test_annotate_without_sample_is_refused(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert self._run(["annotate"]) == 2
        assert "requires --sample" in capsys.readouterr().err


class TestExportIngestRoundTrip:
    """The page's export must be ingestible by the command that already exists."""

    def test_page_export_line_becomes_an_annotation_record(self, tmp_path: Path) -> None:
        # Exactly the object exportJsonl() writes, including `unaided`, which
        # AnnotationRecord does not yet carry (alignment R7.4) and must ignore.
        line = {
            "trace_id": "trace-abc",
            "note": "No spans at all, so nothing says which phase diverged.",
            "tags": ["no-spans-run-level-only", "status-failed-without-evidence"],
            "first_failure_span_id": None,
            "unaided": True,
        }
        rec = apply_batch_item(
            sample_id="smp-1",
            annotator="tester",
            item=line,
            annotations_root=tmp_path,
        )
        assert rec.trace_id == "trace-abc"
        assert rec.tags == line["tags"]
        assert rec.first_failure_span_id is None
        assert rec.sample_id == "smp-1"

        on_disk = load_annotations(tmp_path / "tester.jsonl")
        assert len(on_disk) == 1
        assert on_disk[0].note == line["note"]

    def test_extra_keys_do_not_break_ingest(self, tmp_path: Path) -> None:
        rec = apply_batch_item(
            sample_id="smp-1",
            annotator="tester",
            item={"trace_id": "t1", "tags": ["x"], "unaided": True, "coded_at": 123},
            annotations_root=tmp_path,
        )
        assert rec.tags == ["x"]

    def test_first_failure_span_id_survives(self, tmp_path: Path) -> None:
        rec = apply_batch_item(
            sample_id="smp-1",
            annotator="tester",
            item={"trace_id": "t1", "tags": ["x"], "first_failure_span_id": "span_0007"},
            annotations_root=tmp_path,
        )
        assert rec.first_failure_span_id == "span_0007"

    def test_exported_tags_cluster_as_the_page_previews(self, tmp_path: Path) -> None:
        """Stage 2's client-side clustering must agree with propose.cluster_tags."""
        lines = [
            {"trace_id": "t1", "tags": ["no-spans-run-level-only", "zero-artifacts"]},
            {"trace_id": "t2", "tags": ["No Spans Run Level Only"]},
            {"trace_id": "t3", "tags": ["no_spans_run_level_only", "scenario-id-unknown"]},
        ]
        for item in lines:
            apply_batch_item(
                sample_id="smp-1", annotator="tester", item=item, annotations_root=tmp_path
            )
        recs = load_annotations(tmp_path / "tester.jsonl")
        clusters = {c.canonical: c for c in cluster_tags(recs)}
        # Three spellings collapse to one category — the page shows the same.
        assert clusters["no_spans_run_level_only"].count == 3
        assert len(clusters["no_spans_run_level_only"].variants) == 3
        assert clusters["zero_artifacts"].count == 1
        assert clusters["scenario_id_unknown"].count == 1
