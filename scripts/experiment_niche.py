"""Ecological niche experiment with per-organism snapshots.

Default run (recommended for routine robustness): 5,000 steps over n=30 seeds.
Optional long-horizon sensitivity mode: 10,000 steps over n=30 seeds.

Usage:
    uv run python scripts/experiment_niche.py
    uv run python scripts/experiment_niche.py --long-horizon

Output:
    - default: experiments/niche_normal.json
    - --long-horizon: experiments/niche_normal_long.json
"""

import argparse
import json
import time
from pathlib import Path

import digital_life
from experiment_common import log, make_config

STEPS = 5000
LONG_HORIZON_STEPS = 10000
SAMPLE_EVERY = 100
SEEDS = list(range(100, 130))  # test set: seeds 100-129, n=30
# Windows spaced ~200 steps apart (near median lifespan ~245 steps)
# to ensure sufficient organism overlap for persistence analysis
SNAPSHOT_STEPS = [2000, 2200, 4500, 4700]
LONG_HORIZON_SNAPSHOT_STEPS = [2000, 2200, 4500, 4700, 7000, 7200, 9500, 9700]


def parse_args():
    """Parse command-line options."""
    parser = argparse.ArgumentParser(
        description="Run ecological niche experiment with per-organism snapshots."
    )
    parser.add_argument(
        "--long-horizon",
        action="store_true",
        help="Run optional long-horizon sensitivity mode (10,000 steps).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path. Defaults to mode-specific experiments/*.json file.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    steps = LONG_HORIZON_STEPS if args.long_horizon else STEPS
    default_name = "niche_normal_long.json" if args.long_horizon else "niche_normal.json"
    snapshot_steps = LONG_HORIZON_SNAPSHOT_STEPS if args.long_horizon else SNAPSHOT_STEPS

    log(f"Digital Life v{digital_life.version()}")
    mode = "long-horizon sensitivity" if args.long_horizon else "standard robustness"
    log(f"Ecological niche experiment (per-organism snapshots, {mode})")
    log(f"  Steps: {steps}, sample_every: {SAMPLE_EVERY}")
    log(f"  Seeds: {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})")
    log(f"  Snapshot steps: {snapshot_steps}")
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)

    snapshot_steps_json = json.dumps(snapshot_steps)
    results = []
    total_start = time.perf_counter()

    for seed in SEEDS:
        config_json = make_config(seed, {})
        t0 = time.perf_counter()
        result_json = digital_life.run_niche_experiment_json(
            config_json, steps, SAMPLE_EVERY, snapshot_steps_json
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

    out_path = args.output if args.output is not None else out_dir / default_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    log(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
