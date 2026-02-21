"""Extract simple failure-pathway traces from ablation result JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


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
    args = parser.parse_args()
    base = Path(args.experiment_dir)

    normal = summarize_condition(load(base / "final_graph_normal.json"))
    metabolism = summarize_condition(load(base / "final_graph_no_metabolism.json"))
    response = summarize_condition(load(base / "final_graph_no_response.json"))

    payload = {
        "experiment": "failure_pathways",
        "normal": normal,
        "no_metabolism": metabolism,
        "no_response": response,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
