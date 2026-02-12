"""1000-step feasibility experiment for Go/No-Go decision.

Runs 3 conditions:
  1. Normal   — all criteria enabled (baseline)
  2. No-Metab — metabolism disabled (ablation)
  3. No-Bound — boundary maintenance disabled (ablation)

Each condition is run with multiple seeds (calibration set: 0-9) to check
reproducibility and compute summary statistics.

Output: TSV data to stdout + summary report to stderr.
        Raw JSON saved to experiments/ directory.
"""

import json
import sys
import time
from pathlib import Path

import digital_life

STEPS = 1000
SAMPLE_EVERY = 10
SEEDS = list(range(10))  # calibration subset: seeds 0-9

# Tuned baseline from parameter sweep (2026-02-12)
TUNED_BASELINE = {
    "boundary_decay_base_rate": 0.001,
    "boundary_repair_rate": 0.05,
    "metabolic_viability_floor": 0.1,
    "crowding_neighbor_threshold": 50.0,
}

CONDITIONS = {
    "normal": {},
    "no_metabolism": {"enable_metabolism": False},
    "no_boundary": {"enable_boundary_maintenance": False},
}


def log(msg: str) -> None:
    """Write a message to stderr for progress reporting."""
    print(msg, file=sys.stderr)


def make_config(seed: int, overrides: dict) -> str:
    """Build a JSON config string with tuned baseline, seed, and overrides."""
    config = json.loads(digital_life.default_config_json())
    config["seed"] = seed
    config.update(TUNED_BASELINE)
    config.update(overrides)
    return json.dumps(config)


def run_single(seed: int, overrides: dict) -> dict:
    """Run a single experiment and return parsed results."""
    config_json = make_config(seed, overrides)
    result_json = digital_life.run_experiment_json(config_json, STEPS, SAMPLE_EVERY)
    return json.loads(result_json)


def print_header():
    """Print TSV column header to stdout."""
    cols = [
        "condition", "seed", "step",
        "alive_count", "energy_mean", "waste_mean", "boundary_mean",
        "birth_count", "death_count", "population_size",
        "mean_generation", "mean_genome_drift",
    ]
    print("\t".join(cols))


def print_sample(condition: str, seed: int, s: dict):
    """Print a single sample row as TSV to stdout."""
    vals = [
        condition, str(seed), str(s["step"]),
        str(s["alive_count"]),
        f"{s['energy_mean']:.4f}",
        f"{s['waste_mean']:.4f}",
        f"{s['boundary_mean']:.4f}",
        str(s["birth_count"]),
        str(s["death_count"]),
        str(s["population_size"]),
        f"{s['mean_generation']:.2f}",
        f"{s['mean_genome_drift']:.4f}",
    ]
    print("\t".join(vals))


def summarize(condition: str, results: list[dict]) -> dict | None:
    """Compute summary statistics for a condition across seeds.

    Returns None if results is empty.
    """
    if not results:
        return None

    results_with_samples = [r for r in results if r.get("samples")]
    if not results_with_samples:
        return None

    final_alive = [r["final_alive_count"] for r in results_with_samples]
    last_samples = [r["samples"][-1] for r in results_with_samples]
    n = len(last_samples)

    alive_mean = sum(final_alive) / n
    energy_mean = sum(s["energy_mean"] for s in last_samples) / n
    boundary_mean = sum(s["boundary_mean"] for s in last_samples) / n
    waste_mean = sum(s["waste_mean"] for s in last_samples) / n
    total_births = sum(s["birth_count"] for r in results_with_samples for s in r["samples"])
    total_deaths = sum(s["death_count"] for r in results_with_samples for s in r["samples"])

    extinct = sum(1 for a in final_alive if a == 0)

    return {
        "condition": condition,
        "seeds": n,
        "alive_mean": alive_mean,
        "alive_min": min(final_alive),
        "alive_max": max(final_alive),
        "extinct_count": extinct,
        "energy_mean": energy_mean,
        "boundary_mean": boundary_mean,
        "waste_mean": waste_mean,
        "total_births": total_births,
        "total_deaths": total_deaths,
    }


def main():
    log(f"Digital Life v{digital_life.version()}")
    log(f"Experiment: {STEPS} steps, sample every {SAMPLE_EVERY}, seeds {SEEDS[0]}-{SEEDS[-1]}")
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)

    all_results: dict[str, list[dict]] = {}
    print_header()

    for cond_name, overrides in CONDITIONS.items():
        log(f"--- Condition: {cond_name} ---")
        results = []
        for seed in SEEDS:
            t0 = time.perf_counter()
            result = run_single(seed, overrides)
            elapsed = time.perf_counter() - t0
            results.append(result)

            for s in result["samples"]:
                print_sample(cond_name, seed, s)

            final = result["final_alive_count"]
            log(f"  seed={seed:3d}  alive={final:4d}  {elapsed:.2f}s")

        all_results[cond_name] = results

        raw_path = out_dir / f"1000step_{cond_name}.json"
        with open(raw_path, "w") as f:
            json.dump(results, f, indent=2)
        log(f"  Saved: {raw_path}")
        log("")

    # Summary report
    log("=" * 60)
    log("SUMMARY (step=1000, averaged over seeds)")
    log("=" * 60)
    summaries = []
    for cond_name, results in all_results.items():
        s = summarize(cond_name, results)
        if s is None:
            log(f"\n[{cond_name}] SKIPPED — no valid results")
            continue
        summaries.append(s)
        log(f"\n[{s['condition']}]")
        log(f"  Final alive  : {s['alive_mean']:.1f} (min={s['alive_min']}, max={s['alive_max']})")
        log(f"  Extinction   : {s['extinct_count']}/{s['seeds']} seeds")
        log(f"  Energy mean  : {s['energy_mean']:.4f}")
        log(f"  Boundary mean: {s['boundary_mean']:.4f}")
        log(f"  Waste mean   : {s['waste_mean']:.4f}")
        log(f"  Total births : {s['total_births']}")
        log(f"  Total deaths : {s['total_deaths']}")

    # Go/No-Go assessment
    log("\n" + "=" * 60)
    log("GO/NO-GO ASSESSMENT")
    log("=" * 60)

    passed = True
    normal = next((s for s in summaries if s["condition"] == "normal"), None)
    no_met = next((s for s in summaries if s["condition"] == "no_metabolism"), None)
    no_bnd = next((s for s in summaries if s["condition"] == "no_boundary"), None)

    if normal is None or normal["alive_mean"] == 0:
        log("\n[FAIL] All organisms extinct under normal conditions")
        passed = False
    else:
        log(f"\n[PASS] Organisms survive: {normal['alive_mean']:.1f} alive at step {STEPS}")

        if no_met and no_met["alive_mean"] < normal["alive_mean"]:
            ratio = no_met["alive_mean"] / normal["alive_mean"]
            log(f"[PASS] Metabolism ablation shows degradation: "
                f"{no_met['alive_mean']:.1f} vs {normal['alive_mean']:.1f} "
                f"({ratio:.1%} of normal)")
        else:
            met_val = no_met["alive_mean"] if no_met else "N/A"
            log(f"[WARN] No clear metabolism ablation effect: "
                f"no_metab={met_val} vs normal={normal['alive_mean']:.1f}")
            passed = False

        if no_bnd and no_bnd["alive_mean"] < normal["alive_mean"]:
            ratio = no_bnd["alive_mean"] / normal["alive_mean"]
            log(f"[PASS] Boundary ablation shows degradation: "
                f"{no_bnd['alive_mean']:.1f} vs {normal['alive_mean']:.1f} "
                f"({ratio:.1%} of normal)")
        else:
            bnd_val = no_bnd["alive_mean"] if no_bnd else "N/A"
            log(f"[WARN] No clear boundary ablation effect: "
                f"no_bound={bnd_val} vs normal={normal['alive_mean']:.1f}")
            passed = False

    # Save summary JSON
    summary_path = out_dir / "1000step_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summaries, f, indent=2)
    log(f"\nSummary saved: {summary_path}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
