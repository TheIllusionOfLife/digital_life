"""Final criterion-ablation experiment with GraphMetabolism (2000 steps, n=30, test set).

Runs 8 conditions (normal baseline + 7 criterion ablations) with
metabolism_mode="graph", seeds 100-129, 2000 steps.

Usage:
    uv run python scripts/experiment_final_graph.py > experiments/final_graph_data.tsv
"""

import json
import time
from pathlib import Path

import digital_life
from experiment_manifest import write_manifest
from experiment_utils import CONDITIONS, log, make_config, run_single, safe_path

STEPS = 2000
SAMPLE_EVERY = 50
SEEDS = list(range(100, 130))  # test set: seeds 100-129, n=30

GRAPH_OVERRIDES = {"metabolism_mode": "graph"}


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


def main():
    log(f"Digital Life v{digital_life.version()}")
    log(f"Final GraphMetabolism experiment: {STEPS} steps, sample every {SAMPLE_EVERY}, "
        f"seeds {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})")
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)
    base_config = json.loads(make_config(SEEDS[0], GRAPH_OVERRIDES))
    write_manifest(
        out_dir / "final_graph_manifest.json",
        experiment_name="final_graph_ablation",
        steps=STEPS,
        sample_every=SAMPLE_EVERY,
        seeds=SEEDS,
        base_config=base_config,
        condition_overrides={name: {**GRAPH_OVERRIDES, **ov} for name, ov in CONDITIONS.items()},
        report_bindings=[
            {
                "result_id": "ablation_primary",
                "paper_ref": "tab:ablation",
                "source_files": [
                    "experiments/final_graph_data.tsv",
                    "experiments/final_graph_statistics.json",
                ],
            },
            {
                "result_id": "coupling_main",
                "paper_ref": "fig:coupling",
                "source_files": [
                    "experiments/final_graph_normal.json",
                    "experiments/coupling_analysis.json",
                ],
            },
        ],
    )

    print_header()
    total_start = time.perf_counter()

    for cond_name, overrides in CONDITIONS.items():
        log(f"--- Condition: {cond_name} ---")
        results = []
        cond_start = time.perf_counter()

        for seed in SEEDS:
            t0 = time.perf_counter()
            result = run_single(seed, STEPS, SAMPLE_EVERY, GRAPH_OVERRIDES, overrides)
            elapsed = time.perf_counter() - t0
            results.append(result)

            for s in result["samples"]:
                print_sample(cond_name, seed, s)

            final = result["final_alive_count"]
            log(f"  seed={seed:3d}  alive={final:4d}  {elapsed:.2f}s")

        cond_elapsed = time.perf_counter() - cond_start
        log(f"  Condition time: {cond_elapsed:.1f}s")

        raw_path = safe_path(out_dir, f"final_graph_{cond_name}.json")
        with open(raw_path, "w") as f:
            json.dump(results, f, indent=2)
        log(f"  Saved: {raw_path}")
        log("")

    total_elapsed = time.perf_counter() - total_start
    log(f"Total experiment time: {total_elapsed:.1f}s")


if __name__ == "__main__":
    main()
