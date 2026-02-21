"""Analyze mid-run vs step-0 ablation outcomes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_condition(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def mean_final_alive(rows: list[dict]) -> float:
    values = [float(r.get("final_alive_count", 0)) for r in rows]
    return sum(values) / max(1, len(values))


def build_report(experiment_dir: Path) -> dict:
    report: dict[str, object] = {
        "experiment": "midrun_ablation",
        "criteria": [],
    }

    criteria = [
        "metabolism",
        "boundary",
        "homeostasis",
        "response",
        "reproduction",
        "evolution",
        "growth",
    ]
    normal = load_condition(experiment_dir / "midrun_normal.json")
    normal_mean = mean_final_alive(normal)

    entries = []
    for criterion in criteria:
        step0 = load_condition(experiment_dir / f"midrun_no_{criterion}_step0.json")
        midrun = load_condition(experiment_dir / f"midrun_no_{criterion}_midrun.json")
        step0_mean = mean_final_alive(step0)
        midrun_mean = mean_final_alive(midrun)
        entries.append(
            {
                "criterion": criterion,
                "normal_mean": round(normal_mean, 3),
                "step0_mean": round(step0_mean, 3),
                "midrun_mean": round(midrun_mean, 3),
                "midrun_minus_step0": round(midrun_mean - step0_mean, 3),
            }
        )

    report["criteria"] = entries
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze mid-run ablation outputs.")
    parser.add_argument("experiment_dir", nargs="?", default="experiments")
    args = parser.parse_args()
    report = build_report(Path(args.experiment_dir))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
