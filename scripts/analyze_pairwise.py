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

try:
    from .experiment_common import PAIRS, extract_final_alive, load_json
except ImportError:
    from experiment_common import PAIRS, extract_final_alive, load_json


def compute_synergy(
    decline_a: float,
    decline_b: float,
    decline_ab: float,
) -> float:
    """Compute synergy: super-additive = positive."""
    return decline_ab - (decline_a + decline_b)


def load_baseline(single_prefix: str, pairwise_prefix: str) -> tuple[float, list[int]]:
    """Load baseline data from pairwise or single prefix."""
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
    return baseline_mean, normal_alive


def load_single_ablations(single_prefix: str) -> dict[str, list[float]]:
    """Load single ablation results for all criteria in PAIRS."""
    single_alive = {}
    for criterion in set(c for pair in PAIRS for c in pair):
        path = Path(f"{single_prefix}_no_{criterion}.json")
        results = load_json(path)
        if results:
            single_alive[criterion] = np.array(
                extract_final_alive(results), dtype=float
            )
    return single_alive


def calculate_declines(
    baseline_mean: float, single_alive: dict[str, list[float]]
) -> dict[str, float]:
    """Calculate decline for each single ablation."""
    single_declines = {}
    for criterion, alive in single_alive.items():
        alive_mean = float(np.mean(alive))
        decline = baseline_mean - alive_mean
        single_declines[criterion] = decline
        print(
            f"  no_{criterion}: mean={alive_mean:.1f}, decline={decline:.1f}",
            file=sys.stderr,
        )

    # Check for missing criteria
    all_criteria = set(c for pair in PAIRS for c in pair)
    for criterion in all_criteria:
        if criterion not in single_declines:
            print(f"  no_{criterion}: MISSING", file=sys.stderr)

    return single_declines


def analyze_pairs(
    pairwise_prefix: str,
    baseline_mean: float,
    single_declines: dict[str, float],
    single_alive: dict[str, list[float]],
) -> tuple[list[dict], list[dict]]:
    """Analyze pairwise ablations and compute synergy."""
    pair_results = []
    robust_synergy = []

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

        missing = [k for k in (a, b) if k not in single_declines]
        if missing:
            print(
                f"  {pair_name}: SKIPPED (missing single-ablation data for {missing})",
                file=sys.stderr,
            )
            continue

        decline_a = single_declines[a]
        decline_b = single_declines[b]
        decline_ab = baseline_mean - float(np.mean(ab_alive))
        synergy = compute_synergy(decline_a, decline_b, decline_ab)

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

        # Robust synergy
        a_mean = baseline_mean - entry["decline_a"]
        b_mean = baseline_mean - entry["decline_b"]
        ab_mean = entry["ab_mean"]

        # Log scale synergy
        log_bl = np.log(baseline_mean + 1)
        log_ab = np.log(ab_mean + 1)
        log_a = np.log(a_mean + 1)
        log_b = np.log(b_mean + 1)
        synergy_log = (log_bl - log_ab) - ((log_bl - log_a) + (log_bl - log_b))

        # Percent scale synergy
        if baseline_mean > 0:
            pct_a = (baseline_mean - a_mean) / baseline_mean * 100
            pct_b = (baseline_mean - b_mean) / baseline_mean * 100
            pct_ab = (baseline_mean - ab_mean) / baseline_mean * 100
            synergy_pct = pct_ab - (pct_a + pct_b)
        else:
            pct_a = pct_b = pct_ab = synergy_pct = 0.0

        robust_entry = {
            "pair": [a, b],
            "synergy_raw": entry["synergy"],
            "synergy_log": round(float(synergy_log), 4),
            "synergy_pct": round(float(synergy_pct), 2),
            "pct_decline_a": round(float(pct_a), 2),
            "pct_decline_b": round(float(pct_b), 2),
            "pct_decline_ab": round(float(pct_ab), 2),
        }
        robust_synergy.append(robust_entry)

    print("\n--- Robust synergy (log & percent scales) ---", file=sys.stderr)
    for r in robust_synergy:
        a, b = r["pair"]
        print(
            f"  ({a}, {b}): raw={r['synergy_raw']}, "
            f"log={r['synergy_log']:.4f}, pct={r['synergy_pct']:.2f}%",
            file=sys.stderr,
        )

    return pair_results, robust_synergy


def analyze_floor_effects(
    normal_alive: list[int],
    single_alive: dict[str, list[float]],
    pair_results: list[dict],
    pairwise_prefix: str,
) -> dict:
    """Analyze floor effects (fraction of samples <= threshold)."""
    print("\n--- Floor effect analysis ---", file=sys.stderr)
    FLOOR_THRESHOLD = 5
    floor_analysis = {}

    # Normal condition
    normal_floor = float(np.mean(np.array(normal_alive) <= FLOOR_THRESHOLD))
    floor_analysis["normal"] = {
        "fraction_at_floor": round(normal_floor, 4),
        "n": len(normal_alive),
    }
    print(f"  normal: floor_frac={normal_floor:.4f}", file=sys.stderr)

    # Single ablations
    for criterion, alive_arr in single_alive.items():
        frac = float(np.mean(alive_arr <= FLOOR_THRESHOLD))
        floor_analysis[f"no_{criterion}"] = {
            "fraction_at_floor": round(frac, 4),
            "n": len(alive_arr),
        }
        print(f"  no_{criterion}: floor_frac={frac:.4f}", file=sys.stderr)

    # Pairwise ablations
    for entry in pair_results:
        pair_name = entry["pair_name"]
        path = Path(f"{pairwise_prefix}_{pair_name}.json")
        results = load_json(path)
        if results:
            alive_arr = np.array(extract_final_alive(results), dtype=float)
            frac = float(np.mean(alive_arr <= FLOOR_THRESHOLD))
            floor_analysis[pair_name] = {
                "fraction_at_floor": round(frac, 4),
                "n": len(alive_arr),
            }
            print(f"  {pair_name}: floor_frac={frac:.4f}", file=sys.stderr)

    return floor_analysis


def compute_bootstrap_ci(
    pair_results: list[dict],
    robust_synergy: list[dict],
    normal_alive: list[int],
    single_alive: dict[str, list[float]],
    pairwise_prefix: str,
) -> None:
    """Compute bootstrap CI for synergy (updates results in place)."""
    print("\n--- Bootstrap CI for synergy (2000 resamples) ---", file=sys.stderr)
    rng = np.random.default_rng(42)
    N_BOOT = 2000
    for entry, robust_entry in zip(pair_results, robust_synergy, strict=True):
        a, b = entry["pair"]
        if a not in single_alive or b not in single_alive:
            continue

        pair_name = entry["pair_name"]
        path = Path(f"{pairwise_prefix}_{pair_name}.json")
        results = load_json(path)
        if not results:
            continue
        ab_arr = np.array(extract_final_alive(results), dtype=float)
        normal_arr = np.array(normal_alive, dtype=float)
        a_arr = single_alive[a]
        b_arr = single_alive[b]

        boot_synergy = np.empty(N_BOOT)
        n = len(normal_arr)
        for i in range(N_BOOT):
            idx_n = rng.integers(0, len(normal_arr), size=n)
            idx_a = rng.integers(0, len(a_arr), size=n)
            idx_b = rng.integers(0, len(b_arr), size=n)
            idx_ab = rng.integers(0, len(ab_arr), size=n)
            bl = float(np.mean(normal_arr[idx_n]))
            dec_a = bl - float(np.mean(a_arr[idx_a]))
            dec_b = bl - float(np.mean(b_arr[idx_b]))
            dec_ab = bl - float(np.mean(ab_arr[idx_ab]))
            boot_synergy[i] = dec_ab - (dec_a + dec_b)

        ci_lo = float(np.percentile(boot_synergy, 2.5))
        ci_hi = float(np.percentile(boot_synergy, 97.5))
        entry["bootstrap_ci_95"] = [round(ci_lo, 2), round(ci_hi, 2)]
        robust_entry["bootstrap_ci_95"] = [round(ci_lo, 2), round(ci_hi, 2)]
        print(
            f"  ({a}, {b}): 95% CI = [{ci_lo:.2f}, {ci_hi:.2f}]",
            file=sys.stderr,
        )


def main():
    """Compute pairwise synergy scores and statistical tests."""
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

    baseline_mean, normal_alive = load_baseline(single_prefix, pairwise_prefix)

    single_alive = load_single_ablations(single_prefix)
    single_declines = calculate_declines(baseline_mean, single_alive)

    pair_results, robust_synergy = analyze_pairs(
        pairwise_prefix, baseline_mean, single_declines, single_alive
    )

    floor_analysis = analyze_floor_effects(
        normal_alive, single_alive, pair_results, pairwise_prefix
    )

    compute_bootstrap_ci(
        pair_results, robust_synergy, normal_alive, single_alive, pairwise_prefix
    )

    output = {
        "experiment": "pairwise_ablation",
        "baseline_mean": round(baseline_mean, 2),
        "n_per_condition": len(normal_alive),
        "pairs": pair_results,
        "robust_synergy": robust_synergy,
        "floor_analysis": floor_analysis,
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
