"""Focused sensitivity sweep for critical viability thresholds.

Sweeps death boundary threshold, reproduction gate energy, and max age limit.
Outputs JSON with per-setting final alive counts.

Usage:
    uv run python scripts/param_sweep_thresholds.py
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

from experiment_common import run_single

SEEDS = list(range(100, 110))
STEPS = 2000
SAMPLE_EVERY = 50


def main() -> None:
    base_overrides = {"metabolism_mode": "graph"}
    grid = {
        "death_boundary_threshold": [0.05, 0.1, 0.15],
        "reproduction_min_energy": [0.65, 0.7, 0.75],
        "max_organism_age_steps": [15000, 20000, 25000],
    }

    keys = list(grid.keys())
    results: list[dict] = []

    for values in itertools.product(*(grid[k] for k in keys)):
        overrides = dict(base_overrides)
        overrides.update(dict(zip(keys, values, strict=True)))
        final_alive = []
        for seed in SEEDS:
            run = run_single(seed, overrides, steps=STEPS, sample_every=SAMPLE_EVERY)
            final_alive.append(int(run["final_alive_count"]))
        results.append(
            {
                "overrides": {k: v for k, v in zip(keys, values, strict=True)},
                "mean_final_alive": sum(final_alive) / len(final_alive),
                "min_final_alive": min(final_alive),
                "max_final_alive": max(final_alive),
            }
        )

    payload = {
        "experiment": "threshold_sensitivity",
        "seeds": [SEEDS[0], SEEDS[-1]],
        "n": len(SEEDS),
        "results": results,
    }

    out_path = Path("experiments") / "threshold_sensitivity.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
