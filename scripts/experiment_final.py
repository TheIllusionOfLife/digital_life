"""Final criterion-ablation experiment (2000 steps, n=30, test set).

Runs 8 conditions (normal baseline + 7 criterion ablations) with
seeds 100-129 (test set) and 2000 steps for stronger evolution signal.

Usage:
    uv run python scripts/experiment_final.py > experiments/final_data.tsv

Output: TSV data to stdout + summary report to stderr.
        Raw JSON saved to experiments/final_graph_{condition}.json.
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
)

STEPS = 2000
SAMPLE_EVERY = 50
SEEDS = list(range(100, 130))  # test set: seeds 100-129, n=30

GRAPH_OVERRIDES = {"metabolism_mode": "graph"}

CONDITIONS = {
    "normal": {},
    "no_metabolism": {"enable_metabolism": False},
    "no_boundary": {"enable_boundary_maintenance": False},
    "no_homeostasis": {"enable_homeostasis": False},
    "no_response": {"enable_response": False},
    "no_reproduction": {"enable_reproduction": False},
    "no_evolution": {"enable_evolution": False},
    "no_growth": {"enable_growth": False},
}


def main():
    """Run final criterion-ablation experiment (8 conditions x 30 seeds)."""
    log(f"Digital Life v{digital_life.version()}")
    log(f"Final experiment: {STEPS} steps, sample every {SAMPLE_EVERY}, "
        f"seeds {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})")
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
            result = run_single(seed, {**GRAPH_OVERRIDES, **overrides}, steps=STEPS, sample_every=SAMPLE_EVERY)
            elapsed = time.perf_counter() - t0
            results.append(result)

            for s in result["samples"]:
                print_sample(cond_name, seed, s)

            final = result["final_alive_count"]
            log(f"  seed={seed:3d}  alive={final:4d}  {elapsed:.2f}s")

        cond_elapsed = time.perf_counter() - cond_start
        log(f"  Condition time: {cond_elapsed:.1f}s")

        raw_path = out_dir / f"final_graph_{cond_name}.json"
        with open(raw_path, "w") as f:
            json.dump(results, f, indent=2)
        log(f"  Saved: {raw_path}")
        log("")

    total_elapsed = time.perf_counter() - total_start
    log(f"Total experiment time: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
