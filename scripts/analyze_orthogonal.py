"""Orthogonal outcome-measure analysis for criterion-ablation experiments.

Addresses peer-review Concern #1: demonstrate that ablation effects are
detectable with criterion-orthogonal metrics (spatial cohesion, persistence
time), not just alive count.

For each metric, computes Mann-Whitney U (one-sided, normal > ablated),
Holm-Bonferroni correction, and Cliff's delta with bootstrap CI.

Usage:
    uv run python scripts/analyze_orthogonal.py
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

from analyze_results import bootstrap_cliffs_delta_ci, cliffs_delta, holm_bonferroni

EXP_DIR = Path("experiments")
CONDITIONS = [
    "no_metabolism",
    "no_boundary",
    "no_homeostasis",
    "no_response",
    "no_reproduction",
    "no_evolution",
    "no_growth",
]


def load_condition(condition: str) -> list[dict]:
    path = EXP_DIR / f"final_graph_{condition}.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def extract_spatial_cohesion(results: list[dict]) -> np.ndarray:
    """Extract spatial_cohesion_mean from the last sample of each seed."""
    values = []
    for r in results:
        samples = r.get("samples", [])
        if samples:
            values.append(samples[-1]["spatial_cohesion_mean"])
    return np.array(values)


def extract_median_lifespan_per_seed(results: list[dict]) -> np.ndarray:
    """Extract median lifespan per seed (one value per seed)."""
    values = []
    for r in results:
        lifespans = r.get("lifespans", [])
        if lifespans:
            values.append(float(np.median(lifespans)))
        else:
            values.append(0.0)
    return np.array(values)


def analyze_metric(
    name: str,
    normal_vals: np.ndarray,
    condition_vals: dict[str, np.ndarray],
) -> dict:
    """Run Mann-Whitney U + Cliff's delta for one metric across all ablations."""
    comparisons = []
    raw_p_values = []

    for condition in CONDITIONS:
        ablated = condition_vals.get(condition)
        if ablated is None or len(ablated) < 2:
            print(f"  {name}/{condition}: SKIPPED", file=sys.stderr)
            continue

        u_stat, p_value = stats.mannwhitneyu(
            normal_vals, ablated, alternative="greater"
        )
        cliff_d = cliffs_delta(normal_vals, ablated)
        cliff_ci = bootstrap_cliffs_delta_ci(normal_vals, ablated)

        comparisons.append(
            {
                "condition": condition,
                "n_normal": len(normal_vals),
                "n_ablated": len(ablated),
                "normal_median": round(float(np.median(normal_vals)), 4),
                "ablated_median": round(float(np.median(ablated)), 4),
                "U": float(u_stat),
                "p_raw": float(p_value),
                "cliffs_delta": round(cliff_d, 4),
                "cliffs_delta_ci_lo": round(cliff_ci[0], 4),
                "cliffs_delta_ci_hi": round(cliff_ci[1], 4),
            }
        )
        raw_p_values.append(p_value)
        print(
            f"  {name}/{condition}: U={u_stat:.1f}, p={p_value:.6f}, "
            f"cliff={cliff_d:.3f}",
            file=sys.stderr,
        )

    corrected = holm_bonferroni(raw_p_values)
    sig_count = 0
    for comp, p_corr in zip(comparisons, corrected, strict=True):
        comp["p_corrected"] = round(p_corr, 6)
        comp["significant"] = bool(p_corr < 0.05)
        if comp["significant"]:
            sig_count += 1

    return {
        "metric": name,
        "significant_count": sig_count,
        "total_comparisons": len(comparisons),
        "comparisons": comparisons,
    }


def main():
    print("Loading data...", file=sys.stderr)

    normal = load_condition("normal")
    if not normal:
        print("ERROR: no normal baseline data", file=sys.stderr)
        sys.exit(1)

    normal_cohesion = extract_spatial_cohesion(normal)
    normal_lifespan = extract_median_lifespan_per_seed(normal)

    cohesion_vals: dict[str, np.ndarray] = {}
    lifespan_vals: dict[str, np.ndarray] = {}

    for condition in CONDITIONS:
        results = load_condition(condition)
        if results:
            cohesion_vals[condition] = extract_spatial_cohesion(results)
            lifespan_vals[condition] = extract_median_lifespan_per_seed(results)

    print("Analyzing spatial cohesion...", file=sys.stderr)
    cohesion_results = analyze_metric(
        "spatial_cohesion", normal_cohesion, cohesion_vals
    )

    print("Analyzing persistence time (median lifespan)...", file=sys.stderr)
    lifespan_results = analyze_metric(
        "persistence_time", normal_lifespan, lifespan_vals
    )

    output = {
        "analysis": "orthogonal_outcome_measures",
        "description": (
            "Criterion-orthogonal metrics showing ablation effects "
            "beyond alive count: spatial cohesion and persistence time."
        ),
        "metrics": [cohesion_results, lifespan_results],
    }

    out_path = EXP_DIR / "orthogonal_statistics.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults written to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
