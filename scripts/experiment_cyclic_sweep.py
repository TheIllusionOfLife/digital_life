"""Cyclic period sweep experiment.

Runs cyclic environment with periods {500, 1000, 2000, 5000},
comparing evolution-on vs evolution-off for each period.

Usage:
    uv run python scripts/experiment_cyclic_sweep.py > experiments/cyclic_sweep_data.tsv

Output: TSV data to stdout + summary to stderr.
        Raw JSON saved to experiments/cyclic_sweep_{condition}.json.
"""

import json
import time
from pathlib import Path

import digital_life
from experiment_common import (
    log,
    print_header,
    print_sample,
    run_single,
    safe_path,
)

STEPS = 10000
SAMPLE_EVERY = 100
SEEDS = list(range(100, 130))  # test set: seeds 100-129, n=30

PERIODS = [500, 1000, 2000, 5000]
NORMAL_RATE = 0.01  # matches config default; not passed as override
LOW_RATE = 0.005


def main():
    """Run cyclic period sweep (4 periods x 2 conditions x 30 seeds)."""
    log(f"Digital Life v{digital_life.version()}")
    log(f"Cyclic sweep: {STEPS} steps, sample every {SAMPLE_EVERY}, "
        f"seeds {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})")
    log(f"Periods: {PERIODS}, normal rate: {NORMAL_RATE}, low rate: {LOW_RATE}")
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)

    print_header()
    total_start = time.perf_counter()

    for period in PERIODS:
        for evo_label, enable_evo in [("evo_on", True), ("evo_off", False)]:
            cond_name = f"sweep_p{period}_{evo_label}"
            overrides = {
                "metabolism_mode": "graph",
                "environment_cycle_period": period,
                "environment_cycle_low_rate": LOW_RATE,
            }
            if not enable_evo:
                overrides["enable_evolution"] = False

            log(f"--- Condition: {cond_name} ---")
            results = []
            cond_start = time.perf_counter()

            for seed in SEEDS:
                t0 = time.perf_counter()
                result = run_single(seed, overrides, steps=STEPS, sample_every=SAMPLE_EVERY)
                elapsed = time.perf_counter() - t0
                results.append(result)

                for s in result["samples"]:
                    print_sample(cond_name, seed, s)

                final = result["final_alive_count"]
                log(f"  seed={seed:3d}  alive={final:4d}  {elapsed:.2f}s")

            cond_elapsed = time.perf_counter() - cond_start
            log(f"  Condition time: {cond_elapsed:.1f}s")

            raw_path = safe_path(out_dir, f"cyclic_sweep_{cond_name}.json")
            with open(raw_path, "w") as f:
                json.dump(results, f, indent=2)
            log(f"  Saved: {raw_path}")
            log("")

    total_elapsed = time.perf_counter() - total_start
    log(f"Total experiment time: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
