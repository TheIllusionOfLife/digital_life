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
import os
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


def make_config(seed: int, overrides: dict) -> str:
    config = json.loads(digital_life.default_config_json())
    config["seed"] = seed
    config.update(TUNED_BASELINE)
    config.update(overrides)
    return json.dumps(config)


def run_single(seed: int, overrides: dict) -> dict:
    config_json = make_config(seed, overrides)
    result_json = digital_life.run_experiment_json(config_json, STEPS, SAMPLE_EVERY)
    return json.loads(result_json)


def extract_trajectory(result: dict) -> list[dict]:
    return result["samples"]


def print_header():
    cols = [
        "condition", "seed", "step",
        "alive_count", "energy_mean", "waste_mean", "boundary_mean",
        "birth_count", "death_count", "population_size",
        "mean_generation", "mean_genome_drift",
    ]
    print("\t".join(cols))


def print_sample(condition: str, seed: int, s: dict):
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


def summarize(condition: str, results: list[dict]):
    final_alive = [r["final_alive_count"] for r in results]
    last_samples = [r["samples"][-1] for r in results]

    alive_mean = sum(final_alive) / len(final_alive)
    energy_mean = sum(s["energy_mean"] for s in last_samples) / len(last_samples)
    boundary_mean = sum(s["boundary_mean"] for s in last_samples) / len(last_samples)
    waste_mean = sum(s["waste_mean"] for s in last_samples) / len(last_samples)
    total_births = sum(s["birth_count"] for r in results for s in r["samples"])
    total_deaths = sum(s["death_count"] for r in results for s in r["samples"])

    # Extinction rate: seeds where all organisms died
    extinct = sum(1 for a in final_alive if a == 0)

    return {
        "condition": condition,
        "seeds": len(results),
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
    log = lambda msg: print(msg, file=sys.stderr)

    log(f"Digital Life v{digital_life.version()}")
    log(f"Experiment: {STEPS} steps, sample every {SAMPLE_EVERY}, seeds {SEEDS[0]}-{SEEDS[-1]}")
    log("")

    # Create output directory
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

        # Save raw JSON per condition
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

    normal = next(s for s in summaries if s["condition"] == "normal")
    no_met = next(s for s in summaries if s["condition"] == "no_metabolism")
    no_bnd = next(s for s in summaries if s["condition"] == "no_boundary")

    # Check 1: Do organisms survive under normal conditions?
    if normal["alive_mean"] > 0:
        log(f"\n[PASS] Organisms survive: {normal['alive_mean']:.1f} alive at step 1000")
    else:
        log(f"\n[FAIL] All organisms extinct under normal conditions")

    # Check 2: Does disabling metabolism cause degradation?
    if normal["alive_mean"] > 0 and no_met["alive_mean"] < normal["alive_mean"]:
        ratio = no_met["alive_mean"] / normal["alive_mean"]
        log(f"[PASS] Metabolism ablation shows degradation: "
            f"{no_met['alive_mean']:.1f} vs {normal['alive_mean']:.1f} "
            f"({ratio:.1%} of normal)")
    else:
        log(f"[WARN] No clear metabolism ablation effect: "
            f"no_metab={no_met['alive_mean']:.1f} vs normal={normal['alive_mean']:.1f}")

    # Check 3: Does disabling boundary cause degradation?
    if normal["alive_mean"] > 0 and no_bnd["alive_mean"] < normal["alive_mean"]:
        ratio = no_bnd["alive_mean"] / normal["alive_mean"]
        log(f"[PASS] Boundary ablation shows degradation: "
            f"{no_bnd['alive_mean']:.1f} vs {normal['alive_mean']:.1f} "
            f"({ratio:.1%} of normal)")
    else:
        log(f"[WARN] No clear boundary ablation effect: "
            f"no_bound={no_bnd['alive_mean']:.1f} vs normal={normal['alive_mean']:.1f}")

    # Save summary JSON
    summary_path = out_dir / "1000step_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summaries, f, indent=2)
    log(f"\nSummary saved: {summary_path}")


if __name__ == "__main__":
    main()
