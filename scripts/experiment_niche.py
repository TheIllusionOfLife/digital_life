"""Ecological niche experiment with per-organism snapshots.

Runs 10,000-step simulations under normal conditions and collects
per-organism trait snapshots at early (2000), mid (5000), and late (9000)
steps for organism-level phenotype persistence analysis.

Usage:
    uv run python scripts/experiment_niche.py

Output: experiments/niche_normal.json (per-seed results with organism snapshots).
"""

import json
import time
from pathlib import Path

import digital_life

from experiment_common import TUNED_BASELINE, log, make_config

STEPS = 5000
SAMPLE_EVERY = 100
SEEDS = list(range(100, 110))  # test set: seeds 100-109, n=10
# Windows spaced ~200 steps apart (near median lifespan ~245 steps)
# to ensure sufficient organism overlap for persistence analysis
SNAPSHOT_STEPS = [2000, 2200, 4500, 4700]


def main():
    """Run niche experiment: 10k steps with per-organism snapshots."""
    log(f"Digital Life v{digital_life.version()}")
    log("Ecological niche experiment (per-organism snapshots)")
    log(f"  Steps: {STEPS}, sample_every: {SAMPLE_EVERY}")
    log(f"  Seeds: {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})")
    log(f"  Snapshot steps: {SNAPSHOT_STEPS}")
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)

    snapshot_steps_json = json.dumps(SNAPSHOT_STEPS)
    results = []
    total_start = time.perf_counter()

    for seed in SEEDS:
        config_json = make_config(seed, {})
        t0 = time.perf_counter()
        result_json = digital_life.run_niche_experiment_json(
            config_json, STEPS, SAMPLE_EVERY, snapshot_steps_json
        )
        elapsed = time.perf_counter() - t0
        result = json.loads(result_json)
        result["seed"] = seed
        results.append(result)

        n_snapshots = len(result.get("organism_snapshots", []))
        total_orgs = sum(
            len(f["organisms"]) for f in result.get("organism_snapshots", [])
        )
        log(
            f"  seed={seed:3d}  alive={result['final_alive_count']:4d}  "
            f"snapshots={n_snapshots}  total_orgs={total_orgs}  {elapsed:.2f}s"
        )

    total_elapsed = time.perf_counter() - total_start
    log(f"\nTotal experiment time: {total_elapsed:.1f}s")

    out_path = out_dir / "niche_normal.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    log(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
