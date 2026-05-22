"""Phase 10 output renderers (output/*) + the main.py CLI.

export_json / export_csv / plot_radar consume real optimizer results (10
sensory attributes + distance, no compounds / score). The CLI smoke test runs
main.py end to end.
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from optimizer import optimize
from output.export import export_csv, export_json
from output.radar import plot_radar
from models.sensory import ATTRIBUTES


def _sample_results():
    return optimize(roast_code="medium_light", brewer_size="xl", temp=95.0, top_n=3)


def test_export_json_csv_and_radar(tmp_path: Path) -> None:
    results = _sample_results()
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        export_json(results, "medium_light", 95.0)
        export_csv(results, "medium_light")
        plot_radar(results)
    finally:
        os.chdir(cwd)

    json_path = tmp_path / "output.json"
    csv_path = tmp_path / "output.csv"
    radar_path = tmp_path / "radar_top3.png"
    assert json_path.exists() and csv_path.exists()
    assert radar_path.exists() and radar_path.stat().st_size > 0

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(payload["results"]) == 3
    first = payload["results"][0]
    assert "distance" in first
    assert set(first["attributes"]) == set(ATTRIBUTES)
    assert "ideal" in first
    # the compound-era fields are gone
    assert "compounds" not in first and "score" not in first

    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert "distance" in rows[0]
    assert "attr_Sour" in rows[0] and "ideal_Sour" in rows[0]


def test_cli_runs_and_reports_distance(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [sys.executable, str(root / "main.py"),
         "--roast", "medium_light", "--brewer", "xl", "--top", "1"],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=120, check=True,
    )
    stdout = completed.stdout
    # Phase 10 terminal output: distance headline + recipe_id, no 0-100 score
    assert "距目標" in stdout
    assert re.search(r"recipe_id=[0-9a-f]{12}", stdout)
    assert "預測 TDS" in stdout
    assert "/ 100" not in stdout


def test_cli_json_output(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.run(
        [sys.executable, str(root / "main.py"),
         "--roast", "light", "--brewer", "xl", "--top", "2", "--output", "json"],
        cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=120, check=True,
    )
    payload = json.loads((tmp_path / "output.json").read_text(encoding="utf-8"))
    assert len(payload["results"]) == 2
    assert "distance" in payload["results"][0]
