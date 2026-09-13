"""Runtime image invariants that CI asserts after ``docker build`` (R18).

A ``RUN chown -R`` after COPY doubles the image (CI 2.55 GB vs 900 MB ratchet).
``build-essential`` / ``gcc`` belong in the builder stage only.

to see this fail: add ``RUN chown -R aiteam:aiteam /app`` to the runtime stage.
"""

from __future__ import annotations

from tests.unit.repo._paths import REPO_ROOT

_DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile"


def _runtime_stage(text: str) -> str:
    marker = "AS runtime"
    idx = text.find(marker)
    if idx < 0:
        raise AssertionError("docker/Dockerfile has no `AS runtime` stage")
    return text[idx:]


def test_runtime_copy_uses_chown_not_a_layer_chown() -> None:
    text = _DOCKERFILE.read_text(encoding="utf-8")
    runtime = _runtime_stage(text)
    assert "COPY --from=builder --chown=" in runtime
    assert "COPY --from=frontend --chown=" in runtime
    for line in runtime.splitlines():
        stripped = line.strip()
        if stripped.startswith("RUN") and "chown" in stripped:
            raise AssertionError(
                "runtime stage must not RUN chown (it duplicates COPY layers): " + stripped
            )


def test_runtime_apt_does_not_install_a_compiler() -> None:
    runtime = _runtime_stage(_DOCKERFILE.read_text(encoding="utf-8"))
    lowered = runtime.lower()
    for banned in ("build-essential", "gcc", "g++"):
        assert banned not in lowered, f"runtime stage mentions {banned!r}"


def test_ci_image_size_ratchet_reads_toml() -> None:
    """CI Size check must use ratchets.toml, not a second hardcoded ceiling."""
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "tests/unit/repo/ratchets.toml" in ci
    assert "docker_image_mb" in ci
    assert "900 * 1024 * 1024" not in ci
