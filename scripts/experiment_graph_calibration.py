"""Calibration experiment for GraphMetabolism mode.

Runs normal condition with metabolism_mode="graph", seeds 0-29, 2000 steps.
Compares alive counts and energy dynamics to ToyMetabolism baseline.

Usage:
    uv run python scripts/experiment_graph_calibration.py
"""

import json
import time
from pathlib import Path

import digital_life
from experiment_utils import log, run_single, safe_path

STEPS = 2000
SAMPLE_EVERY = 50
SEEDS = list(range(0, 30))  # calibration set


def summarize_results(label: str, results: list[dict]) -> dict:
    """Compute summary statistics for a set of experiment results."""
    n = len(results)
    if n == 0:
        return {
            "label": label,
            "n": 0,
            "alive_mean": 0.0,
            "alive_min": 0,
            "alive_max": 0,
            "energy_mean": 0.0,
        }
    alive_counts = [r["final_alive_count"] for r in results]
    energies = [r["samples"][-1]["energy_mean"] for r in results if r["samples"]]
    return {
        "label": label,
        "n": n,
        "alive_mean": sum(alive_counts) / n,
        "alive_min": min(alive_counts),
        "alive_max": max(alive_counts),
        "energy_mean": sum(energies) / len(energies) if energies else 0.0,
    }


def main():
    log(f"Digital Life v{digital_life.version()}")
    log(f"GraphMetabolism calibration: {STEPS} steps, seeds {SEEDS[0]}-{SEEDS[-1]}")
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)

    modes = {
        "toy": {"metabolism_mode": "toy"},
        "graph": {"metabolism_mode": "graph"},
    }

    summaries = []
    for mode_name, overrides in modes.items():
        log(f"--- Mode: {mode_name} ---")
        results = []
        t0 = time.perf_counter()

        for seed in SEEDS:
            ts = time.perf_counter()
            result = run_single(seed, STEPS, SAMPLE_EVERY, overrides)
            elapsed = time.perf_counter() - ts
            results.append(result)
            log(f"  seed={seed:3d}  alive={result['final_alive_count']:4d}  {elapsed:.2f}s")

        elapsed = time.perf_counter() - t0
        log(f"  Mode time: {elapsed:.1f}s")

        raw_path = safe_path(out_dir, f"calibration_{mode_name}.json")
        with open(raw_path, "w") as f:
            json.dump(results, f, indent=2)
        log(f"  Saved: {raw_path}")

        summary = summarize_results(mode_name, results)
        summaries.append(summary)
        log(f"  alive: mean={summary['alive_mean']:.1f} "
            f"[{summary['alive_min']}, {summary['alive_max']}]  "
            f"energy_mean={summary['energy_mean']:.4f}")
        log("")

    log("=== Comparison ===")
    for s in summaries:
        log(f"  {s['label']:6s}: alive_mean={s['alive_mean']:.1f}, "
            f"energy_mean={s['energy_mean']:.4f}")

    summary_path = safe_path(out_dir, "calibration_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summaries, f, indent=2)
    log(f"\nSaved summary: {summary_path}")


if __name__ == "__main__":
    main()
