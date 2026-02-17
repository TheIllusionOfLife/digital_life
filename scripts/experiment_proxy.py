"""Proxy control comparison experiment.

Runs 3 metabolism conditions on the same seeds to demonstrate that
graph metabolism provides qualitative advantage over simpler proxies.

Conditions:
  1. graph   - Full graph-based multi-step metabolism
  2. toy     - Intermediate single-step with waste dynamics
  3. counter - Minimal single-step, no waste production

Usage:
    uv run python scripts/experiment_proxy.py > experiments/proxy_data.tsv

Output: TSV data to stdout + summary report to stderr.
        Raw JSON saved to experiments/proxy_{condition}.json.
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

STEPS = 2000
SAMPLE_EVERY = 50
SEEDS = list(range(100, 130))  # test set: seeds 100-129, n=30

CONDITIONS = {
    "graph": {"metabolism_mode": "graph"},
    "toy": {"metabolism_mode": "toy"},
    "counter": {"metabolism_mode": "counter"},
}


def main():
    """Run proxy control comparison experiment across 3 metabolism modes."""
    log(f"Digital Life v{digital_life.version()}")
    log(f"Proxy control experiment: {STEPS} steps, sample every {SAMPLE_EVERY}, "
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

        raw_path = safe_path(out_dir, f"proxy_{cond_name}.json")
        with open(raw_path, "w") as f:
            json.dump(results, f, indent=2)
        log(f"  Saved: {raw_path}")
        log("")

    total_elapsed = time.perf_counter() - total_start
    log(f"Total experiment time: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
