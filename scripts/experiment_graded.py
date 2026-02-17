"""Graded metabolic ablation experiment.

Sweeps metabolism_efficiency_multiplier over [1.0, 0.75, 0.5, 0.25, 0.0]
to produce a dose-response curve for metabolic efficiency.

Usage:
    uv run python scripts/experiment_graded.py > experiments/graded_data.tsv

Output: TSV data to stdout + summary report to stderr.
        Raw JSON saved to experiments/graded_{level}.json.
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

STEPS = 1000
SAMPLE_EVERY = 50
SEEDS = list(range(100, 130))  # test set: seeds 100-129, n=30

LEVELS = [1.0, 0.75, 0.5, 0.25, 0.0]

CONDITIONS = {
    f"graded_{level:.2f}": {
        "metabolism_mode": "graph",
        "metabolism_efficiency_multiplier": level,
    }
    for level in LEVELS
}


def main():
    """Run graded metabolic ablation experiment (5 levels x 30 seeds)."""
    log(f"Digital Life v{digital_life.version()}")
    log(f"Graded ablation: {STEPS} steps, sample every {SAMPLE_EVERY}, "
        f"seeds {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})")
    log(f"Levels: {LEVELS}")
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)

    print_header()
    total_start = time.perf_counter()

    for cond_name, overrides in CONDITIONS.items():
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

        raw_path = safe_path(out_dir, f"graded_{cond_name}.json")
        with open(raw_path, "w") as f:
            json.dump(results, f, indent=2)
        log(f"  Saved: {raw_path}")
        log("")

    total_elapsed = time.perf_counter() - total_start
    log(f"Total experiment time: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
