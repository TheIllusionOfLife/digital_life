"""AUC and alive-count extraction utilities for experiment results."""

from __future__ import annotations

import numpy as np

# np.trapezoid was added in NumPy 2.0; np.trapz was removed in NumPy 2.0.
# Support both to satisfy the project's numpy>=1.24 minimum.
_trapezoid = getattr(np, "trapezoid", None) or getattr(np, "trapz")


def extract_final_alive(results: list[dict]) -> np.ndarray:
    """Extract final_alive_count from each seed's result."""
    return np.array(
        [r["final_alive_count"] for r in results if "samples" in r and "final_alive_count" in r]
    )


def extract_auc(results: list[dict]) -> np.ndarray:
    """Compute AUC (area under alive-count curve) for each seed using trapezoidal rule."""
    aucs = []
    for r in results:
        if "samples" not in r:
            continue
        steps = [s["step"] for s in r["samples"]]
        counts = [s["alive_count"] for s in r["samples"]]
        if len(steps) >= 2:
            aucs.append(float(_trapezoid(counts, steps)))
        else:
            aucs.append(0.0)
    return np.array(aucs)


def extract_median_lifespan(results: list[dict]) -> float:
    """Extract median lifespan across all seeds."""
    all_lifespans = []
    for r in results:
        all_lifespans.extend(r.get("lifespans", []))
    if not all_lifespans:
        return 0.0
    return float(np.median(all_lifespans))


def extract_alive_at_step(results: list[dict], target_step: int) -> np.ndarray:
    """Extract alive_count at a specific step from each seed's samples.

    Finds the sample closest to target_step. For step 500 with sample_every=50,
    this is sample index 10.
    """
    counts = []
    for r in results:
        if "samples" not in r:
            continue
        best = None
        for s in r["samples"]:
            if best is None or abs(s["step"] - target_step) < abs(best["step"] - target_step):
                best = s
        if best is not None:
            counts.append(best["alive_count"])
    return np.array(counts)
