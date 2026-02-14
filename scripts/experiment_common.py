"""Shared utilities for experiment scripts.

Provides common constants, configuration helpers, logging, and TSV output
functions used across experiment_final.py, experiment_proxy.py,
experiment_pairwise.py, and experiment_evolution.py.
"""

import json
import sys
from pathlib import Path

import digital_life

# Tuned baseline parameters from parameter sweep (2026-02-12)
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

# Criterion name to config flag mapping
CRITERION_TO_FLAG = {
    "metabolism": "enable_metabolism",
    "boundary": "enable_boundary_maintenance",
    "homeostasis": "enable_homeostasis",
    "response": "enable_response",
    "reproduction": "enable_reproduction",
    "evolution": "enable_evolution",
    "growth": "enable_growth",
}

# Pairwise ablation pairs (top criteria by effect size)
PAIRS = [
    ("metabolism", "homeostasis"),
    ("metabolism", "response"),
    ("reproduction", "growth"),
    ("boundary", "homeostasis"),
    ("response", "homeostasis"),
    ("reproduction", "evolution"),
]

# TSV column headers for experiment output
TSV_COLUMNS = [
    "condition", "seed", "step",
    "alive_count", "energy_mean", "waste_mean", "boundary_mean",
    "birth_count", "death_count", "population_size",
    "mean_generation", "mean_genome_drift",
    "energy_std", "waste_std", "boundary_std",
    "mean_age", "genome_diversity", "max_generation",
]


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


def run_single(seed: int, overrides: dict,
               steps: int = 2000, sample_every: int = 50) -> dict:
    """Run a single experiment and return parsed results."""
    config_json = make_config(seed, overrides)
    result_json = digital_life.run_experiment_json(config_json, steps, sample_every)
    return json.loads(result_json)


def print_header() -> None:
    """Print TSV column header to stdout."""
    print("\t".join(TSV_COLUMNS))


def print_sample(condition: str, seed: int, s: dict) -> None:
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
        f"{s.get('energy_std', 0):.4f}",
        f"{s.get('waste_std', 0):.4f}",
        f"{s.get('boundary_std', 0):.4f}",
        f"{s.get('mean_age', 0):.1f}",
        f"{s.get('genome_diversity', 0):.4f}",
        str(s.get("max_generation", 0)),
    ]
    print("\t".join(vals))


def experiment_output_dir() -> Path:
    """Return the experiments output directory, creating it if needed."""
    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)
    return out_dir


def load_json(path: Path) -> list[dict]:
    """Load a JSON file and return its contents, or empty list if missing."""
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def extract_final_alive(results: list[dict]) -> list[int]:
    """Extract final_alive_count from each seed's result."""
    return [r["final_alive_count"] for r in results if "samples" in r]
