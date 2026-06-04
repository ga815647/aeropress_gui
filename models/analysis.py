"""Ad-hoc feedback analysis — recompute every logged cup under the CURRENT model.

feedback.jsonl stores only durable inputs + the user's evaluation (no tds/ey/
distance — see docs/FEEDBACK_FORMAT.md). This module projects those inputs
through today's Layer 1 + Layer 2 so cross-cup comparisons are always on one
consistent scale, instead of mixing values computed under different model
versions. Pure stdlib — no pandas (the dataset is tiny; a DataFrame is not worth
a dependency at this scale).

    from models import analysis
    rows = analysis.recomputed_rows("light")      # one dict per light cup
    print(analysis.format_rows(rows))              # ASCII table, sorted by stars
    analysis.by_stars("light")                     # {stars: [rows]} buckets

Or from a shell:  python -m models.analysis light
"""
from __future__ import annotations

from models.feedback import read_all, recompute_entry

# Columns surfaced per cup. Durable inputs + the *current* model projection +
# the user's verdict — never the on-disk (stale) derived values.
_COLUMNS = (
    "date", "roast", "temp", "dial", "steep_sec", "dose",
    "tds", "ey", "distance", "stars", "absolute", "overall",
)


def recomputed_rows(roast: str | None = None) -> list[dict]:
    """Every feedback cup as a flat row, with tds/ey/distance recomputed under
    the current model from its recipe inputs. Optionally filter by roast.
    Rows with no recomputable recipe snapshot get None for the derived fields."""
    rows: list[dict] = []
    for entry in read_all():
        if roast and entry.get("roast") != roast:
            continue
        recipe = entry.get("recipe") or {}
        derived = recompute_entry(entry) or {}
        rows.append({
            "timestamp": entry.get("timestamp"),
            "date": (entry.get("timestamp") or "")[:10],
            "recipe_id": entry.get("recipe_id"),
            "roast": entry.get("roast"),
            "temp": recipe.get("temp"),
            "dial": recipe.get("dial"),
            "steep_sec": recipe.get("steep_sec"),
            "dose": recipe.get("dose"),
            "tds": derived.get("tds"),
            "ey": derived.get("ey"),
            "distance": derived.get("distance"),
            "stars": entry.get("stars"),
            "absolute": entry.get("absolute"),
            "overall": entry.get("overall"),
            "compared_to": entry.get("compared_to"),
            "comment": entry.get("comment"),
        })
    return rows


def by_stars(roast: str | None = None) -> dict:
    """Recomputed rows bucketed by star rating (None = unrated), highest first."""
    buckets: dict = {}
    for row in recomputed_rows(roast):
        buckets.setdefault(row.get("stars"), []).append(row)
    order = sorted(buckets, key=lambda s: (s is None, -(s or 0)))
    return {s: buckets[s] for s in order}


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}" if abs(value) < 10 else f"{value:.2f}"
    return str(value)


def format_rows(rows: list[dict], columns: tuple[str, ...] = _COLUMNS) -> str:
    """ASCII table of the given rows, sorted by stars desc then date. For quick
    console / conversation inspection — no external deps."""
    ordered = sorted(rows, key=lambda r: (-(r.get("stars") or 0), r.get("date") or ""))
    cells = [[_fmt(r.get(c)) for c in columns] for r in ordered]
    widths = [max(len(columns[i]), *(len(row[i]) for row in cells)) if cells
              else len(columns[i]) for i in range(len(columns))]
    head = "  ".join(c.rjust(widths[i]) for i, c in enumerate(columns))
    lines = [head, "  ".join("-" * widths[i] for i in range(len(columns)))]
    lines += ["  ".join(row[i].rjust(widths[i]) for i in range(len(columns)))
              for row in cells]
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else None
    print(format_rows(recomputed_rows(target)))
