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

from experiment_common import log, run_single

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
    failures: list[dict] = []

    for values in itertools.product(*(grid[k] for k in keys)):
        overrides = dict(base_overrides)
        overrides.update(dict(zip(keys, values, strict=True)))
        final_alive = []
        for seed in SEEDS:
            try:
                run = run_single(seed, overrides, steps=STEPS, sample_every=SAMPLE_EVERY)
            except Exception as exc:
                failures.append(
                    {
                        "seed": seed,
                        "overrides": {k: overrides[k] for k in keys},
                        "error": str(exc),
                    }
                )
                log(f"param sweep failed for seed={seed} overrides={overrides}: {exc}")
                continue
            final_alive.append(int(run["final_alive_count"]))
        if not final_alive:
            log(f"param sweep skipped setting with no successful seeds: {overrides}")
            continue
        results.append(
            {
                "overrides": {k: v for k, v in zip(keys, values, strict=True)},
                "n_success": len(final_alive),
                "mean_final_alive": sum(final_alive) / len(final_alive),
                "min_final_alive": min(final_alive),
                "max_final_alive": max(final_alive),
            }
        )

    payload = {
        "experiment": "threshold_sensitivity",
        "seeds": SEEDS,
        "n": len(SEEDS),
        "failures": failures,
        "results": results,
    }

    out_path = Path("experiments") / "threshold_sensitivity.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload_json = json.dumps(payload, indent=2)
    out_path.write_text(payload_json)
    print(payload_json)


if __name__ == "__main__":
    main()
