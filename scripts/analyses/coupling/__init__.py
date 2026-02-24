"""Directed coupling analysis package.

Combines time-lagged correlation, Granger-style F-tests, and transfer entropy
to measure directed information flow between physiology criteria.

Entry point: ``main()`` for CLI use.
"""

from __future__ import annotations

import json
import sys

import numpy as np
from _project_root import PROJECT_ROOT

from .granger import best_granger_with_lag_correction
from .lagged import (
    bootstrap_ci,
    cross_correlation,
    extract_final_step_means,
    fisher_combine,
    load_seed_timeseries,
    mean_timeseries,
)
from .transfer_entropy import te_robustness_summary, transfer_entropy_lag1

try:
    from ..results.statistics import holm_bonferroni
except ImportError:
    from analyses.results.statistics import holm_bonferroni
DATA_PATH = PROJECT_ROOT / "experiments" / "final_graph_normal.json"
OUTPUT_PATH = PROJECT_ROOT / "experiments" / "coupling_analysis.json"

PAIRS = [
    ("energy_mean", "boundary_mean", "metabolism -> cellular org"),
    ("energy_mean", "internal_state_mean_0", "metabolism -> homeostasis"),
    ("boundary_mean", "internal_state_mean_0", "cellular org -> homeostasis"),
]

MAX_LAG = 5
TE_BINS = 5
TE_PERMUTATIONS = 400
TE_BIN_SETTINGS = [3, 5, 7]
TE_PERMUTATION_SETTINGS = [200, 400, 800]
TE_PHASE_SURROGATE_SAMPLES = 100
MAX_DROPPED_SEED_FRACTION = 0.10
INCLUDE_SEED_DETAILS = True

ROBUSTNESS_PROFILES = {
    "full": {
        "bin_settings": TE_BIN_SETTINGS,
        "permutation_settings": TE_PERMUTATION_SETTINGS,
        "phase_surrogate_samples": TE_PHASE_SURROGATE_SAMPLES,
        "surrogate_permutation_floor": 50,
        "surrogate_permutation_divisor": 4,
    },
    "fast": {
        "bin_settings": [3, 5],
        "permutation_settings": [200, 400],
        "phase_surrogate_samples": 50,
        "surrogate_permutation_floor": 25,
        "surrogate_permutation_divisor": 8,
    },
}


def analyze_pair(
    seed_series: list[dict[str, np.ndarray]],
    var_a: str,
    var_b: str,
    label: str,
    profile: dict,
    rng: np.random.Generator,
    pair_index: int,
) -> tuple[dict, float, float]:
    """Analyze a single pair of variables."""
    bin_settings = profile["bin_settings"]
    permutation_settings = profile["permutation_settings"]
    phase_surrogate_samples = int(profile["phase_surrogate_samples"])
    surrogate_permutation_floor = int(profile["surrogate_permutation_floor"])
    surrogate_permutation_divisor = int(profile["surrogate_permutation_divisor"])

    mean_a = mean_timeseries(seed_series, var_a)
    mean_b = mean_timeseries(seed_series, var_b)
    corr_rows = cross_correlation(mean_a, mean_b, MAX_LAG)
    best_corr = max(corr_rows, key=lambda row: abs(row["pearson_r"])) if corr_rows else None

    seed_granger: list[dict] = []
    seed_granger_p: list[float] = []
    seed_granger_f: list[float] = []

    seed_te: list[dict] = []
    seed_te_p: list[float] = []
    seed_te_values: list[float] = []

    for idx, run in enumerate(seed_series):
        x = run[var_a]
        y = run[var_b]

        g = best_granger_with_lag_correction(x, y, MAX_LAG)
        if g is not None:
            seed_granger.append({"seed_index": idx, **g})
            seed_granger_p.append(g["best_p_corrected"])
            seed_granger_f.append(g["best_f_stat"])

        te = transfer_entropy_lag1(
            x,
            y,
            bins=TE_BINS,
            permutations=TE_PERMUTATIONS,
            rng=rng,
        )
        if te is not None:
            seed_te.append({"seed_index": idx, **te})
            seed_te_p.append(te["p_value"])
            seed_te_values.append(te["te"])

    granger_pair_p = fisher_combine(seed_granger_p)
    te_pair_p = fisher_combine(seed_te_p)

    te_arr = np.array(seed_te_values, dtype=float)
    te_ci = bootstrap_ci(te_arr)

    row = {
        "label": label,
        "var_a": var_a,
        "var_b": var_b,
        "lagged_correlation": {
            "best_lag": best_corr["lag"] if best_corr else None,
            "best_pearson_r": best_corr["pearson_r"] if best_corr else None,
            "best_pearson_p": best_corr["pearson_p"] if best_corr else None,
            "correlations": corr_rows,
        },
        "granger": {
            "n_seed_tests": len(seed_granger),
            "fisher_p_raw": granger_pair_p,
            "median_best_f": round(float(np.median(seed_granger_f)), 6) if seed_granger_f else 0.0,
            "significant_seed_fraction": round(float(np.mean(np.array(seed_granger_p) < 0.05)), 4)
            if seed_granger_p
            else 0.0,
        },
        "transfer_entropy": {
            "n_seed_tests": len(seed_te),
            "fisher_p_raw": te_pair_p,
            "mean_te": round(float(np.mean(te_arr)), 6) if len(te_arr) else 0.0,
            "mean_te_ci95": [round(te_ci[0], 6), round(te_ci[1], 6)],
            "significant_seed_fraction": round(float(np.mean(np.array(seed_te_p) < 0.05)), 4)
            if seed_te_p
            else 0.0,
            "robustness_on_mean": True,
            # Robustness is computed on population means to keep this pass tractable.
            "robustness": te_robustness_summary(
                mean_a,
                mean_b,
                bin_settings=bin_settings,
                permutation_settings=permutation_settings,
                rng_seed=2026 + pair_index,
                phase_surrogate_samples=phase_surrogate_samples,
                surrogate_permutation_floor=surrogate_permutation_floor,
                surrogate_permutation_divisor=surrogate_permutation_divisor,
            ),
        },
    }
    if INCLUDE_SEED_DETAILS:
        row["granger"]["seed_tests"] = seed_granger
        row["transfer_entropy"]["seed_tests"] = seed_te

    return row, granger_pair_p, te_pair_p


def run_pairwise_analysis(
    seed_series: list[dict[str, np.ndarray]],
    profile: dict,
    rng: np.random.Generator,
) -> tuple[list[dict], list[float], list[float]]:
    """Run analysis for all defined pairs."""
    granger_pair_ps: list[float] = []
    te_pair_ps: list[float] = []
    pair_rows: list[dict] = []

    for idx, (var_a, var_b, label) in enumerate(PAIRS):
        row, granger_p, te_p = analyze_pair(
            seed_series, var_a, var_b, label, profile, rng, pair_index=idx
        )

        pair_rows.append(row)
        granger_pair_ps.append(granger_p)
        te_pair_ps.append(te_p)

        granger_median_f = float(row["granger"]["median_best_f"])
        print(f"\n{label}")
        print(f"  Granger fisher p={granger_p:.4e}, median F={granger_median_f:.3f}")
        print(f"  TE fisher p={te_p:.4e}, mean TE={row['transfer_entropy']['mean_te']:.4f}")

    return pair_rows, granger_pair_ps, te_pair_ps


def run_intervention_analysis(output_dict: dict) -> None:
    """Run intervention-based effect summaries and update output dict."""
    print("\n--- Intervention-based effect summaries ---")
    criteria = [
        "metabolism",
        "boundary",
        "homeostasis",
        "response",
        "reproduction",
        "evolution",
        "growth",
    ]
    variables = ["energy_mean", "waste_mean", "boundary_mean", "internal_state_mean_0"]

    normal_finals = extract_final_step_means(DATA_PATH)
    if not normal_finals:
        return

    intervention_effects = {"matrix": [], "details": []}
    for criterion in criteria:
        ablation_path = PROJECT_ROOT / "experiments" / f"final_graph_no_{criterion}.json"
        ablated_finals = extract_final_step_means(ablation_path)
        if not ablated_finals:
            continue

        row = {"ablated_criterion": criterion}
        detail = {"ablated_criterion": criterion, "effects": {}}
        for var in variables:
            normal_val = normal_finals.get(var)
            ablated_val = ablated_finals.get(var)
            if normal_val is None or ablated_val is None or normal_val == 0:
                row[var] = None
                continue
            pct_change = (normal_val - ablated_val) / abs(normal_val) * 100
            row[var] = round(pct_change, 2)
            detail["effects"][var] = {
                "normal": round(normal_val, 4),
                "ablated": round(ablated_val, 4),
                "pct_change": round(pct_change, 2),
            }

        intervention_effects["matrix"].append(row)
        intervention_effects["details"].append(detail)

    output_dict["intervention_effects"] = intervention_effects


def main(*, robustness_profile: str = "full") -> None:
    """Run full coupling analysis and write results to experiments/coupling_analysis.json."""
    if robustness_profile not in ROBUSTNESS_PROFILES:
        valid_profiles = ", ".join(sorted(ROBUSTNESS_PROFILES.keys()))
        raise ValueError(
            f"Unknown robustness_profile '{robustness_profile}'. Expected one of: {valid_profiles}."
        )
    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found")
        return
    profile = ROBUSTNESS_PROFILES[robustness_profile]

    steps, seed_series, quality = load_seed_timeseries(DATA_PATH)
    if not seed_series:
        print(f"ERROR: no timeseries data loaded from {DATA_PATH}")
        return
    if quality["dropped_fraction"] > MAX_DROPPED_SEED_FRACTION:
        print(
            "ERROR: dropped-seed fraction exceeds threshold "
            f"({quality['dropped_fraction']:.2%} > {MAX_DROPPED_SEED_FRACTION:.2%})",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Loaded {len(seed_series)} seeds with {len(steps)} sampled steps")
    print(
        "Seed quality: total={} accepted={} dropped={} ({:.2f}%)".format(
            quality["total_runs"],
            quality["accepted_runs"],
            quality["dropped_runs"],
            100.0 * quality["dropped_fraction"],
        )
    )

    output: dict[str, object] = {
        "schema_version": 2,
        "pairs": [],
        "quality": quality,
        "method": {
            "max_lag": MAX_LAG,
            "te_bins": TE_BINS,
            "te_permutations": TE_PERMUTATIONS,
            "te_robustness_profile": robustness_profile,
            "te_robustness_bin_settings": profile["bin_settings"],
            "te_robustness_permutation_settings": profile["permutation_settings"],
            "te_phase_surrogate_samples": int(profile["phase_surrogate_samples"]),
            "te_surrogate_permutation_floor": int(profile["surrogate_permutation_floor"]),
            "te_surrogate_permutation_divisor": int(profile["surrogate_permutation_divisor"]),
            "te_robustness_on_mean": True,
            "pair_level_correction": "holm_bonferroni",
            "seed_level_p_combination": "fisher",
            "include_seed_details": INCLUDE_SEED_DETAILS,
            "max_dropped_seed_fraction": MAX_DROPPED_SEED_FRACTION,
        },
    }

    te_rng = np.random.default_rng(42)
    pair_rows, granger_pair_ps, te_pair_ps = run_pairwise_analysis(seed_series, profile, te_rng)

    granger_corr = holm_bonferroni(granger_pair_ps)
    te_corr = holm_bonferroni(te_pair_ps)

    for row, p_g, p_te in zip(pair_rows, granger_corr, te_corr, strict=True):
        row["granger"]["fisher_p_corrected"] = round(float(p_g), 6)
        row["granger"]["pair_significant"] = bool(p_g < 0.05)
        row["transfer_entropy"]["fisher_p_corrected"] = round(float(p_te), 6)
        row["transfer_entropy"]["pair_significant"] = bool(p_te < 0.05)

    output["pairs"] = pair_rows

    run_intervention_analysis(output)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved: {OUTPUT_PATH}")
