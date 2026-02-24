"""Cyclic period sweep experiment.

Runs cyclic environment with periods {500, 1000, 2000, 5000},
comparing evolution-on vs evolution-off for each period.

Usage:
    uv run python scripts/experiment_cyclic_sweep.py > experiments/cyclic_sweep_data.tsv

Output: TSV data to stdout + summary to stderr.
        Raw JSON saved to experiments/cyclic_sweep_p{period}_{evo_label}.json.
"""

import digital_life
from experiment_common import log, run_condition_suite

STEPS = 10000
SAMPLE_EVERY = 100
SEEDS = list(range(100, 130))  # test set: seeds 100-129, n=30

PERIODS = [500, 1000, 2000, 5000]
NORMAL_RATE = 0.01  # matches config default; not passed as override
LOW_RATE = 0.005

CONDITIONS = {
    f"p{period}_{evo_label}": {
        "metabolism_mode": "graph",
        "environment_cycle_period": period,
        "environment_cycle_low_rate": LOW_RATE,
        **({"enable_evolution": False} if evo_label == "evo_off" else {}),
    }
    for period in PERIODS
    for evo_label in ["evo_on", "evo_off"]
}


def main():
    """Run cyclic period sweep (4 periods x 2 conditions x 30 seeds)."""
    log(f"Digital Life v{digital_life.version()}")
    log(
        f"Cyclic sweep: {STEPS} steps, sample every {SAMPLE_EVERY}, "
        f"seeds {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})"
    )
    log(f"Periods: {PERIODS}, normal rate: {NORMAL_RATE}, low rate: {LOW_RATE}")
    log("")
    run_condition_suite("cyclic_sweep_", CONDITIONS, STEPS, SEEDS, SAMPLE_EVERY)


if __name__ == "__main__":
    main()
