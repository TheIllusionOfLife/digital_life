"""Evolution evidence analysis addressing peer-review Concern #5.

Shows that evolution is more than neutral drift by providing:
1. Analytical heritability estimate from mutation parameters
2. Selection differential (genome diversity vs fitness correlation)
3. Genome drift trajectory divergence (normal vs no_evolution)
4. Per-cycle recovery rates (evo_on vs evo_off in cyclic environment)
5. Long-run alive count comparison (normal vs no_evolution)

Usage:
    uv run python scripts/analyze_evolution_evidence.py
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

from analyze_results import bootstrap_cliffs_delta_ci, cliffs_delta

EXP_DIR = Path("experiments")

# Mutation parameters from simulation config
POINT_RATE = 0.01
MUTATION_SCALE = 0.1
GENOME_LENGTH = 256


def load_json(filename: str) -> list[dict]:
    path = EXP_DIR / filename
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def analytical_heritability(results: list[dict]) -> dict:
    """Compute analytical h^2 from mutation params and standing variance.

    h^2 = 1 - V_mutation / (V_mutation + V_standing)
    where V_mutation = point_rate * genome_length * scale^2
    and V_standing is proxied by genome_diversity from the data.
    """
    mutation_variance = POINT_RATE * GENOME_LENGTH * MUTATION_SCALE**2

    # Use genome_diversity from final sample of each seed as standing variance
    standing_vars = []
    for r in results:
        samples = r.get("samples", [])
        if samples:
            standing_vars.append(samples[-1]["genome_diversity"])

    standing_var_values = np.array(standing_vars)
    mean_standing = float(np.mean(standing_var_values))
    h2 = 1.0 - mutation_variance / (mutation_variance + mean_standing)

    print(
        f"  Analytical h^2: V_mut={mutation_variance:.4f}, "
        f"V_stand={mean_standing:.4f}, h^2={h2:.4f}",
        file=sys.stderr,
    )

    return {
        "analysis": "analytical_heritability",
        "point_rate": POINT_RATE,
        "mutation_scale": MUTATION_SCALE,
        "genome_length": GENOME_LENGTH,
        "mutation_variance": round(mutation_variance, 6),
        "standing_variance_mean": round(mean_standing, 4),
        "standing_variance_median": round(float(np.median(standing_var_values)), 4),
        "h_squared": round(h2, 4),
    }


def selection_differential(results: list[dict]) -> dict:
    """Correlate final genome_diversity with final_alive_count (Spearman)."""
    diversity = []
    alive = []
    for r in results:
        samples = r.get("samples", [])
        if samples:
            diversity.append(samples[-1]["genome_diversity"])
            alive.append(r["final_alive_count"])

    diversity_arr = np.array(diversity)
    alive_arr = np.array(alive)
    rho, p_val = stats.spearmanr(diversity_arr, alive_arr)

    print(f"  Selection differential: rho={rho:.4f}, p={p_val:.6f}", file=sys.stderr)

    return {
        "analysis": "selection_differential",
        "n": len(diversity),
        "spearman_rho": round(float(rho), 4),
        "p_value": round(float(p_val), 6),
        "significant": bool(p_val < 0.05),
    }


def genome_drift_trajectories(normal: list[dict], no_evo: list[dict]) -> dict:
    """Compare mean_genome_drift time series between normal and no_evolution.

    Computes per-step population mean of drift, then tests divergence at
    the final time point with Mann-Whitney U.
    """

    def extract_drift_series(results: list[dict]) -> tuple[list[int], np.ndarray]:
        """Return (steps, drift_matrix) where drift_matrix[seed, step_idx]."""
        steps = [s["step"] for s in results[0]["samples"]]
        n_seeds = len(results)
        n_steps = len(steps)
        matrix = np.zeros((n_seeds, n_steps))
        for i, r in enumerate(results):
            for j, s in enumerate(r["samples"]):
                matrix[i, j] = s["mean_genome_drift"]
        return steps, matrix

    steps_n, drift_normal = extract_drift_series(normal)
    steps_e, drift_no_evo = extract_drift_series(no_evo)

    # Per-step population means
    mean_normal = drift_normal.mean(axis=0)
    mean_no_evo = drift_no_evo.mean(axis=0)

    # Final values per seed for statistical test
    final_normal = drift_normal[:, -1]
    final_no_evo = drift_no_evo[:, -1]
    u_stat, p_val = stats.mannwhitneyu(
        final_normal, final_no_evo, alternative="two-sided"
    )
    cliff_d = cliffs_delta(final_normal, final_no_evo)

    print(
        f"  Drift trajectories: U={u_stat:.1f}, p={p_val:.6f}, cliff={cliff_d:.3f}",
        file=sys.stderr,
    )

    return {
        "analysis": "genome_drift_trajectories",
        "n_steps": len(steps_n),
        "normal_final_drift_mean": round(float(np.mean(final_normal)), 6),
        "no_evo_final_drift_mean": round(float(np.mean(final_no_evo)), 6),
        "U": float(u_stat),
        "p_value": round(float(p_val), 6),
        "cliffs_delta": round(cliff_d, 4),
        "significant": bool(p_val < 0.05),
        "trajectory_normal_mean": [round(float(x), 6) for x in mean_normal],
        "trajectory_no_evo_mean": [round(float(x), 6) for x in mean_no_evo],
        "trajectory_steps": steps_n,
    }


def cyclic_recovery_rates(evo_on: list[dict], evo_off: list[dict]) -> dict:
    """Compare per-cycle recovery rates between evo_on and evo_off.

    With cycle_period=2000 and 10000 steps, phases alternate every 2000 steps:
    [0-2000) high, [2000-4000) low, [4000-6000) high, [6000-8000) low, [8000-10000) high

    Recovery = transition from low phase to high phase.
    Transitions at steps 4000 and 8000 (start of high after a low phase).
    Recovery rate = (alive_end_of_high - alive_start_of_high) / alive_start_of_high
    """
    sample_every = 100

    def get_alive_at_step(results: list[dict], step: int) -> np.ndarray:
        idx = step // sample_every - 1  # samples start at step 100
        values = []
        for r in results:
            samples = r.get("samples", [])
            if idx < len(samples):
                values.append(samples[idx]["alive_count"])
        return np.array(values, dtype=float)

    # Low->high transitions: after a low phase ends, high phase begins
    # High phases: [0,2000), [4000,6000), [8000,10000)
    # Low phases: [2000,4000), [6000,8000)
    # Recovery transitions: start of high phase after low = steps 4000, 8000
    transitions = [
        {"high_start": 4000, "high_end": 6000},
        {"high_start": 8000, "high_end": 10000},
    ]

    on_rates_all = []
    off_rates_all = []

    cycle_details = []
    for t in transitions:
        on_start = get_alive_at_step(evo_on, t["high_start"])
        on_end = get_alive_at_step(evo_on, t["high_end"])
        off_start = get_alive_at_step(evo_off, t["high_start"])
        off_end = get_alive_at_step(evo_off, t["high_end"])

        # Recovery rate: fractional change during high phase
        on_rates = np.where(on_start > 0, (on_end - on_start) / on_start, 0.0)
        off_rates = np.where(off_start > 0, (off_end - off_start) / off_start, 0.0)

        on_rates_all.extend(on_rates)
        off_rates_all.extend(off_rates)

        u_stat, p_val = stats.mannwhitneyu(on_rates, off_rates, alternative="greater")
        cycle_details.append(
            {
                "high_start": t["high_start"],
                "high_end": t["high_end"],
                "evo_on_rate_mean": round(float(np.mean(on_rates)), 4),
                "evo_off_rate_mean": round(float(np.mean(off_rates)), 4),
                "U": float(u_stat),
                "p_value": round(float(p_val), 6),
            }
        )
        print(
            f"  Cycle {t['high_start']}-{t['high_end']}: "
            f"on={np.mean(on_rates):.4f}, off={np.mean(off_rates):.4f}, "
            f"p={p_val:.6f}",
            file=sys.stderr,
        )

    # Pooled comparison
    on_all = np.array(on_rates_all)
    off_all = np.array(off_rates_all)
    u_pooled, p_pooled = stats.mannwhitneyu(on_all, off_all, alternative="greater")

    return {
        "analysis": "cyclic_recovery_rates",
        "per_cycle": cycle_details,
        "pooled_U": float(u_pooled),
        "pooled_p": round(float(p_pooled), 6),
        "pooled_significant": bool(p_pooled < 0.05),
    }


def long_run_comparison(normal: list[dict], no_evo: list[dict]) -> dict:
    """Compare final alive counts between evolution_long_normal and no_evolution."""
    normal_alive = np.array([r["final_alive_count"] for r in normal])
    no_evo_alive = np.array([r["final_alive_count"] for r in no_evo])

    u_stat, p_val = stats.mannwhitneyu(
        normal_alive, no_evo_alive, alternative="greater"
    )
    cliff_d = cliffs_delta(normal_alive, no_evo_alive)
    cliff_ci = bootstrap_cliffs_delta_ci(normal_alive, no_evo_alive)

    print(
        f"  Long-run alive: normal={np.mean(normal_alive):.1f}, "
        f"no_evo={np.mean(no_evo_alive):.1f}, "
        f"U={u_stat:.1f}, p={p_val:.6f}, cliff={cliff_d:.3f}",
        file=sys.stderr,
    )

    return {
        "analysis": "long_run_alive_count",
        "n_normal": len(normal_alive),
        "n_no_evo": len(no_evo_alive),
        "normal_mean": round(float(np.mean(normal_alive)), 2),
        "no_evo_mean": round(float(np.mean(no_evo_alive)), 2),
        "normal_median": round(float(np.median(normal_alive)), 2),
        "no_evo_median": round(float(np.median(no_evo_alive)), 2),
        "U": float(u_stat),
        "p_value": round(float(p_val), 6),
        "cliffs_delta": round(cliff_d, 4),
        "cliffs_delta_ci_lo": round(cliff_ci[0], 4),
        "cliffs_delta_ci_hi": round(cliff_ci[1], 4),
        "significant": bool(p_val < 0.05),
    }


def main():
    print("Loading data...", file=sys.stderr)
    normal_final = load_json("final_graph_normal.json")
    evo_long_normal = load_json("evolution_long_normal.json")
    evo_long_no_evo = load_json("evolution_long_no_evolution.json")
    cyclic_on = load_json("cyclic_cyclic_evo_on.json")
    cyclic_off = load_json("cyclic_cyclic_evo_off.json")

    print("\n1. Analytical heritability...", file=sys.stderr)
    h2_result = analytical_heritability(evo_long_normal)

    print("\n2. Selection differential...", file=sys.stderr)
    sel_result = selection_differential(normal_final)

    print("\n3. Genome drift trajectories...", file=sys.stderr)
    drift_result = genome_drift_trajectories(evo_long_normal, evo_long_no_evo)

    print("\n4. Cyclic recovery rates...", file=sys.stderr)
    cyclic_result = cyclic_recovery_rates(cyclic_on, cyclic_off)

    print("\n5. Long-run alive count comparison...", file=sys.stderr)
    longrun_result = long_run_comparison(evo_long_normal, evo_long_no_evo)

    output = {
        "analysis": "evolution_evidence",
        "description": (
            "Multiple lines of evidence that evolution in the system "
            "is adaptive, not merely neutral drift."
        ),
        "heritability": h2_result,
        "selection_differential": sel_result,
        "drift_trajectories": drift_result,
        "cyclic_recovery": cyclic_result,
        "long_run_comparison": longrun_result,
    }

    out_path = EXP_DIR / "evolution_evidence.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults written to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
