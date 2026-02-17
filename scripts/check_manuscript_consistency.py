"""Check manuscript-reported parameters against manifest sources."""

from __future__ import annotations

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PAPER = PROJECT_ROOT / "paper" / "main.tex"
DEFAULT_MANIFEST = PROJECT_ROOT / "docs" / "research" / "final_graph_manifest_reference.json"
DEFAULT_BINDINGS = PROJECT_ROOT / "docs" / "research" / "result_manifest_bindings.json"


def _read_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _extract_reported_timing(tex: str) -> tuple[int | None, int | None]:
    pattern = re.compile(
        r"runs for\s+(\d+)\s+timesteps\s+with\s+population\s+sampled\s+every\s+(\d+)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(tex)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def run_checks(paper_path: Path, manifest_path: Path, registry_path: Path) -> dict:
    """Run consistency checks and return a machine-readable report."""
    issues: list[str] = []
    checks: list[str] = []

    paths_to_check = {
        "paper file": paper_path,
        "manifest file": manifest_path,
        "bindings registry": registry_path,
    }
    for name, path in paths_to_check.items():
        if not path.exists():
            issues.append(f"missing {name}: {path}")
    if issues:
        return {"ok": False, "issues": issues, "checks": checks}

    tex = paper_path.read_text()
    manifest = _read_json(manifest_path)
    registry = _read_json(registry_path)

    reported_steps, reported_sample_every = _extract_reported_timing(tex)
    if reported_steps is not None:
        checks.append("timing steps")
        manifest_steps = manifest.get("steps")
        try:
            manifest_steps_int = int(manifest_steps)
        except (TypeError, ValueError):
            issues.append(f"steps invalid in manifest: {manifest_steps}")
        else:
            if manifest_steps_int != reported_steps:
                issues.append(
                    f"steps mismatch: paper={reported_steps} manifest={manifest_steps}"
                )
    else:
        issues.append("could not parse timing steps from paper")

    if reported_sample_every is not None:
        checks.append("timing sample_every")
        manifest_sample_every = manifest.get("sample_every")
        try:
            manifest_sample_every_int = int(manifest_sample_every)
        except (TypeError, ValueError):
            issues.append(f"sample_every invalid in manifest: {manifest_sample_every}")
        else:
            if manifest_sample_every_int != reported_sample_every:
                issues.append(
                    "sample_every mismatch: "
                    f"paper={reported_sample_every} manifest={manifest_sample_every}"
                )
    else:
        issues.append("could not parse sample_every from paper")

    base_cfg = manifest.get("base_config", {})
    for key in ["mutation_point_rate", "mutation_scale"]:
        if key in base_cfg:
            checks.append(f"manifest base_config {key}")
        else:
            issues.append(f"manifest missing base_config.{key}")

    bindings = registry.get("bindings")
    if not isinstance(bindings, list) or len(bindings) == 0:
        issues.append("bindings registry is empty")
    else:
        checks.append("bindings registry non-empty")
        paper_labels = set(re.findall(r"\\label\{([^}]+)\}", tex))
        for idx, binding in enumerate(bindings):
            paper_ref = binding.get("paper_ref")
            manifest_ref = binding.get("manifest")
            if not paper_ref:
                issues.append(f"binding[{idx}] missing paper_ref")
            elif paper_ref not in paper_labels:
                issues.append(f"binding[{idx}] paper_ref not found in paper labels: {paper_ref}")
            if not manifest_ref:
                issues.append(f"binding[{idx}] missing manifest")

    return {"ok": len(issues) == 0, "issues": issues, "checks": checks}


def main() -> int:
    report = run_checks(DEFAULT_PAPER, DEFAULT_MANIFEST, DEFAULT_BINDINGS)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
