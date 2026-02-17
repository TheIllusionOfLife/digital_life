"""Directed coupling analysis for criterion interactions.

Combines:
1. Time-lagged correlation on population means (descriptive)
2. Per-seed Granger-style F-tests (directed linear predictability)
3. Per-seed transfer entropy with permutation significance (nonlinear directionality)

Usage:
    uv run python scripts/analyze_coupling.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parent.parent
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


def holm_bonferroni(p_values: list[float]) -> list[float]:
    """Apply Holm-Bonferroni correction and keep original order."""
    n = len(p_values)
    if n == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    corrected = [0.0] * n
    cumulative_max = 0.0
    for rank, (orig_idx, p_val) in enumerate(indexed):
        adjusted = p_val * (n - rank)
        cumulative_max = max(cumulative_max, adjusted)
        corrected[orig_idx] = min(cumulative_max, 1.0)
    return corrected


def fisher_combine(p_values: list[float]) -> float:
    """Combine p-values using Fisher's method."""
    if not p_values:
        return 1.0
    clipped = [min(max(p, 1e-12), 1.0) for p in p_values]
    stat = -2.0 * sum(np.log(p) for p in clipped)
    return float(stats.chi2.sf(stat, 2 * len(clipped)))


def load_seed_timeseries(
    path: Path,
) -> tuple[list[int], list[dict[str, np.ndarray]], dict[str, int | float]]:
    """Load per-seed time series from normal condition output."""
    with open(path) as f:
        results = json.load(f)

    seed_series: list[dict[str, np.ndarray]] = []
    steps_ref: list[int] | None = None
    total_runs = len(results)
    dropped_missing_samples = 0
    dropped_step_mismatch = 0

    for run in results:
        samples = run.get("samples", [])
        if not samples:
            dropped_missing_samples += 1
            continue
        steps = [int(s["step"]) for s in samples]
        if steps_ref is None:
            steps_ref = steps
        elif steps != steps_ref:
            dropped_step_mismatch += 1
            continue

        energy = np.array([float(s["energy_mean"]) for s in samples], dtype=float)
        boundary = np.array([float(s["boundary_mean"]) for s in samples], dtype=float)
        internal = np.array(
            [
                float(s.get("internal_state_mean", [0.0])[0])
                if s.get("internal_state_mean")
                else 0.0
                for s in samples
            ],
            dtype=float,
        )
        seed_series.append(
            {
                "energy_mean": energy,
                "boundary_mean": boundary,
                "internal_state_mean_0": internal,
            }
        )

    accepted_runs = len(seed_series)
    dropped_runs = dropped_missing_samples + dropped_step_mismatch
    quality = {
        "total_runs": total_runs,
        "accepted_runs": accepted_runs,
        "dropped_runs": dropped_runs,
        "dropped_missing_samples": dropped_missing_samples,
        "dropped_step_mismatch": dropped_step_mismatch,
        "dropped_fraction": (dropped_runs / total_runs) if total_runs else 0.0,
    }

    if steps_ref is None:
        return [], [], quality
    return steps_ref, seed_series, quality


def mean_timeseries(seed_series: list[dict[str, np.ndarray]], var_name: str) -> np.ndarray:
    arr = np.stack([seed[var_name] for seed in seed_series], axis=0)
    return arr.mean(axis=0)


def cross_correlation(x: np.ndarray, y: np.ndarray, max_lag: int) -> list[dict]:
    """Compute lagged Pearson/Spearman correlations on aggregate means."""
    rows: list[dict] = []
    for lag in range(max_lag + 1):
        if lag == 0:
            x_slice, y_slice = x, y
        else:
            x_slice, y_slice = x[:-lag], y[lag:]
        if len(x_slice) < 3:
            continue
        r_p, p_p = stats.pearsonr(x_slice, y_slice)
        r_s, p_s = stats.spearmanr(x_slice, y_slice)
        rows.append(
            {
                "lag": lag,
                "pearson_r": round(float(r_p), 4),
                "pearson_p": float(p_p),
                "spearman_r": round(float(r_s), 4),
                "spearman_p": float(p_s),
                "n": len(x_slice),
            }
        )
    return rows


def _lag_matrix(series: np.ndarray, lag: int) -> np.ndarray:
    """Build [t-1 .. t-lag] lag matrix aligned to y[t]."""
    return np.column_stack([series[lag - i : len(series) - i] for i in range(1, lag + 1)])


def granger_f_test(x: np.ndarray, y: np.ndarray, lag: int) -> tuple[float, float] | None:
    """F-test for x -> y with lagged linear models."""
    if lag <= 0 or len(x) != len(y):
        return None
    n_obs = len(y) - lag
    if n_obs <= (2 * lag + 1):
        return None

    y_target = y[lag:]
    y_lags = _lag_matrix(y, lag)
    x_lags = _lag_matrix(x, lag)

    x_restricted = np.column_stack([np.ones(n_obs), y_lags])
    x_full = np.column_stack([np.ones(n_obs), y_lags, x_lags])

    beta_r, *_ = np.linalg.lstsq(x_restricted, y_target, rcond=None)
    beta_f, *_ = np.linalg.lstsq(x_full, y_target, rcond=None)

    resid_r = y_target - x_restricted @ beta_r
    resid_f = y_target - x_full @ beta_f

    ssr_r = float(np.sum(resid_r**2))
    ssr_f = float(np.sum(resid_f**2))

    df1 = lag
    df2 = n_obs - x_full.shape[1]
    if df2 <= 0 or ssr_f <= 0.0:
        return None

    numerator = max(ssr_r - ssr_f, 0.0) / df1
    denominator = ssr_f / df2
    if denominator <= 0.0:
        return None

    f_stat = numerator / denominator
    p_val = float(stats.f.sf(f_stat, df1, df2))
    return float(f_stat), p_val


def best_granger_with_lag_correction(x: np.ndarray, y: np.ndarray, max_lag: int) -> dict | None:
    """Evaluate lags 1..max_lag and pick best lag with Bonferroni over lags."""
    lag_rows = []
    for lag in range(1, max_lag + 1):
        test = granger_f_test(x, y, lag)
        if test is None:
            continue
        f_stat, p_val = test
        lag_rows.append({"lag": lag, "f_stat": f_stat, "p_raw": p_val})

    if not lag_rows:
        return None

    p_corr = holm_bonferroni([row["p_raw"] for row in lag_rows])
    for row, p_adjusted in zip(lag_rows, p_corr, strict=True):
        row["p_corrected"] = p_adjusted

    best = min(lag_rows, key=lambda row: row["p_corrected"])
    return {
        "best_lag": int(best["lag"]),
        "best_f_stat": float(best["f_stat"]),
        "best_p_corrected": float(best["p_corrected"]),
        "lags": [
            {
                "lag": int(row["lag"]),
                "f_stat": round(float(row["f_stat"]), 6),
                "p_raw": float(row["p_raw"]),
                "p_corrected": float(row["p_corrected"]),
            }
            for row in lag_rows
        ],
    }


def discretize_series(values: np.ndarray, bins: int) -> np.ndarray:
    """Quantile discretization to integer bins in [0, bins-1]."""
    if len(values) == 0:
        return np.array([], dtype=int)
    quantiles = np.linspace(0.0, 1.0, bins + 1)
    edges = np.quantile(values, quantiles)
    edges = np.unique(edges)
    if len(edges) <= 2:
        return np.zeros_like(values, dtype=int)
    idx = np.digitize(values, edges[1:-1], right=False)
    return np.asarray(idx, dtype=int)


def transfer_entropy_from_discrete(
    x_prev: np.ndarray, y_prev: np.ndarray, y_curr: np.ndarray
) -> float:
    """Compute TE = I(Y_t ; X_{t-1} | Y_{t-1}) in bits."""
    n = len(y_curr)
    if n == 0:
        return 0.0

    x_bins = int(np.max(x_prev)) + 1 if len(x_prev) > 0 else 1
    y_bins = int(np.max(np.concatenate((y_prev, y_curr)))) + 1

    joint_y = np.bincount(y_prev, minlength=y_bins).astype(float)
    joint_xy = np.bincount(
        x_prev * y_bins + y_prev, minlength=x_bins * y_bins
    ).astype(float).reshape(x_bins, y_bins)
    joint_yy = np.bincount(
        y_prev * y_bins + y_curr, minlength=y_bins * y_bins
    ).astype(float).reshape(y_bins, y_bins)
    joint_xxy = np.bincount(
        (x_prev * y_bins + y_prev) * y_bins + y_curr,
        minlength=x_bins * y_bins * y_bins,
    ).astype(float).reshape(x_bins, y_bins, y_bins)

    p_xxy = joint_xxy / n
    p_yc_given_xy = np.divide(
        joint_xxy,
        joint_xy[:, :, None],
        out=np.zeros_like(joint_xxy),
        where=joint_xy[:, :, None] > 0,
    )
    p_yc_given_y = np.divide(
        joint_yy[None, :, :],
        joint_y[None, :, None],
        out=np.zeros((1, y_bins, y_bins), dtype=float),
        where=joint_y[None, :, None] > 0,
    )

    ratio = np.divide(
        p_yc_given_xy,
        p_yc_given_y,
        out=np.zeros_like(joint_xxy),
        where=p_yc_given_y > 0,
    )
    mask = (p_xxy > 0) & (ratio > 0)
    if not np.any(mask):
        return 0.0
    te = np.sum(p_xxy[mask] * np.log2(ratio[mask]))
    return float(max(float(te), 0.0))


def transfer_entropy_lag1(
    x: np.ndarray,
    y: np.ndarray,
    bins: int,
    permutations: int,
    rng: np.random.Generator,
) -> dict | None:
    """Estimate TE(X->Y) with permutation p-value."""
    if len(x) < 4 or len(x) != len(y):
        return None

    # Use a shared discretization per full series to keep y(t-1), y(t) on
    # the same state space.
    x_disc = discretize_series(x, bins)
    y_disc = discretize_series(y, bins)
    x_prev = x_disc[:-1]
    y_prev = y_disc[:-1]
    y_curr = y_disc[1:]

    observed = transfer_entropy_from_discrete(x_prev, y_prev, y_curr)

    null_vals = np.empty(permutations, dtype=float)
    for i in range(permutations):
        perm_x_prev = rng.permutation(x_prev)
        null_vals[i] = transfer_entropy_from_discrete(perm_x_prev, y_prev, y_curr)

    p_val = float((np.sum(null_vals >= observed) + 1) / (permutations + 1))
    return {
        "te": float(observed),
        "p_value": p_val,
        "null_mean": float(np.mean(null_vals)),
        "null_std": float(np.std(null_vals, ddof=1)) if permutations > 1 else 0.0,
    }


def phase_randomize(series: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Return a phase-randomized surrogate preserving power spectrum."""
    n = len(series)
    if n < 4:
        return series.copy()
    spectrum = np.fft.rfft(series)
    randomized = spectrum.copy()
    if n % 2 == 0:
        phases = rng.uniform(0.0, 2.0 * np.pi, size=len(spectrum) - 2)
        randomized[1:-1] = np.abs(randomized[1:-1]) * np.exp(1j * phases)
    else:
        phases = rng.uniform(0.0, 2.0 * np.pi, size=len(spectrum) - 1)
        randomized[1:] = np.abs(randomized[1:]) * np.exp(1j * phases)
    surrogate = np.fft.irfft(randomized, n=n)
    return np.asarray(surrogate, dtype=float)


def te_robustness_summary(
    x: np.ndarray,
    y: np.ndarray,
    *,
    bin_settings: list[int],
    permutation_settings: list[int],
    rng_seed: int,
    phase_surrogate_samples: int,
    surrogate_permutation_floor: int,
    surrogate_permutation_divisor: int,
) -> list[dict]:
    """Compute TE sensitivity and phase-surrogate robustness grid for one pair."""
    rows: list[dict] = []
    for bins in bin_settings:
        for permutations in permutation_settings:
            te_seed = np.random.SeedSequence([rng_seed, bins, permutations, 1])
            te_rng = np.random.default_rng(te_seed)
            te = transfer_entropy_lag1(
                x, y, bins=bins, permutations=permutations, rng=te_rng
            )
            if te is None:
                continue

            phase_seed = np.random.SeedSequence([rng_seed, bins, permutations, 2])
            phase_rng = np.random.default_rng(phase_seed)
            surrogate_te = np.empty(phase_surrogate_samples, dtype=float)
            surrogate_te.fill(np.nan)
            for i in range(phase_surrogate_samples):
                x_surrogate = phase_randomize(x, phase_rng)
                y_surrogate = phase_randomize(y, phase_rng)
                te_surrogate = transfer_entropy_lag1(
                    x_surrogate,
                    y_surrogate,
                    bins=bins,
                    permutations=max(
                        surrogate_permutation_floor,
                        permutations // surrogate_permutation_divisor,
                    ),
                    rng=phase_rng,
                )
                if te_surrogate is not None:
                    surrogate_te[i] = te_surrogate["te"]

            valid_surrogates = surrogate_te[~np.isnan(surrogate_te)]
            phase_p = float(
                (np.sum(valid_surrogates >= float(te["te"])) + 1)
                / (len(valid_surrogates) + 1)
            )
            rows.append(
                {
                    "bins": bins,
                    "permutations": permutations,
                    "te": round(float(te["te"]), 6),
                    "p_value": float(te["p_value"]),
                    "phase_surrogate_p_value": phase_p,
                    "phase_surrogate_te_mean": round(float(np.nanmean(surrogate_te)), 6)
                    if len(valid_surrogates) > 0
                    else None,
                    "phase_surrogate_valid_n": int(len(valid_surrogates)),
                }
            )
    return rows


def bootstrap_ci(
    values: np.ndarray, n_boot: int = 2000, alpha: float = 0.05
) -> tuple[float, float]:
    """Percentile bootstrap CI for mean over seeds."""
    if len(values) == 0:
        return (0.0, 0.0)
    rng = np.random.default_rng(2026)
    boot = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sample = values[rng.integers(0, len(values), size=len(values))]
        boot[i] = float(np.mean(sample))
    lo = float(np.percentile(boot, 100 * alpha / 2))
    hi = float(np.percentile(boot, 100 * (1 - alpha / 2)))
    return lo, hi


def extract_final_step_means(path: Path) -> dict[str, float]:
    """Extract mean of final step values across all runs in a JSON file."""
    if not path.exists():
        return {}
    with open(path) as f:
        results = json.load(f)
    vals: dict[str, list[float]] = defaultdict(list)
    for run in results:
        samples = run.get("samples", [])
        if not samples:
            continue
        last = samples[-1]
        vals["energy_mean"].append(float(last["energy_mean"]))
        vals["waste_mean"].append(float(last["waste_mean"]))
        vals["boundary_mean"].append(float(last["boundary_mean"]))
        internal_state = last.get("internal_state_mean")
        if internal_state and len(internal_state) > 0:
            vals["internal_state_mean_0"].append(float(internal_state[0]))
    return {k: float(np.mean(v)) for k, v in vals.items() if v}


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
            "median_best_f": round(float(np.median(seed_granger_f)), 6)
            if seed_granger_f
            else 0.0,
            "significant_seed_fraction": round(
                float(np.mean(np.array(seed_granger_p) < 0.05)), 4
            )
            if seed_granger_p
            else 0.0,
        },
        "transfer_entropy": {
            "n_seed_tests": len(seed_te),
            "fisher_p_raw": te_pair_p,
            "mean_te": round(float(np.mean(te_arr)), 6) if len(te_arr) else 0.0,
            "mean_te_ci95": [round(te_ci[0], 6), round(te_ci[1], 6)],
            "significant_seed_fraction": round(
                float(np.mean(np.array(seed_te_p) < 0.05)), 4
            )
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
        print(
            f"  Granger fisher p={granger_p:.4e}, "
            f"median F={granger_median_f:.3f}"
        )
        print(
            f"  TE fisher p={te_p:.4e}, mean TE={row['transfer_entropy']['mean_te']:.4f}"
        )

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
    if robustness_profile not in ROBUSTNESS_PROFILES:
        valid_profiles = ", ".join(sorted(ROBUSTNESS_PROFILES.keys()))
        raise ValueError(
            f"Unknown robustness_profile '{robustness_profile}'. "
            f"Expected one of: {valid_profiles}."
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--robustness-profile",
        choices=sorted(ROBUSTNESS_PROFILES.keys()),
        default="full",
        help="Runtime/precision profile for TE robustness computations.",
    )
    args = parser.parse_args()
    main(robustness_profile=args.robustness_profile)
