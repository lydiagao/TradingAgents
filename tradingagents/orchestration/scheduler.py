"""
§11.1 Scheduler — launchd plist generation + install (macOS).

NOT APScheduler (SPEC ADR: single-shot + launchd is simpler and crash-independent).

Usage:
    python -m tradingagents.orchestration.scheduler install   # install launchd job
    python -m tradingagents.orchestration.scheduler uninstall # remove launchd job
    python -m tradingagents.orchestration.scheduler status    # check if loaded
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

PLIST_LABEL = "com.quantum-agent.daily-cycle"
PLIST_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_PATH = PLIST_DIR / f"{PLIST_LABEL}.plist"

# Paths
PROJECT_DIR = Path(__file__).parent.parent.parent.resolve()
VENV_PYTHON = PROJECT_DIR / ".venv" / "bin" / "python"
LOG_DIR = Path.home() / ".tradingagents"


def generate_plist() -> str:
    """Generate the launchd plist XML.

    Schedule: Weekdays at 07:00 local time (= 08:00 ET, since system is CT).
    """
    return dedent(f"""\
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>Label</key>
        <string>{PLIST_LABEL}</string>

        <key>ProgramArguments</key>
        <array>
            <string>{VENV_PYTHON}</string>
            <string>-m</string>
            <string>tradingagents.daily_cycle</string>
            <string>--tickers</string>
            <string>IONQ,RGTI,QBTS,QUBT</string>
        </array>

        <key>WorkingDirectory</key>
        <string>{PROJECT_DIR}</string>

        <key>StartCalendarInterval</key>
        <array>
            <!-- Monday through Friday at 07:00 local (CT) = 08:00 ET -->
            <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
            <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
            <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
            <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
            <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
        </array>

        <key>StandardOutPath</key>
        <string>{LOG_DIR}/daily_cycle_stdout.log</string>

        <key>StandardErrorPath</key>
        <string>{LOG_DIR}/daily_cycle_stderr.log</string>

        <key>EnvironmentVariables</key>
        <dict>
            <key>PATH</key>
            <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:{Path.home()}/.local/bin</string>
            <key>HOME</key>
            <string>{Path.home()}</string>
        </dict>

        <key>RunAtLoad</key>
        <false/>

        <key>Nice</key>
        <integer>10</integer>
    </dict>
    </plist>
    """)


def install():
    """Write plist and load into launchd."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PLIST_DIR.mkdir(parents=True, exist_ok=True)

    plist_content = generate_plist()
    PLIST_PATH.write_text(plist_content)
    print(f"Plist written to {PLIST_PATH}")

    # Unload first if already loaded (ignore errors)
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)],
                   capture_output=True, check=False)

    result = subprocess.run(["launchctl", "load", str(PLIST_PATH)],
                            capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Loaded: {PLIST_LABEL}")
        print(f"Schedule: Weekdays at 07:00 CT (= 08:00 ET)")
        print(f"Logs: {LOG_DIR}/daily_cycle_*.log")
    else:
        print(f"Load failed: {result.stderr}")
        sys.exit(1)


def uninstall():
    """Unload from launchd and remove plist."""
    result = subprocess.run(["launchctl", "unload", str(PLIST_PATH)],
                            capture_output=True, text=True)
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
        print(f"Removed: {PLIST_PATH}")
    print(f"Unloaded: {PLIST_LABEL}")


def status():
    """Check if the job is loaded."""
    result = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    if PLIST_LABEL in result.stdout:
        # Find the line
        for line in result.stdout.splitlines():
            if PLIST_LABEL in line:
                print(f"LOADED: {line}")
                return
    else:
        print(f"NOT LOADED: {PLIST_LABEL}")
        if PLIST_PATH.exists():
            print(f"  Plist exists at {PLIST_PATH} — run 'install' to load")
        else:
            print(f"  No plist found — run 'install' to create")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m tradingagents.orchestration.scheduler {install|uninstall|status}")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "install":
        install()
    elif cmd == "uninstall":
        uninstall()
    elif cmd == "status":
        status()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
