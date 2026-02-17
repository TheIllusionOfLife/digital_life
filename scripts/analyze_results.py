"""Statistical analysis for criterion-ablation experiments.

Computes Mann-Whitney U tests, Cohen's d / Cliff's delta effect sizes,
AUC (area under alive-count curve), median lifespan, and
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


def extract_auc(results: list[dict]) -> np.ndarray:
    """Compute AUC (area under alive-count curve) for each seed using trapezoidal rule."""
    aucs = []
    for r in results:
        if "samples" not in r:
            continue
        steps = [s["step"] for s in r["samples"]]
        counts = [s["alive_count"] for s in r["samples"]]
        if len(steps) >= 2:
            aucs.append(float(np.trapezoid(counts, steps)))
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


def cohens_d_ci(a: np.ndarray, b: np.ndarray, alpha: float = 0.05) -> tuple[float, float]:
    """Compute Wald-type CI for Cohen's d with approximate standard error.

    Uses the Hedges & Olkin (1985) approximation for the SE of d.
    """
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return (0.0, 0.0)
    d = cohens_d(a, b)
    df = na + nb - 2
    se_d = np.sqrt((na + nb) / (na * nb) + d**2 / (2 * (na + nb - 2)))
    t_lo = stats.t.ppf(alpha / 2, df)
    t_hi = stats.t.ppf(1 - alpha / 2, df)
    return (float(d + t_lo * se_d), float(d + t_hi * se_d))


def bootstrap_cliffs_delta_ci(
    a: np.ndarray, b: np.ndarray, n_boot: int = 2000, alpha: float = 0.05
) -> tuple[float, float]:
    """Compute bootstrap CI for Cliff's delta using percentile method."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return (0.0, 0.0)
    rng = np.random.default_rng(42)
    boot_deltas = np.empty(n_boot)
    for i in range(n_boot):
        a_boot = a[rng.integers(0, na, size=na)]
        b_boot = b[rng.integers(0, nb, size=nb)]
        boot_deltas[i] = cliffs_delta(a_boot, b_boot)
    lo = float(np.percentile(boot_deltas, 100 * alpha / 2))
    hi = float(np.percentile(boot_deltas, 100 * (1 - alpha / 2)))
    return (lo, hi)


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    """Compute Cliff's delta (nonparametric effect size).

    delta = (#{a_i > b_j} - #{a_i < b_j}) / (n_a * n_b)
    Range: [-1, 1]. Positive means group a tends to be larger.
    """
    na, nb = len(a), len(b)
    if na == 0 or nb == 0:
        return 0.0
    more = 0
    less = 0
    for ai in a:
        for bj in b:
            if ai > bj:
                more += 1
            elif ai < bj:
                less += 1
    return (more - less) / (na * nb)


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


def distribution_stats(arr: np.ndarray) -> dict:
    """Compute median, IQR, mean, and SD for an array."""
    if len(arr) == 0:
        return {"median": 0.0, "q25": 0.0, "q75": 0.0, "mean": 0.0, "std": 0.0}
    return {
        "median": float(np.median(arr)),
        "q25": float(np.percentile(arr, 25)),
        "q75": float(np.percentile(arr, 75)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
    }


def jonckheere_terpstra(groups: list[np.ndarray]) -> tuple[float, float]:
    """Jonckheere-Terpstra trend test for ordered groups.

    Tests whether there is a monotonic trend across ordered groups.
    Returns (JT statistic, two-sided p-value via normal approximation).
    """
    k = len(groups)
    if k < 2:
        return (0.0, 1.0)
    # JT statistic: sum of Mann-Whitney U for all i<j pairs
    jt = 0.0
    for i in range(k):
        for j in range(i + 1, k):
            for xi in groups[i]:
                for yj in groups[j]:
                    if xi > yj:
                        jt += 1.0
                    elif xi == yj:
                        jt += 0.5
    # Expected value and variance under null (no-tie approximation).
    # Tie correction omitted: with continuous-valued alive counts across
    # 30 seeds per group, exact ties are rare and impact is negligible.
    n_total = sum(len(g) for g in groups)
    ns = [len(g) for g in groups]
    e_jt = (n_total ** 2 - sum(n ** 2 for n in ns)) / 4.0
    var_num = n_total ** 2 * (2 * n_total + 3) - sum(n ** 2 * (2 * n + 3) for n in ns)
    var_jt = var_num / 72.0
    if var_jt <= 0:
        return (jt, 1.0)
    z = (jt - e_jt) / np.sqrt(var_jt)
    p_value = 2.0 * (1.0 - stats.norm.cdf(abs(z)))
    return (float(jt), float(p_value))


def analyze_graded(exp_dir: Path) -> dict | None:
    """Analyze graded ablation: dose-response + Jonckheere-Terpstra trend test."""
    levels = [1.0, 0.75, 0.5, 0.25, 0.0]
    groups = []
    level_stats = []

    for level in levels:
        path = exp_dir / f"graded_graded_{level:.2f}.json"
        if not path.exists():
            print(f"  SKIP graded {level}: {path} not found", file=sys.stderr)
            return None
        with open(path) as f:
            results = json.load(f)
        alive = extract_final_alive(results)
        groups.append(alive)
        level_stats.append({
            "level": level,
            "n": len(alive),
            **distribution_stats(alive),
        })

    jt_stat, jt_p = jonckheere_terpstra(groups)
    # Also pairwise: each level vs full (1.0)
    baseline = groups[0]
    pairwise = []
    for i, level in enumerate(levels[1:], 1):
        u_stat, p_val = stats.mannwhitneyu(baseline, groups[i], alternative="greater")
        d = cohens_d(baseline, groups[i])
        pairwise.append({
            "level": level,
            "U": float(u_stat),
            "p_raw": float(p_val),
            "cohens_d": round(d, 4),
        })

    print(f"Graded ablation: JT={jt_stat:.1f}, p={jt_p:.6f}", file=sys.stderr)
    return {
        "experiment": "graded_ablation",
        "levels": level_stats,
        "jonckheere_terpstra_stat": round(jt_stat, 2),
        "jonckheere_terpstra_p": round(jt_p, 6),
        "monotonic_trend": bool(jt_p < 0.05),
        "pairwise_vs_full": pairwise,
    }


def analyze_cyclic(exp_dir: Path) -> dict | None:
    """Analyze cyclic environment: per-cycle recovery comparison."""
    conditions = ["cyclic_evo_on", "cyclic_evo_off"]
    cond_data = {}
    for cond in conditions:
        path = exp_dir / f"cyclic_{cond}.json"
        if not path.exists():
            print(f"  SKIP cyclic {cond}: {path} not found", file=sys.stderr)
            return None
        with open(path) as f:
            cond_data[cond] = json.load(f)

    on_alive = extract_final_alive(cond_data["cyclic_evo_on"])
    off_alive = extract_final_alive(cond_data["cyclic_evo_off"])
    u_stat, p_val = stats.mannwhitneyu(on_alive, off_alive, alternative="greater")
    d = cohens_d(on_alive, off_alive)
    cliff_d = cliffs_delta(on_alive, off_alive)

    print(f"Cyclic: U={u_stat:.1f}, p={p_val:.6f}, d={d:.3f}", file=sys.stderr)
    return {
        "experiment": "cyclic_environment",
        "evo_on_dist": distribution_stats(on_alive),
        "evo_off_dist": distribution_stats(off_alive),
        "U": float(u_stat),
        "p_raw": round(float(p_val), 6),
        "cohens_d": round(d, 4),
        "cliffs_delta": round(cliff_d, 4),
        "significant": bool(p_val < 0.05),
    }


def analyze_sham(exp_dir: Path) -> dict | None:
    """Analyze sham ablation: expect non-significant difference."""
    conditions = ["sham_on", "sham_off"]
    cond_data = {}
    for cond in conditions:
        path = exp_dir / f"sham_{cond}.json"
        if not path.exists():
            print(f"  SKIP sham {cond}: {path} not found", file=sys.stderr)
            return None
        with open(path) as f:
            cond_data[cond] = json.load(f)

    on_alive = extract_final_alive(cond_data["sham_on"])
    off_alive = extract_final_alive(cond_data["sham_off"])
    u_stat, p_val = stats.mannwhitneyu(on_alive, off_alive, alternative="two-sided")
    d = cohens_d(on_alive, off_alive)

    print(f"Sham: U={u_stat:.1f}, p={p_val:.6f}, d={d:.3f}", file=sys.stderr)
    return {
        "experiment": "sham_ablation",
        "sham_on_dist": distribution_stats(on_alive),
        "sham_off_dist": distribution_stats(off_alive),
        "U": float(u_stat),
        "p_raw": round(float(p_val), 6),
        "cohens_d": round(d, 4),
        "non_significant": bool(p_val > 0.05),
    }


def load_experiment_data(prefix: str) -> tuple[list[dict], dict[str, list[dict]]]:
    """Load normal baseline and all condition data."""
    normal_results = load_condition(prefix, "normal")
    if not normal_results:
        print("ERROR: no normal baseline results found", file=sys.stderr)
        sys.exit(1)

    condition_data = {}
    for condition in CONDITIONS:
        condition_data[condition] = load_condition(prefix, condition)

    return normal_results, condition_data


def compute_condition_stats(
    condition: str,
    normal_alive: np.ndarray,
    normal_auc: np.ndarray,
    normal_median_lifespan: float,
    ablated_results: list[dict],
) -> dict | None:
    """Compute stats for a single ablation condition vs normal baseline."""
    ablated_alive = extract_final_alive(ablated_results)
    n_ablated = len(ablated_alive)

    if n_ablated < 2:
        print(f"  {condition}: SKIPPED (n={n_ablated} < 2)", file=sys.stderr)
        return None

    u_stat, p_value = stats.mannwhitneyu(
        normal_alive, ablated_alive, alternative="greater"
    )
    d = cohens_d(normal_alive, ablated_alive)
    d_ci = cohens_d_ci(normal_alive, ablated_alive)
    cliff_d = cliffs_delta(normal_alive, ablated_alive)
    cliff_ci = bootstrap_cliffs_delta_ci(normal_alive, ablated_alive)
    ablated_auc = extract_auc(ablated_results)
    ablated_median_lifespan = extract_median_lifespan(ablated_results)

    print(
        f"  {condition}: U={u_stat:.1f}, p={p_value:.6f}, d={d:.3f}, "
        f"cliff={cliff_d:.3f}, "
        f"normal={np.mean(normal_alive):.1f}, ablated={np.mean(ablated_alive):.1f}",
        file=sys.stderr,
    )

    return {
        "condition": condition,
        "n_normal": len(normal_alive),
        "n_ablated": n_ablated,
        "normal_mean": float(np.mean(normal_alive)),
        "ablation_mean": float(np.mean(ablated_alive)),
        "normal_dist": distribution_stats(normal_alive),
        "ablation_dist": distribution_stats(ablated_alive),
        "U": float(u_stat),
        "p_raw": float(p_value),
        "cohens_d": round(d, 4),
        "cohens_d_ci_lo": round(d_ci[0], 4),
        "cohens_d_ci_hi": round(d_ci[1], 4),
        "cliffs_delta": round(cliff_d, 4),
        "cliffs_delta_ci_lo": round(cliff_ci[0], 4),
        "cliffs_delta_ci_hi": round(cliff_ci[1], 4),
        "normal_auc_mean": round(float(np.mean(normal_auc)), 2),
        "ablation_auc_mean": round(float(np.mean(ablated_auc)), 2),
        "normal_median_lifespan": round(normal_median_lifespan, 1),
        "ablation_median_lifespan": round(ablated_median_lifespan, 1),
    }


def perform_main_analysis(
    normal_results: list[dict],
    condition_data: dict[str, list[dict]],
    alpha: float = 0.05
) -> tuple[list[dict], int]:
    """Perform statistical analysis for all main ablation conditions."""
    normal_alive = extract_final_alive(normal_results)
    normal_auc = extract_auc(normal_results)
    normal_median_lifespan = extract_median_lifespan(normal_results)

    comparisons = []
    raw_p_values = []

    for condition in CONDITIONS:
        results = condition_data[condition]
        if not results:
            print(f"  {condition}: SKIPPED (no data)", file=sys.stderr)
            continue

        stats_res = compute_condition_stats(
            condition, normal_alive, normal_auc, normal_median_lifespan, results
        )
        if stats_res:
            comparisons.append(stats_res)
            raw_p_values.append(stats_res["p_raw"])

    # Apply Holm-Bonferroni correction
    corrected = holm_bonferroni(raw_p_values)
    significant_count = 0
    for comp, p_corr in zip(comparisons, corrected, strict=True):
        comp["p_corrected"] = round(p_corr, 6)
        comp["significant"] = bool(p_corr < alpha)
        if comp["significant"]:
            significant_count += 1

    return comparisons, significant_count


def perform_short_horizon_analysis(
    normal_results: list[dict],
    condition_data: dict[str, list[dict]],
    step: int = 500,
    alpha: float = 0.05
) -> list[dict]:
    """Perform short-horizon analysis (T=500) for individual-level viability."""
    normal_alive_500 = extract_alive_at_step(normal_results, step)
    short_horizon = []
    short_raw_p = []

    for condition in CONDITIONS:
        results = condition_data[condition]
        if not results:
            continue
        ablated_alive_500 = extract_alive_at_step(results, step)
        if len(ablated_alive_500) < 2:
            continue

        u_stat_500, p_500 = stats.mannwhitneyu(
            normal_alive_500, ablated_alive_500, alternative="greater"
        )
        short_horizon.append({
            "condition": condition,
            "normal_mean_500": round(float(np.mean(normal_alive_500)), 2),
            "ablation_mean_500": round(float(np.mean(ablated_alive_500)), 2),
            "U": float(u_stat_500),
            "p_raw": float(p_500),
        })
        short_raw_p.append(p_500)

    short_corrected = holm_bonferroni(short_raw_p)
    for sh, p_corr in zip(short_horizon, short_corrected, strict=True):
        sh["p_corrected"] = round(p_corr, 6)
        sh["significant"] = bool(p_corr < alpha)

    print(f"\nShort-horizon (T={step}):", file=sys.stderr)
    for sh in short_horizon:
        status = "SIG" if sh["significant"] else "n.s."
        print(
            f"  [{status}] {sh['condition']}: mean={sh['ablation_mean_500']:.1f}, "
            f"p_corr={sh['p_corrected']:.6f}",
            file=sys.stderr,
        )

    return short_horizon


def generate_report(
    n_normal: int,
    alpha: float,
    significant_count: int,
    comparisons: list[dict],
    short_horizon_step: int,
    short_horizon: list[dict],
    graded_result: dict | None,
    cyclic_result: dict | None,
    sham_result: dict | None,
) -> dict:
    """Construct the final analysis report dictionary."""
    output = {
        "experiment": "criterion_ablation",
        "n_per_condition": n_normal,
        "alpha": alpha,
        "correction": "holm_bonferroni",
        "significant_count": significant_count,
        "total_comparisons": len(comparisons),
        "comparisons": comparisons,
        "short_horizon": {
            "step": short_horizon_step,
            "comparisons": short_horizon,
        },
    }
    if graded_result:
        output["graded_ablation"] = graded_result
    if cyclic_result:
        output["cyclic_environment"] = cyclic_result
    if sham_result:
        output["sham_ablation"] = sham_result
    return output


def print_summary(comparisons: list[dict], significant_count: int) -> None:
    """Print a summary of significant findings to stderr."""
    print(f"\nSignificant: {significant_count}/{len(comparisons)}", file=sys.stderr)
    for comp in comparisons:
        status = "SIG" if comp["significant"] else "n.s."
        print(
            f"  [{status}] {comp['condition']}: p_corr={comp['p_corrected']:.6f}, "
            f"d={comp['cohens_d']:.3f}, cliff={comp['cliffs_delta']:.3f}",
            file=sys.stderr,
        )


def main():
    """Analyze criterion-ablation results with statistical tests and effect sizes."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/analyze_results.py <prefix>", file=sys.stderr)
        print("  e.g. python scripts/analyze_results.py experiments/final", file=sys.stderr)
        sys.exit(1)

    prefix = sys.argv[1]
    alpha = 0.05

    normal_results, condition_data = load_experiment_data(prefix)

    normal_alive = extract_final_alive(normal_results)
    n_normal = len(normal_alive)
    print(f"Normal baseline: n={n_normal}, mean={np.mean(normal_alive):.1f}", file=sys.stderr)

    comparisons, significant_count = perform_main_analysis(normal_results, condition_data, alpha)

    short_horizon_step = 500
    short_horizon = perform_short_horizon_analysis(
        normal_results, condition_data, short_horizon_step, alpha
    )

    # ── Extended analyses: graded, cyclic, sham ──
    exp_dir = Path(prefix).resolve().parent
    graded_result = analyze_graded(exp_dir)
    cyclic_result = analyze_cyclic(exp_dir)
    sham_result = analyze_sham(exp_dir)

    output = generate_report(
        n_normal,
        alpha,
        significant_count,
        comparisons,
        short_horizon_step,
        short_horizon,
        graded_result,
        cyclic_result,
        sham_result,
    )

    print(json.dumps(output, indent=2))
    print_summary(comparisons, significant_count)


if __name__ == "__main__":
    main()
