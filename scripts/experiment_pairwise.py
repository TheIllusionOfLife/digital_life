"""Pairwise criterion-ablation experiment.

Tests interaction effects between pairs of criteria to prove
interdependence (not just independent necessity).

Pairs tested (top criteria by effect size):
  (metabolism, homeostasis), (metabolism, response),
  (reproduction, growth), (boundary, homeostasis),
  (response, homeostasis), (reproduction, evolution)

Usage:
    uv run python scripts/experiment_pairwise.py > experiments/pairwise_data.tsv

Output: TSV data to stdout + summary report to stderr.
        Raw JSON saved to experiments/pairwise_{pair}.json.
"""

import json
import sys
import time
from pathlib import Path

import digital_life

STEPS = 2000
SAMPLE_EVERY = 50
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

PAIRS = [
    ("metabolism", "homeostasis"),
    ("metabolism", "response"),
    ("reproduction", "growth"),
    ("boundary", "homeostasis"),
    ("response", "homeostasis"),
    ("reproduction", "evolution"),
]

CRITERION_TO_FLAG = {
    "metabolism": "enable_metabolism",
    "boundary": "enable_boundary_maintenance",
    "homeostasis": "enable_homeostasis",
    "response": "enable_response",
    "reproduction": "enable_reproduction",
    "evolution": "enable_evolution",
    "growth": "enable_growth",
}


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def make_config(seed: int, overrides: dict) -> str:
    config = json.loads(digital_life.default_config_json())
    config["seed"] = seed
    config.update(TUNED_BASELINE)
    config.update(overrides)
    return json.dumps(config)


def run_single(seed: int, overrides: dict) -> dict:
    config_json = make_config(seed, overrides)
    result_json = digital_life.run_experiment_json(config_json, STEPS, SAMPLE_EVERY)
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


def run_condition(cond_name: str, overrides: dict, out_dir: Path):
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

    raw_path = out_dir / f"pairwise_{cond_name}.json"
    with open(raw_path, "w") as f:
        json.dump(results, f, indent=2)
    log(f"  Saved: {raw_path}")
    log("")


def main():
    log(f"Digital Life v{digital_life.version()}")
    log(f"Pairwise ablation experiment: {STEPS} steps, sample every {SAMPLE_EVERY}, "
        f"seeds {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})")
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)

    print_header()
    total_start = time.perf_counter()

    # Normal baseline (reuse from final if available, otherwise run)
    run_condition("normal", {}, out_dir)

    # Pairwise ablations
    for a, b in PAIRS:
        cond_name = f"no_{a}_no_{b}"
        overrides = {
            CRITERION_TO_FLAG[a]: False,
            CRITERION_TO_FLAG[b]: False,
        }
        run_condition(cond_name, overrides, out_dir)

    total_elapsed = time.perf_counter() - total_start
    log(f"Total experiment time: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
