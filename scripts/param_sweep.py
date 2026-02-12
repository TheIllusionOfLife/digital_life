"""Quick parameter sweep to find stable organism configurations.

Sweeps key parameters affecting organism survival:
  - boundary_decay_base_rate: how fast boundary decays naturally
  - boundary_repair_rate: how fast energy repairs boundary
  - metabolic_viability_floor: energy threshold below which boundary decays faster
  - crowding_neighbor_threshold: when crowding penalty kicks in

Each combo runs 500 steps on seed=0, reports final alive count and trajectory shape.
"""

import itertools
import json
import sys
import time
from dataclasses import dataclass

import digital_life

STEPS = 500
SAMPLE_EVERY = 50
SEED = 0

# Parameter grid (coarse sweep)
GRID = {
    "boundary_decay_base_rate": [0.0005, 0.001, 0.003],
    "boundary_repair_rate": [0.01, 0.03, 0.05],
    "metabolic_viability_floor": [0.1, 0.2, 0.4],
    "crowding_neighbor_threshold": [8.0, 20.0, 50.0],
}


@dataclass
class ComboMetrics:
    """Pre-computed metrics for a single parameter combination."""

    overrides: dict
    final_alive: int
    peak_alive: int
    total_births: int
    total_deaths: int
    final_energy: float
    final_boundary: float
    final_waste: float
    trajectory: list[int]


def log(msg: str) -> None:
    """Write a message to stderr for progress reporting."""
    print(msg, file=sys.stderr)


def run(overrides: dict) -> dict:
    """Run a single sweep experiment and return parsed results."""
    config = json.loads(digital_life.default_config_json())
    config["seed"] = SEED
    config.update(overrides)
    return json.loads(
        digital_life.run_experiment_json(json.dumps(config), STEPS, SAMPLE_EVERY)
    )


def extract_metrics(overrides: dict, result: dict) -> ComboMetrics | None:
    """Extract metrics from experiment result. Returns None if no samples."""
    samples = result.get("samples", [])
    if not samples:
        return None

    final = samples[-1]
    trajectory = [s["alive_count"] for s in samples]

    return ComboMetrics(
        overrides=overrides,
        final_alive=result["final_alive_count"],
        peak_alive=max(trajectory),
        total_births=sum(s["birth_count"] for s in samples),
        total_deaths=sum(s["death_count"] for s in samples),
        final_energy=final["energy_mean"],
        final_boundary=final["boundary_mean"],
        final_waste=final["waste_mean"],
        trajectory=trajectory,
    )


def main():
    log(f"Parameter sweep: {STEPS} steps, seed={SEED}")

    keys = list(GRID.keys())
    values = list(GRID.values())
    combos = list(itertools.product(*values))
    log(f"Total combinations: {len(combos)}")
    log("")

    # Header
    print("\t".join(keys + [
        "final_alive", "peak_alive", "final_energy", "final_boundary",
        "final_waste", "total_births", "total_deaths", "trajectory",
    ]))

    all_metrics: list[ComboMetrics] = []
    for i, combo in enumerate(combos):
        overrides = dict(zip(keys, combo))
        t0 = time.perf_counter()
        result = run(overrides)
        elapsed = time.perf_counter() - t0

        metrics = extract_metrics(overrides, result)
        if metrics is None:
            continue
        all_metrics.append(metrics)

        trajectory_str = "→".join(str(a) for a in metrics.trajectory)
        row = [str(v) for v in combo] + [
            str(metrics.final_alive),
            str(metrics.peak_alive),
            f"{metrics.final_energy:.4f}",
            f"{metrics.final_boundary:.4f}",
            f"{metrics.final_waste:.4f}",
            str(metrics.total_births),
            str(metrics.total_deaths),
            trajectory_str,
        ]
        print("\t".join(row))

        if (i + 1) % 10 == 0:
            log(f"  {i+1}/{len(combos)} done ({elapsed:.2f}s/run)")

    # Find best configs
    log("\n" + "=" * 60)
    log("TOP 10 CONFIGURATIONS (by final alive count, then peak)")
    log("=" * 60)

    all_metrics.sort(
        key=lambda m: (m.final_alive, m.peak_alive, m.total_births),
        reverse=True,
    )
    for rank, m in enumerate(all_metrics[:10], 1):
        log(f"\n#{rank}: alive={m.final_alive}, peak={m.peak_alive}, births={m.total_births}, "
            f"energy={m.final_energy:.3f}, boundary={m.final_boundary:.3f}")
        for k, v in m.overrides.items():
            log(f"    {k}: {v}")


if __name__ == "__main__":
    main()
