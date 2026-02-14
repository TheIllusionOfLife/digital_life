"""Extended evolution experiment.

Two sub-experiments to demonstrate evolution's contribution:
  1. Long run: 10,000 steps (vs current 2,000), normal vs no_evolution
  2. Environmental shift: 5,000 steps, resource rate halved at step 2,500,
     normal vs no_evolution on post-shift recovery

Usage:
    uv run python scripts/experiment_evolution.py > experiments/evolution_data.tsv

Output: TSV data to stdout + summary report to stderr.
        Raw JSON saved to experiments/evolution_{condition}.json.
"""

import json
import sys
import time
from pathlib import Path

import digital_life

SAMPLE_EVERY = 100
SEEDS = list(range(100, 130))  # test set: seeds 100-129, n=30

TUNED_BASELINE = {
    "boundary_decay_base_rate": 0.001,
    "boundary_repair_rate": 0.05,
    "metabolic_viability_floor": 0.1,
    "crowding_neighbor_threshold": 50.0,
    "homeostasis_decay_rate": 0.01,
    "growth_maturation_steps": 200,
    "growth_immature_metabolic_efficiency": 0.3,
    "resource_regeneration_rate": 0.01,
}

# Sub-experiment 1: Long run (10,000 steps)
LONG_STEPS = 10000
LONG_CONDITIONS = {
    "long_normal": {},
    "long_no_evolution": {"enable_evolution": False},
}

# Sub-experiment 2: Environmental shift (5,000 steps, shift at 2,500)
SHIFT_STEPS = 5000
SHIFT_STEP = 2500
SHIFT_RESOURCE_RATE = 0.005  # halved from 0.01
SHIFT_CONDITIONS = {
    "shift_normal": {
        "environment_shift_step": SHIFT_STEP,
        "environment_shift_resource_rate": SHIFT_RESOURCE_RATE,
    },
    "shift_no_evolution": {
        "enable_evolution": False,
        "environment_shift_step": SHIFT_STEP,
        "environment_shift_resource_rate": SHIFT_RESOURCE_RATE,
    },
}


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def make_config(seed: int, overrides: dict) -> str:
    config = json.loads(digital_life.default_config_json())
    config["seed"] = seed
    config.update(TUNED_BASELINE)
    config.update(overrides)
    return json.dumps(config)


def run_single(seed: int, overrides: dict, steps: int, sample_every: int) -> dict:
    config_json = make_config(seed, overrides)
    result_json = digital_life.run_experiment_json(config_json, steps, sample_every)
    return json.loads(result_json)


def print_header():
    cols = [
        "condition", "seed", "step",
        "alive_count", "energy_mean", "waste_mean", "boundary_mean",
        "birth_count", "death_count", "population_size",
        "mean_generation", "mean_genome_drift",
        "energy_std", "waste_std", "boundary_std",
        "mean_age", "genome_diversity", "max_generation",
    ]
    print("\t".join(cols))


def print_sample(condition: str, seed: int, s: dict):
    vals = [
        condition, str(seed), str(s["step"]),
        str(s["alive_count"]),
        f"{s['energy_mean']:.4f}",
        f"{s['waste_mean']:.4f}",
        f"{s['boundary_mean']:.4f}",
        str(s["birth_count"]),
        str(s["death_count"]),
        str(s["population_size"]),
        f"{s['mean_generation']:.2f}",
        f"{s['mean_genome_drift']:.4f}",
        f"{s.get('energy_std', 0):.4f}",
        f"{s.get('waste_std', 0):.4f}",
        f"{s.get('boundary_std', 0):.4f}",
        f"{s.get('mean_age', 0):.1f}",
        f"{s.get('genome_diversity', 0):.4f}",
        str(s.get("max_generation", 0)),
    ]
    print("\t".join(vals))


def run_condition(cond_name: str, overrides: dict, steps: int,
                  sample_every: int, out_dir: Path):
    log(f"--- Condition: {cond_name} ({steps} steps) ---")
    results = []
    cond_start = time.perf_counter()

    for seed in SEEDS:
        t0 = time.perf_counter()
        result = run_single(seed, overrides, steps, sample_every)
        elapsed = time.perf_counter() - t0
        results.append(result)

        for s in result["samples"]:
            print_sample(cond_name, seed, s)

        final = result["final_alive_count"]
        log(f"  seed={seed:3d}  alive={final:4d}  {elapsed:.2f}s")

    cond_elapsed = time.perf_counter() - cond_start
    log(f"  Condition time: {cond_elapsed:.1f}s")

    raw_path = out_dir / f"evolution_{cond_name}.json"
    with open(raw_path, "w") as f:
        json.dump(results, f, indent=2)
    log(f"  Saved: {raw_path}")
    log("")


def main():
    log(f"Digital Life v{digital_life.version()}")
    log(f"Evolution strengthening experiment")
    log(f"  Long run: {LONG_STEPS} steps, seeds {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})")
    log(f"  Shift run: {SHIFT_STEPS} steps, shift at {SHIFT_STEP}")
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)

    print_header()
    total_start = time.perf_counter()

    # Sub-experiment 1: Long run
    for cond_name, overrides in LONG_CONDITIONS.items():
        run_condition(cond_name, overrides, LONG_STEPS, SAMPLE_EVERY, out_dir)

    # Sub-experiment 2: Environmental shift
    for cond_name, overrides in SHIFT_CONDITIONS.items():
        run_condition(cond_name, overrides, SHIFT_STEPS, SAMPLE_EVERY, out_dir)

    total_elapsed = time.perf_counter() - total_start
    log(f"Total experiment time: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
