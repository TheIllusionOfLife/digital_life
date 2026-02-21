"""Implementation-invariance experiment for boundary/homeostasis criteria.

Compares criterion ablation outcomes across alternative implementation modes:
- boundary_mode: scalar_repair vs spatial_hull_feedback
- homeostasis_mode: nn_regulator vs setpoint_pid

Usage:
    uv run python scripts/experiment_invariance.py > experiments/invariance_data.tsv
"""

import json
from pathlib import Path

import digital_life
from experiment_common import log, make_config, print_header, run_condition_common
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
                "paper_ref": "fig:protocol_extensions",
                "source_files": [
                    "experiments/invariance_data.tsv",
                    "experiments/invariance_statistics.json",
                ],
            }
        ],
    )

    print_header()
    for cond_name, overrides in CONDITIONS.items():
        run_condition_common(
            cond_name,
            overrides,
            out_dir,
            filename_prefix="invariance_",
            seeds=SEEDS,
            steps=STEPS,
            sample_every=SAMPLE_EVERY,
        )


if __name__ == "__main__":
    main()
