"""Extract simple failure-pathway traces from ablation result JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .analysis_utils import load
except ImportError:
    from analysis_utils import load


DEFAULT_CONDITIONS = {
    "normal": "final_graph_normal.json",
    "no_metabolism": "final_graph_no_metabolism.json",
    "no_response": "final_graph_no_response.json",
}


def mean_series(rows: list[dict], key: str) -> list[tuple[int, float]]:
    buckets: dict[int, list[float]] = {}
    for row in rows:
        for sample in row.get("samples", []):
            step = int(sample["step"])
            buckets.setdefault(step, []).append(float(sample.get(key, 0.0)))
    return [(step, sum(vals) / len(vals)) for step, vals in sorted(buckets.items()) if vals]


def first_drop_step(series: list[tuple[int, float]], frac: float = 0.5) -> int | None:
    if not series:
        return None
    baseline = series[0][1]
    if baseline <= 0:
        return None
    threshold = baseline * frac
    for step, value in series:
        if value <= threshold:
            return step
    return None


def summarize_condition(rows: list[dict]) -> dict:
    energy = mean_series(rows, "energy_mean")
    boundary = mean_series(rows, "boundary_mean")
    alive = mean_series(rows, "alive_count")
    return {
        "energy_drop50_step": first_drop_step(energy),
        "boundary_drop50_step": first_drop_step(boundary),
        "alive_drop50_step": first_drop_step(alive),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze failure pathways from ablation JSON files."
    )
    parser.add_argument("experiment_dir", nargs="?", default="experiments")
    parser.add_argument(
        "--condition",
        action="append",
        default=[],
        metavar="NAME=FILENAME",
        help=(
            "Condition mapping (repeatable), e.g. "
            "--condition normal=final_graph_normal.json"
        ),
    )
    args = parser.parse_args()
    base = Path(args.experiment_dir)

    conditions = dict(DEFAULT_CONDITIONS)
    for item in args.condition:
        if "=" not in item:
            parser.error(f"invalid --condition value '{item}', expected NAME=FILENAME")
        name, filename = item.split("=", 1)
        name = name.strip()
        filename = filename.strip()
        if not name or not filename:
            parser.error(f"invalid --condition value '{item}', expected NAME=FILENAME")
        conditions[name] = filename

    missing = [
        f"{name}={filename}"
        for name, filename in conditions.items()
        if not (base / filename).exists()
    ]
    if missing:
        parser.error(
            "missing input files under "
            f"{base}: " + ", ".join(missing)
        )

    payload = {
        "experiment": "failure_pathways",
    }
    for name, filename in conditions.items():
        payload[name] = summarize_condition(load(base / filename))

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
