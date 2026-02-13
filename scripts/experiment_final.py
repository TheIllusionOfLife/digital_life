"""Final criterion-ablation experiment (2000 steps, n=30, test set).

Runs 8 conditions (normal baseline + 7 criterion ablations) with
seeds 100-129 (test set) and 2000 steps for stronger evolution signal.

Output: TSV data to stdout + summary report to stderr.
        Raw JSON saved to experiments/final_{condition}.json.
"""

import json
import sys
import time
from pathlib import Path

import digital_life

STEPS = 2000
SAMPLE_EVERY = 50
SEEDS = list(range(100, 130))  # test set: seeds 100-129, n=30

# Tuned baseline from parameter sweep (2026-02-12)
TUNED_BASELINE = {
    "boundary_decay_base_rate": 0.001,
    "boundary_repair_rate": 0.05,
    "metabolic_viability_floor": 0.1,
    "crowding_neighbor_threshold": 50.0,
    # New parameters for homeostasis, growth, and resource regeneration
    "homeostasis_decay_rate": 0.01,
    "growth_maturation_steps": 200,
    "growth_immature_metabolic_efficiency": 0.3,
    "resource_regeneration_rate": 0.01,
}

CONDITIONS = {
    "normal": {},
    "no_metabolism": {"enable_metabolism": False},
    "no_boundary": {"enable_boundary_maintenance": False},
    "no_homeostasis": {"enable_homeostasis": False},
    "no_response": {"enable_response": False},
    "no_reproduction": {"enable_reproduction": False},
    "no_evolution": {"enable_evolution": False},
    "no_growth": {"enable_growth": False},
}


def log(msg: str) -> None:
    """Write a message to stderr for progress reporting."""
    print(msg, file=sys.stderr)


def make_config(seed: int, overrides: dict) -> str:
    """Build a JSON config string with tuned baseline, seed, and overrides."""
    config = json.loads(digital_life.default_config_json())
    config["seed"] = seed
    config.update(TUNED_BASELINE)
    config.update(overrides)
    return json.dumps(config)


def run_single(seed: int, overrides: dict) -> dict:
    """Run a single experiment and return parsed results."""
    config_json = make_config(seed, overrides)
    result_json = digital_life.run_experiment_json(config_json, STEPS, SAMPLE_EVERY)
    return json.loads(result_json)


def print_header():
    """Print TSV column header to stdout."""
    cols = [
        "condition", "seed", "step",
        "alive_count", "energy_mean", "waste_mean", "boundary_mean",
        "birth_count", "death_count", "population_size",
        "mean_generation", "mean_genome_drift",
    ]
    print("\t".join(cols))


def print_sample(condition: str, seed: int, s: dict):
    """Print a single sample row as TSV to stdout."""
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
    ]
    print("\t".join(vals))


def main():
    log(f"Digital Life v{digital_life.version()}")
    log(f"Final experiment: {STEPS} steps, sample every {SAMPLE_EVERY}, "
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
            result = run_single(seed, overrides)
            elapsed = time.perf_counter() - t0
            results.append(result)

            for s in result["samples"]:
                print_sample(cond_name, seed, s)

            final = result["final_alive_count"]
            log(f"  seed={seed:3d}  alive={final:4d}  {elapsed:.2f}s")

        cond_elapsed = time.perf_counter() - cond_start
        log(f"  Condition time: {cond_elapsed:.1f}s")

        raw_path = out_dir / f"final_{cond_name}.json"
        with open(raw_path, "w") as f:
            json.dump(results, f, indent=2)
        log(f"  Saved: {raw_path}")
        log("")

    total_elapsed = time.perf_counter() - total_start
    log(f"Total experiment time: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
