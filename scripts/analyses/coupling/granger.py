"""Granger-style F-tests for directed linear predictability."""

from __future__ import annotations

import numpy as np
from scipy import stats

try:
    from ..results.statistics import holm_bonferroni
except ImportError:
    from analyses.results.statistics import holm_bonferroni


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
    """Evaluate lags 1..max_lag and pick best lag with Holm-Bonferroni correction over lags."""
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
        "best_f_stat": round(float(best["f_stat"]), 6),
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
