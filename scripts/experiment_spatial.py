"""Spatial cohesion experiment.

Compares spatial_cohesion_mean between normal and no-boundary conditions
to validate that boundary maintenance keeps agents spatially coherent.

Usage:
    uv run python scripts/experiment_spatial.py > experiments/spatial_data.tsv

Output: TSV data to stdout + summary to stderr.
        Raw JSON saved to experiments/spatial_{condition}.json.
"""

import json
import time
from pathlib import Path

import digital_life

from experiment_common import (
    log,
    run_single,
)

STEPS = 2000
SAMPLE_EVERY = 50
SEEDS = list(range(100, 130))  # test set: seeds 100-129, n=30

GRAPH_OVERRIDES = {"metabolism_mode": "graph"}

CONDITIONS = {
    "normal": {**GRAPH_OVERRIDES},
    "no_boundary": {**GRAPH_OVERRIDES, "enable_boundary_maintenance": False},
}

TSV_COLUMNS = [
    "condition", "seed", "step",
    "alive_count", "boundary_mean", "spatial_cohesion_mean",
]


def main():
    """Run spatial cohesion experiment (2 conditions x 30 seeds)."""
    log(f"Digital Life v{digital_life.version()}")
    log(f"Spatial cohesion: {STEPS} steps, sample every {SAMPLE_EVERY}, "
        f"seeds {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})")
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)

    print("\t".join(TSV_COLUMNS))
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
                vals = [
                    cond_name, str(seed), str(s["step"]),
                    str(s["alive_count"]),
                    f"{s['boundary_mean']:.4f}",
                    f"{s.get('spatial_cohesion_mean', 0):.4f}",
                ]
                print("\t".join(vals))

            final = result["final_alive_count"]
            log(f"  seed={seed:3d}  alive={final:4d}  {elapsed:.2f}s")

        cond_elapsed = time.perf_counter() - cond_start
        log(f"  Condition time: {cond_elapsed:.1f}s")

        raw_path = out_dir / f"spatial_{cond_name}.json"
        with open(raw_path, "w") as f:
            json.dump(results, f, indent=2)
        log(f"  Saved: {raw_path}")
        log("")

    total_elapsed = time.perf_counter() - total_start
    log(f"Total experiment time: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
