"""
P2-T5: Guardrail test — yfinance must NEVER be imported on the decision path.

FORBIDDEN_DIRS (per SPEC §4.8.2, Session 0a hardening):
  agents/ risk/ scoring/ orchestration/ execution/

This test uses AST parsing to detect `import yfinance` or
`from yfinance import ...` in any .py file under those directories.

MUST pass on every commit from Phase 2 onward.
"""

from __future__ import annotations

import ast
import pathlib


FORBIDDEN_DIRS = ["agents", "risk", "scoring", "orchestration", "execution"]


def test_no_yfinance_import_on_decision_path():
    repo = pathlib.Path(__file__).parents[2] / "tradingagents"
    violations = []

    for d in FORBIDDEN_DIRS:
        target_dir = repo / d
        if not target_dir.exists():
            continue
        for py_file in target_dir.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "yfinance" in alias.name:
                            violations.append(f"{py_file}:{node.lineno}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if "yfinance" in module:
                        violations.append(f"{py_file}:{node.lineno}")

    assert not violations, (
        f"yfinance imported on decision path (violates §4.8.2):\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
