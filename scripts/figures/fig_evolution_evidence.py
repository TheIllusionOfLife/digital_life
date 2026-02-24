"""Figure 15: Evolution evidence — genome drift trajectories and cyclic recovery rates."""

import numpy as np
from figures._shared import *


def generate_evolution_evidence() -> None:
    """Figure 15: Evolution evidence — genome drift trajectories and cyclic recovery rates."""
    exp_dir = PROJECT_ROOT / "experiments"
    evidence_path = exp_dir / "evolution_evidence.json"
    if not evidence_path.exists():
        print(f"  SKIP: {evidence_path} not found")
        return

    with open(evidence_path) as f:
        import json

        evidence = json.load(f)

    drift = evidence.get("drift_trajectories", {})
    trajectory_steps = drift.get("trajectory_steps", [])
    trajectory_normal = drift.get("trajectory_normal_mean", [])
    trajectory_no_evo = drift.get("trajectory_no_evo_mean", [])

    if not trajectory_steps or not trajectory_normal:
        print("  SKIP: missing drift trajectory data")
        return

    cyclic = evidence.get("cyclic_recovery", {})
    per_cycle = cyclic.get("per_cycle", [])

    fig, axes = plt.subplots(1, 2, figsize=(7, 3.0))

    # Panel A: Genome drift trajectories
    ax = axes[0]
    ax.plot(
        trajectory_steps,
        trajectory_normal,
        color="#000000",
        linewidth=1.5,
        linestyle="-",
        label="Normal",
    )
    ax.plot(
        trajectory_steps,
        trajectory_no_evo,
        color="#CC79A7",
        linewidth=1.5,
        linestyle="--",
        label="No Evolution",
    )
    ax.set_xlabel("Simulation Step")
    ax.set_ylabel("Mean Genome Drift")
    ax.set_title("(A) Genome Drift Trajectories", fontsize=9)
    ax.legend(loc="upper left", fontsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Panel B: Per-cycle recovery rates
    ax = axes[1]
    if per_cycle:
        n_cycles = len(per_cycle)
        x = np.arange(n_cycles)
        width = 0.35
        evo_on_rates = [c["evo_on_rate_mean"] for c in per_cycle]
        evo_off_rates = [c["evo_off_rate_mean"] for c in per_cycle]
        cycle_labels = [f"{c['high_start']}-{c['high_end']}" for c in per_cycle]

        ax.bar(
            x - width / 2,
            evo_on_rates,
            width,
            label="Evo On",
            color="#000000",
            alpha=0.6,
        )
        ax.bar(
            x + width / 2,
            evo_off_rates,
            width,
            label="Evo Off",
            color="#CC79A7",
            alpha=0.6,
        )
        ax.set_xticks(x)
        ax.set_xticklabels(cycle_labels)
        ax.set_xlabel("Cycle Window (steps)")
        ax.legend(loc="upper right", fontsize=7)
    ax.set_ylabel("Recovery Rate")
    ax.set_title("(B) Per-Cycle Recovery Rates", fontsize=9)
    ax.set_ylim(bottom=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_evolution_evidence.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_evolution_evidence.pdf'}")
