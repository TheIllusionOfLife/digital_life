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
    step_vals: dict[str, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in results:
        if "samples" not in r:
            continue
        for s in r["samples"]:
            step = s["step"]
            step_vals["energy_mean"][step].append(s["energy_mean"])
            step_vals["boundary_mean"][step].append(s["boundary_mean"])
            is_mean = s.get("internal_state_mean")
            if is_mean and len(is_mean) > 0:
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

        results.append(
            {
                "lag": lag,
                "pearson_r": round(float(r_pearson), 4),
                "pearson_p": float(p_pearson),
                "spearman_r": round(float(r_spearman), 4),
                "spearman_p": float(p_spearman),
                "n": len(x_slice),
            }
        )
    return results


def main():
    """Run coupling analysis and output JSON results."""
    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found")
        return

    timeseries = load_timeseries(DATA_PATH)
    if not timeseries:
        print(f"ERROR: no timeseries data loaded from {DATA_PATH}")
        return
    print(f"Loaded timeseries: {', '.join(timeseries.keys())}")
    print(f"Steps per variable: {len(next(iter(timeseries.values())))}")

    output = {"pairs": []}

    for var_a, var_b, label in PAIRS:
        if var_a not in timeseries or var_b not in timeseries:
            print(f"  SKIP: {label} (missing variable)")
            continue

        correlations = cross_correlation(timeseries[var_a], timeseries[var_b], MAX_LAG)

        if not correlations:
            print(f"  SKIP: {label} (insufficient data for correlation)")
            continue

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

    # --- Intervention-based causal effects ---
    print("\n--- Intervention-based causal effects ---")
    CRITERIA = [
        "metabolism",
        "boundary",
        "homeostasis",
        "response",
        "reproduction",
        "evolution",
        "growth",
    ]
    VARIABLES = ["energy_mean", "waste_mean", "boundary_mean", "internal_state_mean_0"]

    def extract_final_step_means(path: Path) -> dict[str, float]:
        """Extract population-mean values at the final sampled step, averaged across seeds."""
        if not path.exists():
            return {}
        with open(path) as f:
            results = json.load(f)
        vals: dict[str, list[float]] = defaultdict(list)
        for r in results:
            if "samples" not in r or not r["samples"]:
                continue
            last = r["samples"][-1]
            vals["energy_mean"].append(last["energy_mean"])
            vals["waste_mean"].append(last["waste_mean"])
            vals["boundary_mean"].append(last["boundary_mean"])
            is_mean = last.get("internal_state_mean")
            if is_mean and len(is_mean) > 0:
                vals["internal_state_mean_0"].append(is_mean[0])
        return {k: float(np.mean(v)) for k, v in vals.items() if v}

    normal_finals = extract_final_step_means(DATA_PATH)
    if not normal_finals:
        print("  WARNING: no normal baseline data for intervention analysis")
    else:
        intervention_effects = {"matrix": [], "details": []}
        for criterion in CRITERIA:
            ablation_path = (
                PROJECT_ROOT / "experiments" / f"final_graph_no_{criterion}.json"
            )
            ablated_finals = extract_final_step_means(ablation_path)
            if not ablated_finals:
                print(f"  SKIP: no_{criterion} (missing data)")
                continue

            row = {"ablated_criterion": criterion}
            detail = {"ablated_criterion": criterion, "effects": {}}
            for var in VARIABLES:
                normal_val = normal_finals.get(var)
                ablated_val = ablated_finals.get(var)
                if (
                    normal_val is not None
                    and ablated_val is not None
                    and normal_val != 0
                ):
                    pct_change = (normal_val - ablated_val) / abs(normal_val) * 100
                    row[var] = round(pct_change, 2)
                    detail["effects"][var] = {
                        "normal": round(normal_val, 4),
                        "ablated": round(ablated_val, 4),
                        "pct_change": round(pct_change, 2),
                    }
                else:
                    row[var] = None

            intervention_effects["matrix"].append(row)
            intervention_effects["details"].append(detail)
            effects_str = ", ".join(
                f"{v}={row[v]:.1f}%" for v in VARIABLES if row[v] is not None
            )
            print(f"  no_{criterion}: {effects_str}")

        output["intervention_effects"] = intervention_effects

    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
