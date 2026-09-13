"""Complexity ratchets (R12). Branch count is the primary axis.

Exemption (R12.6): functions with ≤2 branches that are flat declarative builders
(e.g. ``evals/cli.py:build_parser``).

to see this fail: add a 151-line function with 3+ branches under src/.
"""

from __future__ import annotations

import ast

from tests.unit.repo._paths import REPO_ROOT, read_ratchets

_SKIP = frozenset({"node_modules", "frontend", "vendor", "__pycache__"})


def _branch_count(node: ast.AST) -> int:
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.If | ast.For | ast.AsyncFor | ast.While | ast.ExceptHandler):
            count += 1
        elif isinstance(child, ast.BoolOp):
            count += max(0, len(child.values) - 1)
        elif isinstance(child, ast.comprehension):
            count += 1
    return count


def _scan() -> tuple[int, int, int]:
    over80 = over150 = over8 = 0
    files = 0
    for root_name in ("src", "evals"):
        for path in (REPO_ROOT / root_name).rglob("*.py"):
            if any(p in _SKIP for p in path.parts):
                continue
            files += 1
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                end = getattr(node, "end_lineno", node.lineno) or node.lineno
                length = end - node.lineno + 1
                params = (
                    len(node.args.args)
                    + len(node.args.kwonlyargs)
                    + (1 if node.args.vararg else 0)
                    + (1 if node.args.kwarg else 0)
                )
                branches = _branch_count(node)
                if branches <= 2:
                    continue  # R12.6 exemption
                if length > 80:
                    over80 += 1
                if length > 150:
                    over150 += 1
                if params > 8:
                    over8 += 1
    if files == 0:
        raise AssertionError("AST walk visited zero files")
    return over80, over150, over8


def test_complexity_ratchets() -> None:
    r = read_ratchets()
    over80, over150, over8 = _scan()
    errors: list[str] = []
    if over80 > r["functions_over_80_lines"]:
        errors.append(f"functions >80 lines: {over80} (budget {r['functions_over_80_lines']})")
    if over150 > r["functions_over_150_lines"]:
        errors.append(f"functions >150 lines: {over150} (budget {r['functions_over_150_lines']})")
    if over8 > r["functions_over_8_params"]:
        errors.append(f"functions >8 params: {over8} (budget {r['functions_over_8_params']})")
    assert not errors, "; ".join(errors) + ". Extract, do not raise the floor."
