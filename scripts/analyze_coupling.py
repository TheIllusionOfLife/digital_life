"""Time-lagged cross-correlation analysis for criterion coupling evidence.

Computes Pearson and Spearman correlations between per-step criterion
variables from normal-condition data to quantify functional coupling
between criteria (Reviewer B §C2).

Usage:
    uv run python scripts/analyze_coupling.py
"""

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "experiments" / "final_graph_normal.json"
OUTPUT_PATH = PROJECT_ROOT / "experiments" / "coupling_analysis.json"

# Variable pairs to analyze (var_a, var_b, label)
PAIRS = [
    ("energy_mean", "boundary_mean", "metabolism → cellular org"),
    ("energy_mean", "internal_state_mean_0", "metabolism → homeostasis"),
    ("boundary_mean", "internal_state_mean_0", "cellular org → homeostasis"),
]

MAX_LAG = 5


def load_timeseries(path: Path) -> dict[str, np.ndarray]:
    """Load normal-condition data and compute per-step population means.

    Returns dict mapping variable name to 1D array indexed by step order.
    """
    with open(path) as f:
        results = json.load(f)

    # Collect per-step values across all seeds
    step_vals: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in results:
        if "samples" not in r:
            continue
        for s in r["samples"]:
            step = s["step"]
            step_vals["energy_mean"][step].append(s["energy_mean"])
            step_vals["boundary_mean"][step].append(s["boundary_mean"])
            is_mean = s.get("internal_state_mean", [0, 0, 0, 0])
            step_vals["internal_state_mean_0"][step].append(is_mean[0])

    # Average across seeds for each step, ordered by step
    timeseries = {}
    for var_name, step_map in step_vals.items():
        steps = sorted(step_map.keys())
        timeseries[var_name] = np.array([np.mean(step_map[s]) for s in steps])

    return timeseries


def cross_correlation(x: np.ndarray, y: np.ndarray, max_lag: int) -> list[dict]:
    """Compute time-lagged Pearson and Spearman correlations.

    Positive lag means x leads y (x[t] correlates with y[t+lag]).
    """
    results = []
    n = len(x)
    for lag in range(max_lag + 1):
        if lag == 0:
            x_slice = x
            y_slice = y
        else:
            x_slice = x[:-lag]
            y_slice = y[lag:]

        if len(x_slice) < 3:
            continue

        r_pearson, p_pearson = stats.pearsonr(x_slice, y_slice)
        r_spearman, p_spearman = stats.spearmanr(x_slice, y_slice)

        results.append({
            "lag": lag,
            "pearson_r": round(float(r_pearson), 4),
            "pearson_p": float(p_pearson),
            "spearman_r": round(float(r_spearman), 4),
            "spearman_p": float(p_spearman),
            "n": len(x_slice),
        })
    return results


def main():
    """Run coupling analysis and output JSON results."""
    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found")
        return

    timeseries = load_timeseries(DATA_PATH)
    print(f"Loaded timeseries: {', '.join(timeseries.keys())}")
    print(f"Steps per variable: {len(next(iter(timeseries.values())))}")

    output = {"pairs": []}

    for var_a, var_b, label in PAIRS:
        if var_a not in timeseries or var_b not in timeseries:
            print(f"  SKIP: {label} (missing variable)")
            continue

        correlations = cross_correlation(timeseries[var_a], timeseries[var_b], MAX_LAG)

        # Best lag (highest absolute Pearson r)
        best = max(correlations, key=lambda c: abs(c["pearson_r"]))

        pair_result = {
            "var_a": var_a,
            "var_b": var_b,
            "label": label,
            "best_lag": best["lag"],
            "best_pearson_r": best["pearson_r"],
            "best_pearson_p": best["pearson_p"],
            "correlations": correlations,
        }
        output["pairs"].append(pair_result)

        print(f"\n  {label}:")
        for c in correlations:
            marker = " <-- best" if c["lag"] == best["lag"] else ""
            print(
                f"    lag={c['lag']}: Pearson r={c['pearson_r']:.4f} "
                f"(p={c['pearson_p']:.4e}), "
                f"Spearman r={c['spearman_r']:.4f} "
                f"(p={c['spearman_p']:.4e}){marker}"
            )

    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
