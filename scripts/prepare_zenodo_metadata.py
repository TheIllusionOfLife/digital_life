"""Prepare Zenodo upload metadata for heavy experiment artifacts.

Usage:
    uv run python scripts/prepare_zenodo_metadata.py \
        experiments/niche_normal_long.json \
        --experiment-name niche_long_horizon \
        --steps 10000 \
        --seed-start 100 \
        --seed-end 129 \
        --paper-binding fig:persistent_clusters=experiments/phenotype_analysis.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _detect_git_commit() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return out or None


def _parse_binding(raw: str) -> dict[str, str]:
    if "=" not in raw:
        raise ValueError(f"invalid binding '{raw}': expected PAPER_REF=FILE_PATH")
    paper_ref, file_path = raw.split("=", 1)
    paper_ref = paper_ref.strip()
    file_path = file_path.strip()
    if not paper_ref or not file_path:
        raise ValueError(f"invalid binding '{raw}': expected PAPER_REF=FILE_PATH")
    return {"paper_ref": paper_ref, "file_path": file_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", type=Path, nargs="+", help="Artifact files uploaded to Zenodo.")
    parser.add_argument("--experiment-name", required=True, help="Logical experiment identifier.")
    parser.add_argument("--steps", type=int, required=True, help="Simulation steps per run.")
    parser.add_argument("--seed-start", type=int, required=True, help="Inclusive seed range start.")
    parser.add_argument("--seed-end", type=int, required=True, help="Inclusive seed range end.")
    parser.add_argument(
        "--entrypoint",
        default="uv run python scripts/experiment_niche.py --long-horizon",
        help="Command used to generate the artifacts.",
    )
    parser.add_argument(
        "--paper-binding",
        action="append",
        default=[],
        help="Optional mapping in PAPER_REF=FILE_PATH format. Repeatable.",
    )
    parser.add_argument("--zenodo-doi", default=None, help="Reserved or published Zenodo DOI.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("zenodo_metadata.json"),
        help="Output JSON path (default: ./zenodo_metadata.json).",
    )
    return parser.parse_args()


def build_metadata(args: argparse.Namespace) -> dict:
    if args.seed_end < args.seed_start:
        raise ValueError(
            f"invalid seed range: seed-end ({args.seed_end}) < seed-start ({args.seed_start})"
        )
    if args.steps <= 0:
        raise ValueError(f"invalid steps: expected positive int, got {args.steps}")

    artifact_entries = []
    for path in args.files:
        resolved = path.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"artifact not found: {path}")
        artifact_entries.append(
            {
                "path": str(path),
                "size_bytes": resolved.stat().st_size,
                "sha256": _sha256(resolved),
            }
        )

    bindings = [_parse_binding(raw) for raw in args.paper_binding]
    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_name": args.experiment_name,
        "git_commit": _detect_git_commit(),
        "entrypoint": args.entrypoint,
        "metadata_generation_argv": list(sys.argv[1:]),
        "seed_range": {"start": args.seed_start, "end": args.seed_end},
        "steps": args.steps,
        "artifacts": artifact_entries,
        "paper_bindings": bindings,
    }
    if args.zenodo_doi:
        payload["zenodo_doi"] = args.zenodo_doi
    return payload


def main() -> int:
    args = parse_args()
    payload = build_metadata(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Saved metadata: {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
