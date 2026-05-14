"""Anchor check hook — auto-runs diagnose_anchor.py after physics-affecting edits.

Triggered as PostToolUse hook for Edit/Write/MultiEdit. Filters by file path:
only fires when modifying scoring-affecting files (constants / models).

If diagnose_anchor.py output contains [ FAIL ]:
  → decision: "block" + reason → assistant must fix constants until anchors pass
If all 6 anchors PASS:
  → injects brief summary into model context (additionalContext)

The hook receives the standard PostToolUse JSON payload on stdin and emits
hook control JSON on stdout (see Claude Code hooks schema).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

# Files whose modification affects scoring physics → must validate anchors
TRIGGER_SUFFIXES = (
    "/constants.py",
    "/models/compounds.py",
    "/models/scoring.py",
    "/models/ey_model.py",
    "/models/tds_model.py",
)

# Project root = parent of .claude/, derived from this script's path.
# Robust regardless of where the hook is invoked from.
PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        # Bad input → silently pass (don't break tool flow on malformed hook payload)
        return

    tool_input = data.get("tool_input") or {}
    file_path = (tool_input.get("file_path") or "").replace("\\", "/")
    if not file_path:
        return

    if not any(file_path.lower().endswith(suf) for suf in TRIGGER_SUFFIXES):
        return  # Not a trigger file

    # Confirm the file is in THIS project (defensive — avoid firing for
    # same-named files in another repo if CWD ever differs).
    project_norm = PROJECT_ROOT.replace("\\", "/").lower()
    if not file_path.lower().startswith(project_norm):
        return

    try:
        result = subprocess.run(
            ["python", "diagnose_anchor.py"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = (result.stdout or "") + (result.stderr or "")
    except Exception as e:
        print(json.dumps({
            "systemMessage": f"Anchor hook error: {e}",
        }))
        return

    # Trim to last 30 lines — full output is verbose, summary is enough for context.
    trimmed = "\n".join(output.splitlines()[-30:])

    if "[ FAIL ]" in output:
        print(json.dumps({
            "decision": "block",
            "reason": (
                "diagnose_anchor.py reported [ FAIL ] after constants/models change.\n"
                "CLAUDE.md mandates fixing constants until all 6 anchors PASS "
                "before reporting completion.\n\n"
                "Output (last 30 lines):\n" + trimmed
            ),
            "systemMessage": "Anchor test FAILED — fix constants until 6 anchors PASS",
        }))
    else:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    "Anchor test ran automatically after constants/models change. "
                    "All 6 anchors PASS (Hoffman / April / Champion / Under / Over / Hedrick).\n\n"
                    "Last 30 lines of diagnose_anchor.py output:\n" + trimmed
                ),
            },
            "systemMessage": "Anchor test PASS (6/6)",
        }))


if __name__ == "__main__":
    main()
