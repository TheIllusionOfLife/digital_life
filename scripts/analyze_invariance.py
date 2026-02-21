"""Analyze implementation invariance experiment outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def mean_final(rows: list[dict]) -> float:
    vals = [float(r.get("final_alive_count", 0)) for r in rows]
    return sum(vals) / max(1, len(vals))


def report(experiment_dir: Path) -> dict:
    baseline_default = mean_final(load(experiment_dir / "invariance_baseline_default.json"))
    baseline_alt = mean_final(load(experiment_dir / "invariance_baseline_alt_modes.json"))

    no_boundary_default = mean_final(load(experiment_dir / "invariance_no_boundary_default.json"))
    no_boundary_alt = mean_final(load(experiment_dir / "invariance_no_boundary_alt_mode.json"))

    no_homeo_default = mean_final(load(experiment_dir / "invariance_no_homeostasis_default.json"))
    no_homeo_alt = mean_final(load(experiment_dir / "invariance_no_homeostasis_alt_mode.json"))

    boundary_effect_default = baseline_default - no_boundary_default
    boundary_effect_alt = baseline_alt - no_boundary_alt
    homeo_effect_default = baseline_default - no_homeo_default
    homeo_effect_alt = baseline_alt - no_homeo_alt

    return {
        "experiment": "implementation_invariance",
        "baseline": {
            "default_modes": round(baseline_default, 3),
            "alt_modes": round(baseline_alt, 3),
        },
        "boundary": {
            "effect_default": round(boundary_effect_default, 3),
            "effect_alt": round(boundary_effect_alt, 3),
            "direction_consistent": (boundary_effect_default >= 0) == (boundary_effect_alt >= 0),
        },
        "homeostasis": {
            "effect_default": round(homeo_effect_default, 3),
            "effect_alt": round(homeo_effect_alt, 3),
            "direction_consistent": (homeo_effect_default >= 0) == (homeo_effect_alt >= 0),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze implementation invariance outputs.")
    parser.add_argument("experiment_dir", nargs="?", default="experiments")
    args = parser.parse_args()
    print(json.dumps(report(Path(args.experiment_dir)), indent=2))


if __name__ == "__main__":
    main()
