"""Environment regime shift robustness experiment.

Runs full 8-condition criterion-ablation under multiple environment regimes
with GraphMetabolism mode to test external validity.

Usage:
    uv run python scripts/experiment_regimes.py
"""

import json
import time
from pathlib import Path

import digital_life
from experiment_utils import CONDITIONS, log, run_single, safe_path

STEPS = 2000
SAMPLE_EVERY = 50
SEEDS = list(range(100, 130))  # test set: seeds 100-129, n=30

GRAPH_OVERRIDES = {"metabolism_mode": "graph"}

REGIMES = {
    "default": {},
    "sparse": {"resource_regeneration_rate": 0.005, "world_size": 150.0},
    "crowded": {"num_organisms": 80, "agents_per_organism": 30, "world_size": 80.0},
    "scarce": {"resource_regeneration_rate": 0.003},
}


def main():
    log(f"Digital Life v{digital_life.version()}")
    log(f"Regime shift experiment: {STEPS} steps, seeds {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})")
    log(f"Regimes: {list(REGIMES.keys())}")
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)

    total_start = time.perf_counter()

    for regime_name, regime_overrides in REGIMES.items():
        log(f"=== Regime: {regime_name} ===")
        regime_start = time.perf_counter()

        for cond_name, cond_overrides in CONDITIONS.items():
            log(f"  --- {cond_name} ---")
            results = []

            for seed in SEEDS:
                t0 = time.perf_counter()
                result = run_single(
                    seed, STEPS, SAMPLE_EVERY, GRAPH_OVERRIDES, regime_overrides, cond_overrides
                )
                elapsed = time.perf_counter() - t0
                results.append(result)
                log(f"    seed={seed:3d}  alive={result['final_alive_count']:4d}  {elapsed:.2f}s")

            raw_path = safe_path(out_dir, f"regime_{regime_name}_{cond_name}.json")
            with open(raw_path, "w") as f:
                json.dump(results, f, indent=2)

        regime_elapsed = time.perf_counter() - regime_start
        log(f"  Regime time: {regime_elapsed:.1f}s")
        log("")

    total_elapsed = time.perf_counter() - total_start
    log(f"Total experiment time: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
