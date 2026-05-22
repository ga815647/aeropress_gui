from __future__ import annotations

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from models.sensory import ATTRIBUTES


def plot_radar(results: list[dict], top_n: int = 3) -> None:
    """Radar of the 10 sensory attributes — Top-N predicted profiles vs the IDEAL.

    Attribute values are CATA detection frequencies (nominally [0, 1]); plotted
    on a shared raw scale, no per-attribute normalization, so the gap to the
    dashed IDEAL polygon reads directly as sensory distance.
    """
    if not results:
        return

    top_results = results[:top_n]
    n = len(ATTRIBUTES)
    angles = [k / float(n) * 2 * math.pi for k in range(n)]
    angles += angles[:1]

    ideal = top_results[0]["ideal"]
    attr_max = max(
        max(r["attributes"][a] for a in ATTRIBUTES for r in top_results),
        max(ideal[a] for a in ATTRIBUTES),
    )
    y_top = math.ceil(attr_max * 10) / 10 + 0.05

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"polar": True})

    ideal_vals = [ideal[a] for a in ATTRIBUTES]
    ideal_vals += ideal_vals[:1]
    ax.plot(angles, ideal_vals, linewidth=2, linestyle="--", color="black", label="IDEAL")
    ax.fill(angles, ideal_vals, alpha=0.05, color="black")

    for index, result in enumerate(top_results, start=1):
        vals = [result["attributes"][a] for a in ATTRIBUTES]
        vals += vals[:1]
        ax.plot(angles, vals, linewidth=2, label=f"#{index} dist {result['distance']:.4f}")
        ax.fill(angles, vals, alpha=0.10)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(list(ATTRIBUTES))
    ax.set_ylim(0, y_top)
    ax.set_title("AeroPress — 10 Sensory Attributes vs IDEAL")
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.10))
    fig.tight_layout()
    fig.savefig("radar_top3.png", dpi=150)
    plt.close(fig)
