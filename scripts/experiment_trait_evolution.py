"""Trait evolution experiment: generation-stratified selection differential.

Tracks per-organism physiology across lineage generations to test whether
evolution drives directed trait change (vs. neutral drift). Two conditions:
- normal: evolution enabled
- no_evo: evolution disabled

Seeds 100-114 (n=15), 10,000 steps, organism snapshots at [2000, 5000, 8000, 10000].

Usage:
    uv run python scripts/experiment_trait_evolution.py
"""

import json
import time
from pathlib import Path

import digital_life
from experiment_common import log, make_config

STEPS = 10000
SAMPLE_EVERY = 100
SEEDS = list(range(100, 115))  # n=15
SNAPSHOT_STEPS = [2000, 5000, 8000, 10000]

CONDITIONS = {
    "trait_evo_normal": {},
    "trait_evo_no_evo": {"enable_evolution": False},
}


def run_condition(cond_name: str, overrides: dict, out_dir: Path) -> None:
    log(f"--- Condition: {cond_name} ---")
    snapshot_steps_json = json.dumps(SNAPSHOT_STEPS)
    results = []
    total_start = time.perf_counter()

    for seed in SEEDS:
        config_json = make_config(seed, overrides)
        t0 = time.perf_counter()
        result_json = digital_life.run_niche_experiment_json(
            config_json, STEPS, SAMPLE_EVERY, snapshot_steps_json
        )
        elapsed = time.perf_counter() - t0
        result = json.loads(result_json)
        result["seed"] = seed
        results.append(result)

        snapshots = result.get("organism_snapshots") or []
        n_snapshots = len(snapshots)
        total_orgs = sum(len(f.get("organisms") or []) for f in snapshots)
        log(
            f"  seed={seed:3d}  alive={result['final_alive_count']:4d}  "
            f"snapshots={n_snapshots}  total_orgs={total_orgs}  {elapsed:.2f}s"
        )

    total_elapsed = time.perf_counter() - total_start
    log(f"  Condition time: {total_elapsed:.1f}s")
    log("")

    out_path = out_dir / f"{cond_name}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    log(f"  Saved: {out_path}")


def main() -> None:
    log(f"Digital Life v{digital_life.version()}")
    log(
        "Trait evolution experiment (generation-stratified selection differential)"
    )
    log(f"  Steps: {STEPS}, sample_every: {SAMPLE_EVERY}")
    log(f"  Seeds: {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})")
    log(f"  Snapshot steps: {SNAPSHOT_STEPS}")
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)

    for cond_name, overrides in CONDITIONS.items():
        run_condition(cond_name, overrides, out_dir)

    log("Trait evolution experiment complete.")


if __name__ == "__main__":
    main()
