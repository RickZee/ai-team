"""Build the spec register in ``.kiro/specs/README.md`` from the specs themselves.

Why this exists: every spec header said "Draft for implementation" long after its tasks
were done, because a status typed by hand drifts. The register is generated from each
spec's own header (``Spec ID``, ``Created``, ``Status``, ``Depends on``), so it can only be
as stale as the specs, and a test fails when the README falls behind.

Task counts are deliberately not in the README table: a task box is ticked in almost every
spec PR, and a count in the table would make the README stale on every one of them. The
table changes only when a spec is added or a header changes. Run the script with no flags
to see the counts.

Order is creation order: ``Created`` date, then dependencies before dependents on the
same day, then name. The number lives in the register,
not in folder names, because folder names are linked from ~130 places.

Usage::

    uv run python scripts/spec_index.py           # print the register, with task counts
    uv run python scripts/spec_index.py --write   # update the README between the markers
    uv run python scripts/spec_index.py --check   # exit 1 if the README is out of date
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPECS_DIR = REPO_ROOT / ".kiro" / "specs"
README = SPECS_DIR / "README.md"
START = "<!-- spec-index:start -->"
END = "<!-- spec-index:end -->"

# Allowed statuses. "Done" means every task an agent can do is checked; tasks that need a
# human to spend money may stay open (CLAUDE.md: "leave human-triggered spend tasks open").
STATUSES = ("Draft", "In progress", "Done", "Replaced by")

_FIELD = re.compile(r"^\*\*(?P<key>[^*]+):\*\*\s*(?P<value>.*)$")
_LINK = re.compile(r"\.\./([a-z0-9-]+)/")
_TASK = re.compile(r"^- \[(?P<mark>[ x])\]")


@dataclass(frozen=True)
class Spec:
    """One spec folder, as read from its requirements header and task list."""

    spec_id: str
    created: str
    status: str
    depends_on: tuple[str, ...]
    done: int
    total: int

    @property
    def status_kind(self) -> str:
        """The status vocabulary word the header starts with ('' if none matches)."""
        for kind in STATUSES:
            if self.status.startswith(kind):
                return kind
        return ""


def header_fields(text: str) -> dict[str, str]:
    """Return the ``**Key:** value`` fields at the top of a requirements file.

    A field's value continues onto following lines until the next field, a blank line,
    a heading or a rule, so multi-line ``Depends on`` entries are read whole.
    """
    fields: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## ") or line.strip() == "---":
            break
        match = _FIELD.match(line)
        if match:
            current = match["key"].strip()
            fields[current] = match["value"].strip()
        elif current and line.strip():
            fields[current] += " " + line.strip()
        elif not line.strip():
            current = None
    return fields


def count_tasks(text: str) -> tuple[int, int]:
    """Return (checked, total) for top-level ``- [ ]`` / ``- [x]`` task lines."""
    marks = [m["mark"] for m in (_TASK.match(line) for line in text.splitlines()) if m]
    return marks.count("x"), len(marks)


def read_spec(folder: Path, known: set[str]) -> Spec:
    """Read one spec folder. ``known`` limits ``depends_on`` to real spec folders."""
    fields = header_fields((folder / "requirements.md").read_text())
    tasks = folder / "tasks.md"
    done, total = count_tasks(tasks.read_text()) if tasks.exists() else (0, 0)
    deps = tuple(
        dict.fromkeys(
            name
            for name in _LINK.findall(fields.get("Depends on", ""))
            if name in known and name != folder.name
        )
    )
    return Spec(
        spec_id=fields.get("Spec ID", folder.name).strip("`"),
        created=fields.get("Created", ""),
        status=fields.get("Status", ""),
        depends_on=deps,
        done=done,
        total=total,
    )


def load_specs(specs_dir: Path = SPECS_DIR) -> list[Spec]:
    """All spec folders with a requirements file, in creation order (see module docstring)."""
    folders = sorted(p for p in specs_dir.iterdir() if (p / "requirements.md").exists())
    known = {p.name for p in folders}
    specs = [read_spec(p, known) for p in folders]
    by_id = {s.spec_id: s for s in specs}

    def depth(spec: Spec, seen: frozenset[str] = frozenset()) -> int:
        # Longest dependency chain. Breaks same-day ties so a spec lists after what it needs.
        parents = [by_id[d] for d in spec.depends_on if d in by_id and d not in seen]
        return 1 + max((depth(d, seen | {spec.spec_id}) for d in parents), default=-1)

    return sorted(specs, key=lambda s: (s.created, depth(s), s.spec_id))


def render(specs: list[Spec], *, with_tasks: bool = False) -> str:
    """The register as a Markdown table, wrapped in the README markers.

    Args:
        specs: Specs in register order.
        with_tasks: Add a "Tasks done" column. Off for the README (see module docstring).
    """
    task_head, task_rule = (" Tasks done |", " --- |") if with_tasks else ("", "")
    rows = [
        START,
        "<!-- Generated by scripts/spec_index.py. Edit the spec headers, then run it with --write. -->",
        "",
        f"| # | Spec | Created | Status |{task_head} Depends on |",
        f"| --- | --- | --- | --- |{task_rule} --- |",
    ]
    for number, spec in enumerate(specs, start=1):
        deps = ", ".join(f"[{d}](./{d}/)" for d in spec.depends_on) or "—"
        tasks = ""
        if with_tasks:
            tasks = f" {spec.done}/{spec.total} |" if spec.total else " — |"
        rows.append(
            f"| {number} | [{spec.spec_id}](./{spec.spec_id}/) | {spec.created} "
            f"| {spec.status} |{tasks} {deps} |"
        )
    rows += ["", END]
    return "\n".join(rows)


def problems(specs: list[Spec]) -> list[str]:
    """Header problems that make the register untrustworthy."""
    found = []
    for spec in specs:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", spec.created):
            found.append(f"{spec.spec_id}: Created is not a YYYY-MM-DD date: {spec.created!r}")
        if not spec.status_kind:
            found.append(
                f"{spec.spec_id}: Status must start with one of {STATUSES}: {spec.status!r}"
            )
        if spec.status_kind == "Done" and spec.total and spec.done == 0:
            found.append(f"{spec.spec_id}: Status is Done but no task is checked")
    return found


def updated_readme(readme_text: str, block: str) -> str:
    """Replace the marked block in the README (markers must already exist)."""
    if START not in readme_text or END not in readme_text:
        raise ValueError(f"{README} has no {START} / {END} markers")
    head, _, rest = readme_text.partition(START)
    _, _, tail = rest.partition(END)
    return head + block + tail


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="update the README in place")
    mode.add_argument("--check", action="store_true", help="exit 1 if the README is stale")
    args = parser.parse_args(argv)

    specs = load_specs()
    issues = problems(specs)
    for issue in issues:
        print(f"spec_index: {issue}", file=sys.stderr)
    block = render(specs)

    if args.write:
        README.write_text(updated_readme(README.read_text(), block))
        print(f"spec_index: wrote {len(specs)} specs to {README.relative_to(REPO_ROOT)}")
        return 1 if issues else 0
    if args.check:
        current = README.read_text()
        if updated_readme(current, block) != current:
            print("spec_index: README register is stale; run with --write", file=sys.stderr)
            return 1
        return 1 if issues else 0
    print(render(specs, with_tasks=True))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
