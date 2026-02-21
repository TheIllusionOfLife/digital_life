"""Ecology stressor experiment beyond static resource scaling.

Introduces temporal environmental stressors:
- abrupt resource-regeneration shift
- cyclic boom/bust resource phases
and compares with/without evolution under stress.

Usage:
    uv run python scripts/experiment_ecology_stress.py > experiments/ecology_stress_data.tsv
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
    "normal": {**GRAPH_OVERRIDES},
    "resource_shift": {
        **GRAPH_OVERRIDES,
        "environment_shift_step": 1000,
        "environment_shift_resource_rate": 0.003,
    },
    "cyclic_stress": {
        **GRAPH_OVERRIDES,
        "environment_cycle_period": 200,
        "environment_cycle_low_rate": 0.003,
    },
    "cyclic_stress_no_evolution": {
        **GRAPH_OVERRIDES,
        "environment_cycle_period": 200,
        "environment_cycle_low_rate": 0.003,
        "enable_evolution": False,
    },
}


def main() -> None:
    log(f"Digital Life v{digital_life.version()}")
    log(
        f"Ecology stress: {STEPS} steps, sample every {SAMPLE_EVERY}, "
        f"seeds {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)})"
    )
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)

    base_config = json.loads(make_config(SEEDS[0], GRAPH_OVERRIDES))
    write_manifest(
        out_dir / "ecology_stress_manifest.json",
        experiment_name="ecology_stress",
        steps=STEPS,
        sample_every=SAMPLE_EVERY,
        seeds=SEEDS,
        base_config=base_config,
        condition_overrides=CONDITIONS,
        report_bindings=[
            {
                "result_id": "ecology_stress",
                "paper_ref": "fig:ecology_stress",
                "source_files": [
                    "experiments/ecology_stress_data.tsv",
                    "experiments/ecology_stress_statistics.json",
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
            filename_prefix="ecology_stress_",
            seeds=SEEDS,
            steps=STEPS,
            sample_every=SAMPLE_EVERY,
        )


if __name__ == "__main__":
    main()
