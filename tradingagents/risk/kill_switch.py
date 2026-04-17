"""
§11.2 Kill switch — touch /tmp/quantum_agent_kill to halt all trading.
"""

from __future__ import annotations

import sys
from pathlib import Path

KILL_FILE = Path("/tmp/quantum_agent_kill")


def check_kill_switch() -> None:
    """Raise SystemExit if kill switch file exists."""
    if KILL_FILE.exists():
        raise SystemExit(
            f"KILL SWITCH ACTIVATED: {KILL_FILE} exists. "
            f"Remove it to resume trading: rm {KILL_FILE}"
        )
