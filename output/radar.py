from __future__ import annotations

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import constants


def plot_radar(results: list[dict], top_n: int = 3) -> None:
    if not results:
        return

    top_results = results[:top_n]
    angles = [n / float(len(constants.KEYS)) * 2 * math.pi for n in range(len(constants.KEYS))]
    angles += angles[:1]

    six_max = {k: max(r["compounds"][k] for r in top_results) for k in constants.KEYS}
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"polar": True})

    for index, result in enumerate(top_results, start=1):
        normalized = [result["compounds"][k] / max(six_max[k], 1e-8) for k in constants.KEYS]
        normalized += normalized[:1]
        ax.plot(angles, normalized, linewidth=2, label=f"#{index} score {result['score']:.1f}")
        ax.fill(angles, normalized, alpha=0.10)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(constants.KEYS)
    ax.set_yticklabels([])
    ax.set_ylim(0, 1)
    ax.set_title("AeroPress Top Results Radar")
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.10))
    fig.tight_layout()
    fig.savefig("radar_top3.png", dpi=150)
    plt.close(fig)
