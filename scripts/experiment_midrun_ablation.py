"""Mid-run vs. step-0 criterion ablation experiment.

Compares immediate ablation (step 0) against delayed ablation after system
stabilization (default step 1000) for all seven criteria.

Usage:
    uv run python scripts/experiment_midrun_ablation.py > experiments/midrun_ablation_data.tsv
"""

import json
from pathlib import Path

import digital_life
from experiment_common import (
    CRITERION_TO_FLAG,
    log,
    make_config,
    print_header,
    run_condition_common,
)
from experiment_manifest import write_manifest

STEPS = 2000
SAMPLE_EVERY = 50
SEEDS = list(range(100, 130))
MIDRUN_STEP = 1000
GRAPH_OVERRIDES = {"metabolism_mode": "graph"}


def build_conditions() -> dict[str, dict]:
    conditions: dict[str, dict] = {"normal": {**GRAPH_OVERRIDES}}
    for criterion, flag in CRITERION_TO_FLAG.items():
        conditions[f"no_{criterion}_step0"] = {**GRAPH_OVERRIDES, flag: False}
        conditions[f"no_{criterion}_midrun"] = {
            **GRAPH_OVERRIDES,
            "ablation_step": MIDRUN_STEP,
            "ablation_targets": [criterion],
        }
    return conditions


def main() -> None:
    log(f"Digital Life v{digital_life.version()}")
    log(
        f"Mid-run ablation: {STEPS} steps, sample every {SAMPLE_EVERY}, "
        f"seeds {SEEDS[0]}-{SEEDS[-1]} (n={len(SEEDS)}), mid-run step={MIDRUN_STEP}"
    )
    log("")

    out_dir = Path(__file__).resolve().parent.parent / "experiments"
    out_dir.mkdir(exist_ok=True)
    conditions = build_conditions()

    base_config = json.loads(make_config(SEEDS[0], GRAPH_OVERRIDES))
    write_manifest(
        out_dir / "midrun_ablation_manifest.json",
        experiment_name="midrun_ablation",
        steps=STEPS,
        sample_every=SAMPLE_EVERY,
        seeds=SEEDS,
        base_config=base_config,
        condition_overrides=conditions,
        report_bindings=[
            {
                "result_id": "midrun_ablation",
                "paper_ref": "fig:protocol_extensions",
                "source_files": [
                    "experiments/midrun_ablation_data.tsv",
                    "experiments/midrun_ablation_statistics.json",
                ],
            }
        ],
    )

    print_header()
    for cond_name, overrides in conditions.items():
        run_condition_common(
            cond_name,
            overrides,
            out_dir,
            filename_prefix="midrun_",
            seeds=SEEDS,
            steps=STEPS,
            sample_every=SAMPLE_EVERY,
        )


if __name__ == "__main__":
    main()
