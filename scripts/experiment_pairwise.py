"""Pairwise criterion-ablation experiment with Graph metabolism.

Tests interaction effects between pairs of criteria to prove
interdependence (not just independent necessity).  Uses Graph metabolism
for consistency with the main ablation table (Table 3).

Pairs tested (top criteria by effect size):
  (metabolism, homeostasis), (metabolism, response),
  (reproduction, growth), (boundary, homeostasis),
  (response, homeostasis), (reproduction, evolution)

Usage:
    uv run python scripts/experiment_pairwise.py > experiments/pairwise_graph_data.tsv

Output: TSV data to stdout + summary report to stderr.
        Raw JSON saved to experiments/pairwise_graph_{pair}.json.
"""

import json
import time
from pathlib import Path

import digital_life

from experiment_common import (
    CRITERION_TO_FLAG,
    PAIRS,
    log,
    print_header,
    print_sample,
    run_single,
)

STEPS = 2000
SAMPLE_EVERY = 50
SEEDS = list(range(100, 130))  # test set: seeds 100-129, n=30

GRAPH_OVERRIDES = {"metabolism_mode": "graph"}


def run_condition(cond_name: str, overrides: dict, out_dir: Path):
    """Run all seeds for a single condition and save results to JSON."""
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

    raw_path = out_dir / f"pairwise_graph_{cond_name}.json"
    with open(raw_path, "w") as f:
        json.dump(results, f, indent=2)
    log(f"  Saved: {raw_path}")
    log("")


def main():
    """Run pairwise criterion-ablation experiment for 6 criterion pairs."""
    log(f"Digital Life v{digital_life.version()}")
    log(f"Pairwise ablation experiment: {STEPS} steps, sample every {SAMPLE_EVERY}, "
        f"seeds {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})")
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)

    print_header()
    total_start = time.perf_counter()

    # Normal baseline (always re-run with pairwise settings for consistency)
    run_condition("normal", {}, out_dir)

    # Pairwise ablations
    for a, b in PAIRS:
        cond_name = f"no_{a}_no_{b}"
        overrides = {
            CRITERION_TO_FLAG[a]: False,
            CRITERION_TO_FLAG[b]: False,
        }
        run_condition(cond_name, overrides, out_dir)

    total_elapsed = time.perf_counter() - total_start
    log(f"Total experiment time: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
