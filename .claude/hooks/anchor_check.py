"""Anchor check hook — auto-runs diagnose_anchor.py after model-affecting edits.

Triggered as a PostToolUse hook for Edit/Write/MultiEdit. Filters by file path:
only fires when modifying files that change the Phase 10 model.

Decision is keyed on diagnose_anchor.py's EXIT CODE (not a string grep):
  exit != 0  → decision "block" + reason → the assistant must fix until it passes
               (a crash in diagnose itself also exits non-zero → correctly blocks,
               instead of the old behaviour of silently injecting a fake PASS)
  exit == 0  → injects a brief PASS summary into model context

The hook receives the standard PostToolUse JSON payload on stdin and emits
hook control JSON on stdout (see Claude Code hooks schema).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

# Files whose modification changes the Phase 10 model → must re-validate.
# (Phase 10: layer1 / sensory / distance / ideal — the old compounds / ey_model
# / tds_model / scoring modules are deleted.)
TRIGGER_SUFFIXES = (
    "/constants.py",
    "/models/layer1.py",
    "/models/sensory.py",
    "/models/distance.py",
    "/models/ideal.py",
    "/data/ideal.json",
)

# Project root = parent of .claude/, derived from this script's path.
PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        # Bad input → silently pass (don't break tool flow on a malformed payload)
        return

    tool_input = data.get("tool_input") or {}
    file_path = (tool_input.get("file_path") or "").replace("\\", "/")
    if not file_path:
        return

    if not any(file_path.lower().endswith(suf) for suf in TRIGGER_SUFFIXES):
        return  # not a trigger file

    # Confirm the file is in THIS project (defensive — avoid firing for a
    # same-named file in another repo if CWD ever differs).
    project_norm = PROJECT_ROOT.replace("\\", "/").lower()
    if not file_path.lower().startswith(project_norm):
        return

    try:
        result = subprocess.run(
            [sys.executable, "diagnose_anchor.py"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        output = (result.stdout or "") + (result.stderr or "")
        failed = result.returncode != 0
    except Exception as e:
        # Could not run diagnose at all → treat as a failure, not a pass.
        print(json.dumps({
            "decision": "block",
            "reason": f"Could not run diagnose_anchor.py: {e}",
            "systemMessage": "Anchor check could not run — investigate",
        }))
        return

    # Trim to the last 30 lines — the per-check summary lives at the end.
    trimmed = "\n".join(output.splitlines()[-30:])

    if failed:
        print(json.dumps({
            "decision": "block",
            "reason": (
                "diagnose_anchor.py FAILED (non-zero exit) after a model change.\n"
                "CLAUDE.md mandates fixing the model until all checks pass before "
                "reporting completion.\n\n"
                "Output (last 30 lines):\n" + trimmed
            ),
            "systemMessage": "Anchor diagnostics FAILED — fix the model until it passes",
        }))
    else:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    "diagnose_anchor.py ran automatically after a model change "
                    "and ALL checks pass (Layer 1 physics + Layer 2 sensory "
                    "distance).\n\nLast 30 lines:\n" + trimmed
                ),
            },
            "systemMessage": "Anchor diagnostics PASS",
        }))


if __name__ == "__main__":
    main()
