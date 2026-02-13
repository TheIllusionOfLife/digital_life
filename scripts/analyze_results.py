"""Statistical analysis for criterion-ablation experiments.

Computes Mann-Whitney U tests, Cohen's d effect sizes, and
Holm-Bonferroni corrected p-values for each ablation condition
vs the normal baseline.

Usage:
    uv run python scripts/analyze_results.py experiments/final > experiments/final_statistics.json

The prefix argument (e.g. experiments/final) is used to find JSON files
named {prefix}_{condition}.json for each condition.
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

CONDITIONS = [
    "no_metabolism",
    "no_boundary",
    "no_homeostasis",
    "no_response",
    "no_reproduction",
    "no_evolution",
    "no_growth",
]


def load_condition(prefix: str, condition: str) -> list[dict]:
    """Load experiment results for a condition from JSON file."""
    path = Path(f"{prefix}_{condition}.json")
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def extract_final_alive(results: list[dict]) -> np.ndarray:
    """Extract final_alive_count from each seed's result."""
    return np.array([r["final_alive_count"] for r in results if "samples" in r])


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Compute Cohen's d effect size (pooled SD)."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return 0.0
    var_a = np.var(a, ddof=1)
    var_b = np.var(b, ddof=1)
    pooled_sd = np.sqrt(((na - 1) * var_a + (nb - 1) * var_b) / (na + nb - 2))
    if pooled_sd == 0:
        return 0.0
    return float((np.mean(a) - np.mean(b)) / pooled_sd)


def holm_bonferroni(p_values: list[float]) -> list[float]:
    """Apply Holm-Bonferroni correction to a list of p-values.

    Returns corrected p-values in the original order.
    """
    n = len(p_values)
    if n == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    corrected = [0.0] * n
    cumulative_max = 0.0
    for rank, (orig_idx, p) in enumerate(indexed):
        adjusted = p * (n - rank)
        cumulative_max = max(cumulative_max, adjusted)
        corrected[orig_idx] = min(cumulative_max, 1.0)
    return corrected


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/analyze_results.py <prefix>", file=sys.stderr)
        print("  e.g. python scripts/analyze_results.py experiments/final", file=sys.stderr)
        sys.exit(1)

    prefix = sys.argv[1]
    alpha = 0.05

    # Load normal baseline
    normal_results = load_condition(prefix, "normal")
    if not normal_results:
        print("ERROR: no normal baseline results found", file=sys.stderr)
        sys.exit(1)
    normal_alive = extract_final_alive(normal_results)
    n_normal = len(normal_alive)
    print(f"Normal baseline: n={n_normal}, mean={np.mean(normal_alive):.1f}", file=sys.stderr)

    # Compute stats for each ablation
    comparisons = []
    raw_p_values = []

    for condition in CONDITIONS:
        results = load_condition(prefix, condition)
        if not results:
            print(f"  {condition}: SKIPPED (no data)", file=sys.stderr)
            continue

        ablated_alive = extract_final_alive(results)
        n_ablated = len(ablated_alive)

        if n_ablated < 2:
            print(f"  {condition}: SKIPPED (n={n_ablated} < 2)", file=sys.stderr)
            continue

        u_stat, p_value = stats.mannwhitneyu(
            normal_alive, ablated_alive, alternative="greater"
        )
        d = cohens_d(normal_alive, ablated_alive)

        comparisons.append({
            "condition": condition,
            "n_normal": n_normal,
            "n_ablated": n_ablated,
            "normal_mean": float(np.mean(normal_alive)),
            "ablation_mean": float(np.mean(ablated_alive)),
            "U": float(u_stat),
            "p_raw": float(p_value),
            "cohens_d": round(d, 4),
        })
        raw_p_values.append(p_value)
        print(
            f"  {condition}: U={u_stat:.1f}, p={p_value:.6f}, d={d:.3f}, "
            f"normal={np.mean(normal_alive):.1f}, ablated={np.mean(ablated_alive):.1f}",
            file=sys.stderr,
        )

    # Apply Holm-Bonferroni correction
    corrected = holm_bonferroni(raw_p_values)
    significant_count = 0
    for comp, p_corr in zip(comparisons, corrected, strict=True):
        comp["p_corrected"] = round(p_corr, 6)
        comp["significant"] = bool(p_corr < alpha)
        if comp["significant"]:
            significant_count += 1

    output = {
        "experiment": "criterion_ablation",
        "n_per_condition": n_normal,
        "alpha": alpha,
        "correction": "holm_bonferroni",
        "significant_count": significant_count,
        "total_comparisons": len(comparisons),
        "comparisons": comparisons,
    }

    print(json.dumps(output, indent=2))

    print(f"\nSignificant: {significant_count}/{len(comparisons)}", file=sys.stderr)
    for comp in comparisons:
        status = "SIG" if comp["significant"] else "n.s."
        print(
            f"  [{status}] {comp['condition']}: p_corr={comp['p_corrected']:.6f}, d={comp['cohens_d']:.3f}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
