"""Synergy analysis for pairwise criterion-ablation experiments.

Computes synergy scores to test whether criteria interact
super-additively (true interdependence) or sub-additively.

For each pair (A, B):
  decline_A  = baseline_mean - ablation_A_mean
  decline_B  = baseline_mean - ablation_B_mean
  decline_AB = baseline_mean - ablation_AB_mean
  synergy    = decline_AB - (decline_A + decline_B)

  synergy > 0: super-additive → true interdependence
  synergy ≈ 0: additive → independent effects
  synergy < 0: sub-additive → redundancy

Usage:
    uv run python scripts/analyze_pairwise.py experiments/final experiments/pairwise \
        > experiments/pairwise_statistics.json

Arguments:
    single_prefix: path prefix for single-ablation JSON files (e.g. experiments/final)
    pairwise_prefix: path prefix for pairwise-ablation JSON files (e.g. experiments/pairwise)
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

PAIRS = [
    ("metabolism", "homeostasis"),
    ("metabolism", "response"),
    ("reproduction", "growth"),
    ("boundary", "homeostasis"),
    ("response", "homeostasis"),
    ("reproduction", "evolution"),
]


def load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def extract_final_alive(results: list[dict]) -> np.ndarray:
    return np.array([r["final_alive_count"] for r in results if "samples" in r])


def compute_synergy(
    baseline_mean: float,
    decline_a: float,
    decline_b: float,
    decline_ab: float,
) -> float:
    """Compute synergy: super-additive = positive."""
    return decline_ab - (decline_a + decline_b)


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python scripts/analyze_pairwise.py <single_prefix> <pairwise_prefix>",
            file=sys.stderr,
        )
        print(
            "  e.g. python scripts/analyze_pairwise.py experiments/final experiments/pairwise",
            file=sys.stderr,
        )
        sys.exit(1)

    single_prefix = sys.argv[1]
    pairwise_prefix = sys.argv[2]

    # Load normal baseline (try pairwise first, fall back to single)
    normal_path = Path(f"{pairwise_prefix}_normal.json")
    if not normal_path.exists():
        normal_path = Path(f"{single_prefix}_normal.json")
    normal_results = load_json(normal_path)
    if not normal_results:
        print("ERROR: no normal baseline results found", file=sys.stderr)
        sys.exit(1)

    normal_alive = extract_final_alive(normal_results)
    baseline_mean = float(np.mean(normal_alive))
    print(f"Baseline: n={len(normal_alive)}, mean={baseline_mean:.1f}", file=sys.stderr)

    # Load single ablation results
    single_declines = {}
    for criterion in set(c for pair in PAIRS for c in pair):
        path = Path(f"{single_prefix}_no_{criterion}.json")
        results = load_json(path)
        if results:
            alive = extract_final_alive(results)
            single_declines[criterion] = baseline_mean - float(np.mean(alive))
            print(
                f"  no_{criterion}: mean={np.mean(alive):.1f}, decline={single_declines[criterion]:.1f}",
                file=sys.stderr,
            )
        else:
            print(f"  no_{criterion}: MISSING", file=sys.stderr)

    # Analyze each pair
    pair_results = []
    for a, b in PAIRS:
        pair_name = f"no_{a}_no_{b}"
        path = Path(f"{pairwise_prefix}_{pair_name}.json")
        results = load_json(path)
        if not results:
            print(f"  {pair_name}: SKIPPED (no data)", file=sys.stderr)
            continue

        ab_alive = extract_final_alive(results)
        if len(ab_alive) < 2:
            print(f"  {pair_name}: SKIPPED (n < 2)", file=sys.stderr)
            continue

        decline_a = single_declines.get(a, 0.0)
        decline_b = single_declines.get(b, 0.0)
        decline_ab = baseline_mean - float(np.mean(ab_alive))
        synergy = compute_synergy(baseline_mean, decline_a, decline_b, decline_ab)

        # Statistical test: compare observed pairwise decline vs expected additive
        # Use one-sample t-test on per-seed pairwise alive counts vs expected
        expected_mean = baseline_mean - (decline_a + decline_b)
        t_stat, p_value = stats.ttest_1samp(ab_alive, expected_mean)
        # We want one-sided: decline_AB > decline_A + decline_B → ab_alive < expected
        p_one_sided = float(p_value / 2) if t_stat < 0 else 1.0 - float(p_value / 2)

        entry = {
            "pair": [a, b],
            "pair_name": pair_name,
            "decline_a": round(decline_a, 2),
            "decline_b": round(decline_b, 2),
            "decline_ab": round(decline_ab, 2),
            "expected_additive": round(decline_a + decline_b, 2),
            "synergy": round(synergy, 2),
            "super_additive": synergy > 0,
            "ab_mean": round(float(np.mean(ab_alive)), 2),
            "ab_median": round(float(np.median(ab_alive)), 2),
            "t_stat": round(float(t_stat), 4),
            "p_super_additive": round(p_one_sided, 6),
            "n": len(ab_alive),
        }
        pair_results.append(entry)

        label = "SUPER-ADD" if synergy > 0 else "sub-add"
        print(
            f"  ({a}, {b}): synergy={synergy:.1f} [{label}], "
            f"decline_AB={decline_ab:.1f} vs expected={decline_a + decline_b:.1f}, "
            f"p={p_one_sided:.4f}",
            file=sys.stderr,
        )

    output = {
        "experiment": "pairwise_ablation",
        "baseline_mean": round(baseline_mean, 2),
        "n_per_condition": len(normal_alive),
        "pairs": pair_results,
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
