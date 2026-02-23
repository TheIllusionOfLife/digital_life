"""Analyze trait evolution experiment outputs.

Produces two analyses:
1. Trait trajectory over snapshot steps (mean ± SEM energy/boundary per condition).
2. Generation-stratified selection differential at final step (Cliff's δ, Mann-Whitney U).

Seed is the replication unit — per-seed means are aggregated, not per-organism values.

Usage:
    uv run python scripts/analyze_trait_evolution.py > experiments/trait_evolution_analysis.json
"""

from __future__ import annotations

import json
import math
from pathlib import Path


def load_json(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def compute_trajectory(results: list[dict], snapshot_steps: list[int]) -> dict:
    """Compute mean ± SEM energy and boundary over snapshot steps.

    SEM is computed across per-seed means (seed is the replication unit).
    """
    energy_by_step: dict[int, list[float]] = {s: [] for s in snapshot_steps}
    boundary_by_step: dict[int, list[float]] = {s: [] for s in snapshot_steps}

    for result in results:
        snapshots = result.get("organism_snapshots") or []
        for snap in snapshots:
            step = int(snap["step"])
            if step not in energy_by_step:
                continue
            organisms = snap.get("organisms") or []
            if not organisms:
                continue
            energies = [float(o.get("energy", 0.0)) for o in organisms]
            boundaries = [float(o.get("boundary_integrity", 0.0)) for o in organisms]
            energy_by_step[step].append(sum(energies) / len(energies))
            boundary_by_step[step].append(sum(boundaries) / len(boundaries))

    # Filter to steps that actually have data
    steps_with_data = [s for s in snapshot_steps if energy_by_step[s]]
    energy_means = []
    energy_sems = []
    boundary_means = []
    boundary_sems = []

    for step in steps_with_data:
        e_vals = energy_by_step[step]
        b_vals = boundary_by_step[step]
        n = len(e_vals)
        e_mean = sum(e_vals) / n
        b_mean = sum(b_vals) / n
        if n >= 2:
            e_std = math.sqrt(sum((v - e_mean) ** 2 for v in e_vals) / (n - 1))
            b_std = math.sqrt(sum((v - b_mean) ** 2 for v in b_vals) / (n - 1))
            e_sem = e_std / math.sqrt(n)
            b_sem = b_std / math.sqrt(n)
        else:
            e_sem = 0.0
            b_sem = 0.0

        energy_means.append(round(e_mean, 4))
        energy_sems.append(round(e_sem, 4))
        boundary_means.append(round(b_mean, 4))
        boundary_sems.append(round(b_sem, 4))

    return {
        "steps": steps_with_data,
        "energy_mean": energy_means,
        "energy_sem": energy_sems,
        "boundary_mean": boundary_means,
        "boundary_sem": boundary_sems,
    }


def mann_whitney_u(x: list[float], y: list[float]) -> tuple[float, float]:
    """Two-sample Mann-Whitney U test. Returns (U_statistic, p_value two-tailed).

    Uses exact U and normal approximation for p-value.
    """
    n1, n2 = len(x), len(y)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0

    u_stat = 0.0
    for xi in x:
        for yj in y:
            if xi > yj:
                u_stat += 1.0
            elif xi == yj:
                u_stat += 0.5

    # Normal approximation
    mean_u = n1 * n2 / 2.0
    # Standard tie-free variance; ties are negligible for continuous float energy values.
    std_u = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12.0)
    if std_u == 0:
        return u_stat, 1.0

    z = (u_stat - mean_u) / std_u
    # Two-tailed p-value using complementary error function approximation
    p_value = 2.0 * (1.0 - _norm_cdf(abs(z)))
    return u_stat, p_value


def _norm_cdf(z: float) -> float:
    """Standard normal CDF using Abramowitz & Stegun approximation (|error| < 7.5e-8)."""
    if z < 0:
        return 1.0 - _norm_cdf(-z)
    t = 1.0 / (1.0 + 0.2316419 * z)
    poly = t * (0.319381530
                + t * (-0.356563782
                       + t * (1.781477937
                              + t * (-1.821255978
                                     + t * 1.330274429))))
    return 1.0 - (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * z * z) * poly


def cliffs_delta(x: list[float], y: list[float]) -> float:
    """Compute Cliff's delta: signed effect size (positive = x > y stochastically)."""
    n1, n2 = len(x), len(y)
    if n1 == 0 or n2 == 0:
        return 0.0
    concordant = sum(1 for xi in x for yj in y if xi > yj)
    discordant = sum(1 for xi in x for yj in y if xi < yj)
    return (concordant - discordant) / (n1 * n2)


def compute_selection_differential(results: list[dict], final_step: int) -> dict:
    """Compute generation-stratified selection differential at final_step.

    For each seed: split organisms at final_step into top/bottom 25% by generation.
    Skip seeds with < 5 organisms in either quartile.
    Aggregate via Mann-Whitney U at the seed level.
    """
    per_seed_high_gen_energy: list[float] = []
    per_seed_low_gen_energy: list[float] = []

    for result in results:
        snapshots = result.get("organism_snapshots") or []
        final_snap = None
        for snap in snapshots:
            if int(snap["step"]) == final_step:
                final_snap = snap
                break
        if final_snap is None:
            continue

        organisms = final_snap.get("organisms") or []
        if len(organisms) < 20:  # Need at least 5 per quartile (q25 = n // 4, so n >= 20)
            continue

        # Sort by generation
        sorted_orgs = sorted(organisms, key=lambda o: float(o.get("generation", 0)))
        n = len(sorted_orgs)
        q25 = max(1, n // 4)  # bottom 25%

        low_gen_orgs = sorted_orgs[:q25]
        high_gen_orgs = sorted_orgs[n - q25:]  # top 25%

        if len(low_gen_orgs) < 5 or len(high_gen_orgs) < 5:
            continue

        low_energy = sum(float(o.get("energy", 0.0)) for o in low_gen_orgs) / len(low_gen_orgs)
        high_energy = sum(float(o.get("energy", 0.0)) for o in high_gen_orgs) / len(high_gen_orgs)

        per_seed_high_gen_energy.append(high_energy)
        per_seed_low_gen_energy.append(low_energy)

    n_seeds_used = len(per_seed_high_gen_energy)

    if n_seeds_used < 2:
        return {
            "per_seed_high_gen_energy": per_seed_high_gen_energy,
            "per_seed_low_gen_energy": per_seed_low_gen_energy,
            "cliff_delta": 0.0,
            "p_value": 1.0,
            "n_seeds_used": n_seeds_used,
        }

    delta = cliffs_delta(per_seed_high_gen_energy, per_seed_low_gen_energy)
    _u_stat, p_value = mann_whitney_u(per_seed_high_gen_energy, per_seed_low_gen_energy)

    return {
        "per_seed_high_gen_energy": [round(v, 4) for v in per_seed_high_gen_energy],
        "per_seed_low_gen_energy": [round(v, 4) for v in per_seed_low_gen_energy],
        "cliff_delta": round(delta, 4),
        "p_value": round(p_value, 6),
        "n_seeds_used": n_seeds_used,
    }


def main() -> None:
    exp_dir = Path(__file__).resolve().parent.parent / "experiments"
    snapshot_steps = [2000, 5000, 8000, 10000]
    final_step = 10000

    conditions = {
        "normal": exp_dir / "trait_evo_normal.json",
        "no_evo": exp_dir / "trait_evo_no_evo.json",
    }

    trajectory: dict[str, dict] = {}
    selection_differential: dict[str, dict] = {}

    for cond_name, path in conditions.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing: {path}")
        results = load_json(path)
        trajectory[cond_name] = compute_trajectory(results, snapshot_steps)
        selection_differential[cond_name] = compute_selection_differential(results, final_step)

    output = {
        "trajectory": trajectory,
        "selection_differential": selection_differential,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
