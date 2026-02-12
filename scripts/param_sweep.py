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


def run(overrides: dict) -> dict:
    config = json.loads(digital_life.default_config_json())
    config["seed"] = SEED
    config.update(overrides)
    result = json.loads(
        digital_life.run_experiment_json(json.dumps(config), STEPS, SAMPLE_EVERY)
    )
    return result


def main():
    log = lambda msg: print(msg, file=sys.stderr)
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

    results = []
    for i, combo in enumerate(combos):
        overrides = dict(zip(keys, combo))
        t0 = time.perf_counter()
        result = run(overrides)
        elapsed = time.perf_counter() - t0

        samples = result["samples"]
        final = samples[-1]
        alive_trajectory = [s["alive_count"] for s in samples]
        peak_alive = max(alive_trajectory)
        total_births = sum(s["birth_count"] for s in samples)
        total_deaths = sum(s["death_count"] for s in samples)

        trajectory_str = "→".join(str(a) for a in alive_trajectory)

        row = [str(v) for v in combo] + [
            str(final["alive_count"]),
            str(peak_alive),
            f"{final['energy_mean']:.4f}",
            f"{final['boundary_mean']:.4f}",
            f"{final['waste_mean']:.4f}",
            str(total_births),
            str(total_deaths),
            trajectory_str,
        ]
        print("\t".join(row))
        results.append((overrides, result))

        if (i + 1) % 10 == 0:
            log(f"  {i+1}/{len(combos)} done ({elapsed:.2f}s/run)")

    # Find best configs
    log("\n" + "=" * 60)
    log("TOP 10 CONFIGURATIONS (by final alive count, then peak)")
    log("=" * 60)

    scored = []
    for overrides, result in results:
        samples = result["samples"]
        final_alive = result["final_alive_count"]
        peak_alive = max(s["alive_count"] for s in samples)
        total_births = sum(s["birth_count"] for s in samples)
        final_energy = samples[-1]["energy_mean"]
        final_boundary = samples[-1]["boundary_mean"]
        scored.append((final_alive, peak_alive, total_births, final_energy, final_boundary, overrides))

    scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    for rank, (alive, peak, births, energy, boundary, params) in enumerate(scored[:10], 1):
        log(f"\n#{rank}: alive={alive}, peak={peak}, births={births}, "
            f"energy={energy:.3f}, boundary={boundary:.3f}")
        for k, v in params.items():
            log(f"    {k}: {v}")


if __name__ == "__main__":
    main()
