"""Figure 12: Phylogenetic depth plot."""

import json

from figures._shared import *


def generate_lineage() -> None:
    """Figure 12: Phylogenetic depth plot — generation vs step, colored by seed."""
    analysis_path = PROJECT_ROOT / "experiments" / "lineage_analysis.json"
    if not analysis_path.exists():
        print(f"  SKIP: {analysis_path} not found")
        return

    with open(analysis_path, encoding="utf-8") as f:
        analysis = json.load(f)

    events = analysis.get("events", [])
    if len(events) < 5:
        print("  SKIP: insufficient lineage events")
        return

    fig, ax = plt.subplots(figsize=(3.4, 2.8))

    steps = [e["step"] for e in events]
    gens = [e["generation"] for e in events]
    seeds = [e["seed"] for e in events]

    ax.scatter(steps, gens, c=seeds, s=4, alpha=0.4, cmap="viridis", edgecolors="none")
    ax.set_xlabel("Simulation Step")
    ax.set_ylabel("Generation")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Depth stats annotation
    ds = analysis.get("depth_stats", {})
    if ds:
        ax.text(
            0.98,
            0.95,
            f"Max gen: {ds.get('max', 0)}\nMean: {ds.get('mean', 0):.1f}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=7,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="0.8", alpha=0.9),
        )

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_lineage.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_lineage.pdf'}")
