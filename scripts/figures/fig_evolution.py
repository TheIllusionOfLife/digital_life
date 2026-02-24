"""Figure 4: Evolution strengthening — long run + env shift."""

from collections import defaultdict

import numpy as np
from figures._shared import *


def generate_evolution() -> None:
    """Figure 4: Evolution strengthening — long run + env shift."""
    exp_dir = PROJECT_ROOT / "experiments"

    conditions = {
        "long_normal": ("Normal", "#000000"),
        "long_no_evolution": ("No Evolution", "#CC79A7"),
        "shift_normal": ("Normal", "#000000"),
        "shift_no_evolution": ("No Evolution", "#CC79A7"),
    }

    # Load time-series
    cond_data: dict[str, dict[int, list[float]]] = {}
    for cond in conditions:
        path = exp_dir / f"evolution_{cond}.json"
        if not path.exists():
            print(f"  SKIP: {path} not found")
            return
        results = load_json(path)
        step_vals: dict[int, list[float]] = defaultdict(list)
        for r in results:
            for s in r["samples"]:
                step_vals[s["step"]].append(s["alive_count"])
        cond_data[cond] = step_vals

    fig, axes = plt.subplots(2, 1, figsize=(3.4, 4.0), sharex=False)

    # Top: Long run (10K steps)
    ax = axes[0]
    for cond in ["long_normal", "long_no_evolution"]:
        label, color = conditions[cond]
        steps = sorted(cond_data[cond].keys())
        means = [np.mean(cond_data[cond][s]) for s in steps]
        sems = [
            np.std(cond_data[cond][s], ddof=1) / np.sqrt(len(cond_data[cond][s]))
            if len(cond_data[cond][s]) > 1
            else 0.0
            for s in steps
        ]
        means, sems = np.array(means), np.array(sems)
        ls = "-" if "normal" in cond and "no_" not in cond else "--"
        ax.plot(steps, means, color=color, linestyle=ls, label=label)
        ax.fill_between(steps, means - sems, means + sems, color=color, alpha=0.15)
    ax.set_ylabel("Alive Count")
    ax.set_title("Long run (10,000 steps)", fontsize=9)
    ax.set_ylim(bottom=0)
    ax.legend(loc="lower right", fontsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Bottom: Shift run (5K steps)
    ax = axes[1]
    for cond in ["shift_normal", "shift_no_evolution"]:
        label, color = conditions[cond]
        steps = sorted(cond_data[cond].keys())
        means = [np.mean(cond_data[cond][s]) for s in steps]
        sems = [
            np.std(cond_data[cond][s], ddof=1) / np.sqrt(len(cond_data[cond][s]))
            if len(cond_data[cond][s]) > 1
            else 0.0
            for s in steps
        ]
        means, sems = np.array(means), np.array(sems)
        ls = "-" if "normal" in cond and "no_" not in cond else "--"
        ax.plot(steps, means, color=color, linestyle=ls, label=label)
        ax.fill_between(steps, means - sems, means + sems, color=color, alpha=0.15)
    ax.axvline(x=2500, color="#888888", linestyle=":", linewidth=0.8, label="Env. shift")
    ax.set_xlabel("Step")
    ax.set_ylabel("Alive Count")
    ax.set_title("Environmental shift at step 2,500", fontsize=9)
    ax.set_ylim(bottom=0)
    ax.legend(loc="lower right", fontsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_evolution.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_evolution.pdf'}")
