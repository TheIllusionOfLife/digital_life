"""Sham ablation control experiment.

Compares enable_sham_process=true vs false to validate that ablation
effects are functional, not computational artifacts.

Usage:
    uv run python scripts/experiment_sham.py > experiments/sham_data.tsv

Output: TSV data to stdout + summary report to stderr.
        Raw JSON saved to experiments/sham_{condition}.json.
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

CONDITIONS = {
    "sham_on": {
        "metabolism_mode": "graph",
        "enable_sham_process": True,
    },
    "sham_off": {
        "metabolism_mode": "graph",
        "enable_sham_process": False,
    },
}


def main():
    """Run sham ablation control experiment (2 conditions x 30 seeds)."""
    log(f"Digital Life v{digital_life.version()}")
    log(f"Sham control: {STEPS} steps, sample every {SAMPLE_EVERY}, "
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
            result = run_single(seed, overrides, steps=STEPS, sample_every=SAMPLE_EVERY)
            elapsed = time.perf_counter() - t0
            results.append(result)

            for s in result["samples"]:
                print_sample(cond_name, seed, s)

            final = result["final_alive_count"]
            log(f"  seed={seed:3d}  alive={final:4d}  {elapsed:.2f}s")

        cond_elapsed = time.perf_counter() - cond_start
        log(f"  Condition time: {cond_elapsed:.1f}s")

        raw_path = safe_path(out_dir, f"sham_{cond_name}.json")
        with open(raw_path, "w") as f:
            json.dump(results, f, indent=2)
        log(f"  Saved: {raw_path}")
        log("")

    total_elapsed = time.perf_counter() - total_start
    log(f"Total experiment time: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
