"""Figure 6: Violin/strip plots for ablation distributions."""

import numpy as np
from figures._shared import *


def generate_ablation_distributions() -> None:
    """Figure 6: Violin/strip plots showing per-seed distributions for each condition."""
    exp_dir = PROJECT_ROOT / "experiments"

    # Collect final alive counts per condition
    condition_data: dict[str, np.ndarray] = {}
    for condition in CONDITION_ORDER:
        path = exp_dir / f"final_graph_{condition}.json"
        if not path.exists():
            print(f"  SKIP: {path} not found")
            return
        results = load_json(path)
        condition_data[condition] = np.array(
            [r["final_alive_count"] for r in results if "samples" in r]
        )

    if condition_data["normal"].size == 0:
        print("  SKIP: No valid 'normal' condition data found")
        return
    normal_mean = float(np.mean(condition_data["normal"]))

    fig, ax = plt.subplots(figsize=(7, 3.0))

    positions = list(range(len(CONDITION_ORDER)))
    data_list = [condition_data[c] for c in CONDITION_ORDER]

    parts = ax.violinplot(
        data_list,
        positions=positions,
        showmeans=False,
        showmedians=False,
        showextrema=False,
    )
    for i, body in enumerate(parts["bodies"]):
        color = COLORS[CONDITION_ORDER[i]]
        body.set_facecolor(color)
        body.set_alpha(0.3)
        body.set_edgecolor(color)
        body.set_linewidth(0.8)

    # Overlay individual data points (strip plot)
    rng = np.random.default_rng(0)
    for i, condition in enumerate(CONDITION_ORDER):
        vals = condition_data[condition]
        jitter = rng.uniform(-0.15, 0.15, size=len(vals))
        ax.scatter(
            i + jitter,
            vals,
            s=8,
            alpha=0.6,
            color=COLORS[condition],
            edgecolors="none",
            zorder=5,
        )
        # Median marker
        ax.scatter(
            i,
            np.median(vals),
            s=30,
            color=COLORS[condition],
            edgecolors="white",
            linewidths=0.8,
            zorder=10,
            marker="D",
        )

    # Normal baseline reference line
    ax.axhline(
        y=normal_mean,
        color="#000000",
        linestyle=":",
        linewidth=0.8,
        alpha=0.5,
        label=f"Normal mean ({normal_mean:.0f})",
    )

    ax.set_xticks(positions)
    ax.set_xticklabels([LABELS[c] for c in CONDITION_ORDER], rotation=30, ha="right")
    ax.set_ylabel("Final Alive Count ($N_T$)")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper right", fontsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_ablation_distributions.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_ablation_distributions.pdf'}")
