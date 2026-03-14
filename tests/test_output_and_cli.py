import pytest
from pathlib import Path
import sys
import subprocess
import re
import os
import json
import csv
from output.export import export_json, export_csv
from output.radar import plot_radar


def _sample_results() -> list[dict]:
    return [
        {
            "brewer": "AeroPress XL",
            "water_ml": 400,
            "temp": 92,
            "dial": 4.5,
            "steep_sec": 120,
            "dose": 22.0,
            "swirl_sec": 5,
            "swirl_wait_sec": 30,
            "press_sec": 32,
            "press_sec_internal": 32,
            "total_contact_sec": 187,
            "ey": 19.2,
            "tds": 1.241,
            "fines_ratio": 0.15,
            "t_slurry": 88.3,
            "t_kinetic": 112.1,
            "retention": 2.3,
            "compounds": {"AC": 0.5, "SW": 1.0, "PS": 0.8, "CA": 0.88, "CGA": 1.0, "MEL": 0.6},
            "score": 78.5,
        }
    ]


def test_export_json_csv_and_radar(tmp_path: Path) -> None:
    results = _sample_results()
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        export_json(results, "medium", 50, 30)
        export_csv(results, "medium")
        plot_radar(results)
    finally:
        os.chdir(cwd)

    json_path = tmp_path / "output.json"
    csv_path = tmp_path / "output.csv"
    radar_path = tmp_path / "radar_top3.png"
    assert json_path.exists()
    assert csv_path.exists()
    assert radar_path.exists()
    assert radar_path.stat().st_size > 0

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["hoffman_constants"]["swirl_time_sec"] == 5
    assert payload["results"][0]["vectors"]["dose_g"] == 22.0

    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["compounds_AC"] == "0.5"





def test_cli_reference_command_ranges(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        str(root / "main.py"),
        "--brewer",
        "xl",
        "--roast",
        "medium",
        "--gh",
        "50",
        "--kh",
        "30",
        "--t-env",
        "25",
        "--altitude",
        "0",
        "--top",
        "1",
    ]
    completed = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=True, timeout=120)
    stdout = completed.stdout

    temp = int(re.search(r"水溫 (\d+)°C", stdout).group(1))
    dial = float(re.search(r"刻度 ([\d.]+)", stdout).group(1))
    steep_match = re.search(r"開始浸泡 (\d+):(\d+)", stdout)
    steep = int(steep_match.group(1)) * 60 + int(steep_match.group(2))
    dose = float(re.search(r"豆量 ([\d.]+)g", stdout).group(1))
    ey = float(re.search(r"EY ([\d.]+)%", stdout).group(1))
    tds = float(re.search(r"TDS ([\d.]+)%", stdout).group(1))
    score = float(re.search(r"風味評分：([\d.]+) / 100", stdout).group(1))
    t_slurry = float(re.search(r"漿體起始 ([\d.]+)°C", stdout).group(1))

    assert 88 <= temp <= 94
    assert 4.0 <= dial <= 6.5
    assert 90 <= steep <= 180
    assert 20 <= dose <= 28
    assert 14 <= ey <= 22
    assert 1.10 <= tds <= 1.35
    assert score > 70
    assert 3 <= (temp - t_slurry) <= 7


@pytest.mark.parametrize("roast,expected_temp_min,expected_temp_max", [
    ("very_light", 97, 100),  # 100 ± 3, capped at 100
    ("light", 95, 100),       # 98 ± 3, capped at 100
    ("medium_light", 92, 98), # 95 ± 3
    ("medium", 88, 94),       # 91 ± 3
    ("moderately_dark", 83, 89), # 86 ± 3
    ("dark", 79, 85),         # 82 ± 3
    ("very_dark", 77, 83),    # 80 ± 3
])
def test_cli_roast_base_temp_ranges(tmp_path: Path, roast: str, expected_temp_min: int, expected_temp_max: int) -> None:
    root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        str(root / "main.py"),
        "--brewer",
        "xl",
        "--roast",
        roast,
        "--gh",
        "50",
        "--kh",
        "30",
        "--t-env",
        "25",
        "--altitude",
        "0",
        "--top",
        "1",
    ]
    completed = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=True, timeout=120)
    stdout = completed.stdout

    temp = int(re.search(r"水溫 (\d+)°C", stdout).group(1))
    assert expected_temp_min <= temp <= expected_temp_max, f"For roast {roast}, temp {temp} not in range {expected_temp_min}-{expected_temp_max}"
