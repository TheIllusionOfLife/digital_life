"""Check manuscript-reported parameters against manifest sources."""

from __future__ import annotations

import json
import re
from pathlib import Path

try:
    from .experiment_manifest import config_digest as _config_digest
except ImportError:
    from experiment_manifest import config_digest as _config_digest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PAPER = PROJECT_ROOT / "paper" / "main.tex"
DEFAULT_MANIFEST = PROJECT_ROOT / "docs" / "research" / "final_graph_manifest_reference.json"
DEFAULT_BINDINGS = PROJECT_ROOT / "docs" / "research" / "result_manifest_bindings.json"
EXPERIMENT_SCRIPTS = [
    PROJECT_ROOT / "scripts" / "experiment_final_graph.py",
    PROJECT_ROOT / "scripts" / "experiment_pairwise.py",
    PROJECT_ROOT / "scripts" / "experiment_cyclic.py",
    PROJECT_ROOT / "scripts" / "experiment_evolution.py",
    PROJECT_ROOT / "scripts" / "experiment_midrun_ablation.py",
    PROJECT_ROOT / "scripts" / "experiment_invariance.py",
    PROJECT_ROOT / "scripts" / "experiment_ecology_stress.py",
]


def _read_json(path: Path) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"failed to read {path}: {exc}") from exc


def _extract_reported_timing(tex: str) -> tuple[int | None, int | None]:
    pattern = re.compile(
        r"runs for\s+(\d+)\s+timesteps\s+with\s+population\s+sampled\s+every\s+(\d+)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(tex)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def _extract_script_paper_refs(paths: list[Path]) -> set[str]:
    refs: set[str] = set()
    pattern = re.compile(r'"paper_ref"\s*:\s*"([^"]+)"')
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text()
        refs.update(pattern.findall(text))
    return refs


def _check_files_exist(paths: dict[str, Path]) -> list[str]:
    issues: list[str] = []
    for name, path in paths.items():
        if not path.resolve().exists():
            issues.append(f"missing {name}: {path}")
    return issues


def _check_timing(tex: str, manifest: dict) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    checks: list[str] = []
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

    return issues, checks


def _check_base_config(manifest: dict) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    checks: list[str] = []
    base_cfg = manifest.get("base_config", {})
    if "mutation_point_rate" in base_cfg:
        checks.append("manifest base_config mutation_point_rate")
    else:
        issues.append("manifest missing base_config.mutation_point_rate")

    if "mutation_scale" in base_cfg or "mutation_point_scale" in base_cfg:
        checks.append("manifest base_config mutation_scale")
    else:
        issues.append(
            "manifest missing base_config.mutation_scale (or mutation_point_scale)"
        )
    return issues, checks


def _check_reference_manifest(manifest: dict) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    checks: list[str] = []
    for key in ["source_git_commit", "source_generated_at_utc"]:
        if manifest.get(key):
            checks.append(f"reference manifest {key}")
        else:
            issues.append(f"reference manifest missing {key}")
    return issues, checks


def _check_bindings(registry: dict, tex: str) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    checks: list[str] = []
    bindings = registry.get("bindings")
    if not isinstance(bindings, list) or len(bindings) == 0:
        issues.append("bindings registry is empty")
        return issues, checks

    checks.append("bindings registry non-empty")
    paper_labels = set(re.findall(r"\\label\{([^}]+)\}", tex))
    registry_refs: set[str] = set()
    for idx, binding in enumerate(bindings):
        paper_ref = binding.get("paper_ref")
        manifest_ref = binding.get("manifest")
        if not paper_ref:
            issues.append(f"binding[{idx}] missing paper_ref")
        elif paper_ref not in paper_labels:
            issues.append(f"binding[{idx}] paper_ref not found in paper labels: {paper_ref}")
        else:
            registry_refs.add(str(paper_ref))
        if not manifest_ref:
            issues.append(f"binding[{idx}] missing manifest")

    script_refs = _extract_script_paper_refs(EXPERIMENT_SCRIPTS)
    checks.append("experiment script paper_ref labels parsed")
    for ref in sorted(script_refs):
        if ref not in paper_labels:
            issues.append(f"experiment script paper_ref not found in paper labels: {ref}")
        if ref not in registry_refs:
            issues.append(f"experiment script paper_ref missing from registry: {ref}")

    return issues, checks


def _check_freshness(manifest: dict, manifest_path: Path) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    checks: list[str] = []

    generated_manifest_path = PROJECT_ROOT / "experiments" / "final_graph_manifest.json"
    should_check_freshness = manifest_path.resolve() == DEFAULT_MANIFEST.resolve()

    if should_check_freshness and generated_manifest_path.exists():
        try:
            generated_manifest = _read_json(generated_manifest_path)
        except ValueError as exc:
            issues.append(str(exc))
            return issues, checks

        checks.append("generated manifest freshness check")
        for key in ["steps", "sample_every"]:
            if generated_manifest.get(key) != manifest.get(key):
                issues.append(
                    "reference manifest stale for "
                    f"{key}: ref={manifest.get(key)} generated={generated_manifest.get(key)}"
                )
        generated_base_cfg = generated_manifest.get("base_config", {})
        base_cfg = manifest.get("base_config", {})

        if not generated_base_cfg:
            issues.append("generated manifest missing or empty base_config")
        if not base_cfg:
            issues.append("reference manifest missing or empty base_config")
        if generated_base_cfg and base_cfg:
            # Reference manifests may intentionally store a compact base_config.
            # Compare only keys present in the reference manifest so freshness
            # checks remain stable as config schema expands.
            # Schema rename compatibility:
            # reference may use mutation_scale while generated uses mutation_point_scale.
            key_map = {
                "mutation_scale": "mutation_point_scale",
            }
            missing = [
                k
                for k in base_cfg
                if key_map.get(k, k) not in generated_base_cfg
                and k not in generated_base_cfg
            ]
            if missing:
                issues.append(
                    "generated manifest missing reference base_config keys: "
                    + ", ".join(sorted(missing))
                )
            else:
                projected_generated = {}
                for k in base_cfg:
                    mapped = key_map.get(k, k)
                    if mapped in generated_base_cfg:
                        projected_generated[k] = generated_base_cfg[mapped]
                    else:
                        projected_generated[k] = generated_base_cfg[k]
                generated_digest = _config_digest(projected_generated)
                reference_digest = _config_digest(base_cfg)
                if generated_digest != reference_digest:
                    issues.append(
                        "reference manifest base_config differs from generated manifest "
                        "on shared keys"
                    )
    elif should_check_freshness:
        checks.append("generated manifest not present (freshness check skipped)")

    return issues, checks


def _load_documents(
    paper_path: Path, manifest_path: Path, registry_path: Path
) -> tuple[str | None, dict | None, dict | None, list[str]]:
    """Load all required documents, returning (tex, manifest, registry, issues)."""
    tex = None
    manifest = None
    registry = None
    issues: list[str] = []

    try:
        tex = paper_path.read_text()
    except OSError as exc:
        issues.append(f"failed to read paper file {paper_path}: {exc}")
        return tex, manifest, registry, issues

    try:
        manifest = _read_json(manifest_path)
        registry = _read_json(registry_path)
    except ValueError as exc:
        issues.append(str(exc))
        return tex, manifest, registry, issues

    return tex, manifest, registry, issues


def run_checks(paper_path: Path, manifest_path: Path, registry_path: Path) -> dict:
    """Run consistency checks and return a machine-readable report."""
    # 1. Check file existence
    file_issues = _check_files_exist({
        "paper file": paper_path,
        "manifest file": manifest_path,
        "bindings registry": registry_path,
    })
    if file_issues:
        return {"ok": False, "issues": file_issues, "checks": []}

    all_issues: list[str] = []
    all_checks: list[str] = []

    # 2. Load Documents
    tex, manifest, registry, load_issues = _load_documents(
        paper_path, manifest_path, registry_path
    )
    if load_issues:
        return {"ok": False, "issues": load_issues, "checks": all_checks}

    # Since we checked for load_issues, tex, manifest, and registry must be valid here
    assert tex is not None
    assert manifest is not None
    assert registry is not None

    # 3. Timing Checks
    t_issues, t_checks = _check_timing(tex, manifest)
    all_issues.extend(t_issues)
    all_checks.extend(t_checks)

    # 4. Base Config Checks
    bc_issues, bc_checks = _check_base_config(manifest)
    all_issues.extend(bc_issues)
    all_checks.extend(bc_checks)

    # 5. Reference Manifest Checks
    rm_issues, rm_checks = _check_reference_manifest(manifest)
    all_issues.extend(rm_issues)
    all_checks.extend(rm_checks)

    # 6. Bindings Registry Checks
    b_issues, b_checks = _check_bindings(registry, tex)
    all_issues.extend(b_issues)
    all_checks.extend(b_checks)

    # 7. Freshness Checks
    f_issues, f_checks = _check_freshness(manifest, manifest_path)
    all_issues.extend(f_issues)
    all_checks.extend(f_checks)

    return {"ok": len(all_issues) == 0, "issues": all_issues, "checks": all_checks}


def main() -> int:
    report = run_checks(DEFAULT_PAPER, DEFAULT_MANIFEST, DEFAULT_BINDINGS)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
