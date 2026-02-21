"""Implementation-invariance experiment for boundary/homeostasis criteria.

Compares criterion ablation outcomes across alternative implementation modes:
- boundary_mode: scalar_repair vs spatial_hull_feedback
- homeostasis_mode: nn_regulator vs setpoint_pid

Usage:
    uv run python scripts/experiment_invariance.py > experiments/invariance_data.tsv
"""

import json
import time
from pathlib import Path

import digital_life
from experiment_common import log, make_config, print_header, print_sample, run_single
from experiment_manifest import write_manifest

STEPS = 2000
SAMPLE_EVERY = 50
SEEDS = list(range(100, 130))
GRAPH_OVERRIDES = {"metabolism_mode": "graph"}

CONDITIONS = {
    "baseline_default": {**GRAPH_OVERRIDES},
    "no_boundary_default": {**GRAPH_OVERRIDES, "enable_boundary_maintenance": False},
    "no_boundary_alt_mode": {
        **GRAPH_OVERRIDES,
        "boundary_mode": "spatial_hull_feedback",
        "enable_boundary_maintenance": False,
    },
    "no_homeostasis_default": {**GRAPH_OVERRIDES, "enable_homeostasis": False},
    "no_homeostasis_alt_mode": {
        **GRAPH_OVERRIDES,
        "homeostasis_mode": "setpoint_pid",
        "enable_homeostasis": False,
    },
    "baseline_alt_modes": {
        **GRAPH_OVERRIDES,
        "boundary_mode": "spatial_hull_feedback",
        "homeostasis_mode": "setpoint_pid",
    },
}


def run_condition(cond_name: str, overrides: dict, out_dir: Path) -> None:
    log(f"--- Condition: {cond_name} ---")
    start = time.perf_counter()
    results = []

    for seed in SEEDS:
        t0 = time.perf_counter()
        result = run_single(seed, overrides, steps=STEPS, sample_every=SAMPLE_EVERY)
        elapsed = time.perf_counter() - t0
        results.append(result)

        for sample in result["samples"]:
            print_sample(cond_name, seed, sample)

        log(f"  seed={seed:3d}  alive={result['final_alive_count']:4d}  {elapsed:.2f}s")

    with open(out_dir / f"invariance_{cond_name}.json", "w") as f:
        json.dump(results, f, indent=2)

    log(f"  Condition time: {time.perf_counter() - start:.1f}s")
    log("")


def main() -> None:
    log(f"Digital Life v{digital_life.version()}")
    log(
        f"Implementation invariance: {STEPS} steps, sample every {SAMPLE_EVERY}, "
        f"seeds {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})"
    )
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)

    base_config = json.loads(make_config(SEEDS[0], GRAPH_OVERRIDES))
    write_manifest(
        out_dir / "invariance_manifest.json",
        experiment_name="implementation_invariance",
        steps=STEPS,
        sample_every=SAMPLE_EVERY,
        seeds=SEEDS,
        base_config=base_config,
        condition_overrides=CONDITIONS,
        report_bindings=[
            {
                "result_id": "implementation_invariance",
                "paper_ref": "fig:invariance",
                "source_files": [
                    "experiments/invariance_data.tsv",
                    "experiments/invariance_statistics.json",
                ],
            }
        ],
    )

    print_header()
    total_start = time.perf_counter()
    for cond_name, overrides in CONDITIONS.items():
        run_condition(cond_name, overrides, out_dir)
    log(f"Total experiment time: {time.perf_counter() - total_start:.1f}s")


if __name__ == "__main__":
    main()
