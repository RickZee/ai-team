"""Taxonomy loader validation tests (task 3.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from evals.taxonomy.loader import TaxonomyValidationError, load_taxonomy

pytestmark = pytest.mark.eval_unit

_VALID = Path(__file__).resolve().parents[3] / "evals" / "taxonomy" / "failure_modes.yaml"


def _load_raw() -> dict:
    return yaml.safe_load(_VALID.read_text(encoding="utf-8"))


def _write_tax(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "failure_modes.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


class TestLoadTaxonomy:
    def test_valid_taxonomy_loads(self) -> None:
        tax = load_taxonomy(require_examples=True)
        assert tax.version == "1.2.0"
        ids = [fm.id for fm in tax.failure_modes]
        assert ids == [f"FM-{i:03d}" for i in range(1, 18)]
        active = [fm for fm in tax.failure_modes if fm.status == "active"]
        reserved = [fm for fm in tax.failure_modes if fm.status == "reserved"]
        assert reserved == []
        assert [fm.id for fm in active] == [f"FM-{i:03d}" for i in range(1, 18)]
        assert all(fm.status == "active" for fm in active)
        assert all(fm.implemented_by for fm in active)
        assert all(fm.positive_examples for fm in active)
        assert all(fm.negative_examples for fm in active)
        by_id = {fm.id: fm for fm in tax.failure_modes}
        assert by_id["FM-001"].harness_layer == "tools"
        assert by_id["FM-002"].harness_layer is None
        assert by_id["FM-009"].harness_layer is None
        assert by_id["FM-011"].harness_layer == "context"
        assert by_id["FM-012"].harness_layer == "tools"
        assert by_id["FM-013"].harness_layer == "feedback"
        assert by_id["FM-014"].harness_layer == "tools"
        assert by_id["FM-015"].harness_layer == "context"
        assert by_id["FM-016"].harness_layer == "verification"
        assert by_id["FM-017"].harness_layer == "verification"

    def test_trace_refs_resolve_against_fixtures(self) -> None:
        # Auto-enabled because examples are non-empty.
        tax = load_taxonomy()
        assert all(fm.positive_examples for fm in tax.active())

    def test_dangling_trace_ref_raises(self, tmp_path: Path) -> None:
        data = _load_raw()
        data["failure_modes"][0]["positive_examples"] = [
            {"trace_id": "does-not-exist-trace", "span_id": "run"}
        ]
        path = _write_tax(tmp_path, data)
        with pytest.raises(TaxonomyValidationError, match="dangling trace reference"):
            load_taxonomy(path, check_trace_refs=True, corpus_trace_ids=set())

    def test_require_examples_raises_when_empty(self, tmp_path: Path) -> None:
        data = _load_raw()
        data["failure_modes"][0]["positive_examples"] = []
        path = _write_tax(tmp_path, data)
        with pytest.raises(TaxonomyValidationError, match="positive_examples is empty"):
            load_taxonomy(path, require_examples=True, check_trace_refs=False)

    def test_duplicate_id_raises(self, tmp_path: Path) -> None:
        data = _load_raw()
        data["failure_modes"].append(dict(data["failure_modes"][0]))
        path = _write_tax(tmp_path, data)
        with pytest.raises(TaxonomyValidationError, match="duplicate id: FM-001"):
            load_taxonomy(path)

    def test_bad_layer_raises(self, tmp_path: Path) -> None:
        data = _load_raw()
        data["failure_modes"][0]["layer"] = "application"
        path = _write_tax(tmp_path, data)
        with pytest.raises(TaxonomyValidationError, match="bad layer"):
            load_taxonomy(path)

    def test_bad_severity_raises(self, tmp_path: Path) -> None:
        data = _load_raw()
        data["failure_modes"][0]["severity"] = "critical"
        path = _write_tax(tmp_path, data)
        with pytest.raises(TaxonomyValidationError, match="bad severity"):
            load_taxonomy(path)

    def test_detection_check_empty_implemented_by_raises(self, tmp_path: Path) -> None:
        data = _load_raw()
        data["failure_modes"][0]["implemented_by"] = []
        path = _write_tax(tmp_path, data)
        with pytest.raises(
            TaxonomyValidationError,
            match="detection:check with empty implemented_by",
        ):
            load_taxonomy(path)

    def test_reserved_mode_may_have_empty_implemented_by(self, tmp_path: Path) -> None:
        data = _load_raw()
        reserved = dict(data["failure_modes"][0])
        reserved["id"] = "FM-099"
        reserved["slug"] = "reserved_placeholder"
        reserved["status"] = "reserved"
        reserved["implemented_by"] = []
        reserved["positive_examples"] = []
        reserved["negative_examples"] = []
        data["failure_modes"].append(reserved)
        path = _write_tax(tmp_path, data)
        tax = load_taxonomy(path, check_trace_refs=False)
        assert tax.by_id()["FM-099"].status == "reserved"

    def test_retired_id_reused_raises(self, tmp_path: Path) -> None:
        data = _load_raw()
        retired = dict(data["failure_modes"][0])
        retired["status"] = "retired"
        retired["retired_reason"] = "superseded"
        active = dict(data["failure_modes"][0])
        data["failure_modes"] = [retired, active] + data["failure_modes"][1:]
        path = _write_tax(tmp_path, data)
        with pytest.raises(TaxonomyValidationError, match="retired id reused: FM-001"):
            load_taxonomy(path)

    def test_bad_harness_layer_raises(self, tmp_path: Path) -> None:
        data = _load_raw()
        data["failure_modes"][0]["harness_layer"] = "not-a-layer"
        path = _write_tax(tmp_path, data)
        with pytest.raises(TaxonomyValidationError, match="bad harness_layer"):
            load_taxonomy(path)
