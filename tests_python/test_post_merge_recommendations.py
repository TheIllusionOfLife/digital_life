from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from scripts.analyze_coupling import te_robustness_summary
from scripts.experiment_manifest import load_manifest, write_manifest


def test_manifest_schema_v2_supports_report_bindings(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    write_manifest(
        path,
        experiment_name="final_graph_ablation",
        steps=2000,
        sample_every=50,
        seeds=[100, 101],
        base_config={"seed": 100, "mutation_point_rate": 0.02},
        condition_overrides={"normal": {}},
        report_bindings=[
            {
                "result_id": "coupling_main",
                "paper_ref": "fig:coupling",
                "source_files": [
                    "experiments/final_graph_normal.json",
                    "experiments/coupling_analysis.json",
                ],
                "notes": "Primary coupling claim source",
            }
        ],
    )

    payload = load_manifest(path)
    assert payload["schema_version"] == 2
    assert payload["report_bindings"][0]["paper_ref"] == "fig:coupling"


def test_persistence_claim_gate_threshold() -> None:
    from scripts.analyze_phenotype import persistence_claim_gate

    assert persistence_claim_gate(0.2999, threshold=0.30) is False
    assert persistence_claim_gate(0.3000, threshold=0.30) is True


def test_te_robustness_summary_shape() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=120)
    y = 0.2 * np.roll(x, 1) + rng.normal(size=120)
    rows = te_robustness_summary(x, y, bin_settings=[3], permutation_settings=[20], rng_seed=7)

    assert len(rows) == 1
    assert rows[0]["bins"] == 3
    assert rows[0]["permutations"] == 20
    assert "te" in rows[0]
    assert "p_value" in rows[0]


def test_manuscript_consistency_check_detects_mismatch(tmp_path: Path) -> None:
    from scripts.check_manuscript_consistency import run_checks

    paper = tmp_path / "main.tex"
    manifest = tmp_path / "final_graph_manifest.json"
    registry = tmp_path / "result_manifest_bindings.json"

    paper.write_text(
        """
Each simulation runs for 2000 timesteps with population sampled every 50
steps.
""".strip()
    )
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "steps": 1000,
                "sample_every": 50,
                "base_config": {"mutation_point_rate": 0.02, "mutation_scale": 0.15},
            }
        )
    )
    registry.write_text(
        json.dumps(
            {
                "bindings": [
                    {
                        "result_id": "ablation_primary",
                        "paper_ref": "tab:ablation",
                        "manifest": "experiments/final_graph_manifest.json",
                        "source_files": ["experiments/final_graph_statistics.json"],
                    }
                ]
            }
        )
    )

    report = run_checks(paper, manifest, registry)
    assert report["ok"] is False
    assert any("steps" in issue for issue in report["issues"])


def test_manuscript_consistency_handles_non_numeric_manifest_values(tmp_path: Path) -> None:
    from scripts.check_manuscript_consistency import run_checks

    paper = tmp_path / "main.tex"
    manifest = tmp_path / "final_graph_manifest.json"
    registry = tmp_path / "result_manifest_bindings.json"

    paper.write_text(
        """
Each simulation runs for 2000 timesteps with population sampled every 50
steps.
\\label{tab:ablation}
""".strip()
    )
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "steps": None,
                "sample_every": "not-a-number",
                "base_config": {"mutation_point_rate": 0.02, "mutation_scale": 0.15},
            }
        )
    )
    registry.write_text(
        json.dumps(
            {
                "bindings": [
                    {
                        "result_id": "ablation_primary",
                        "paper_ref": "tab:ablation",
                        "manifest": "experiments/final_graph_manifest.json",
                        "source_files": ["experiments/final_graph_statistics.json"],
                    }
                ]
            }
        )
    )

    report = run_checks(paper, manifest, registry)
    assert report["ok"] is False
    assert any("steps invalid in manifest" in issue for issue in report["issues"])
    assert any("sample_every invalid in manifest" in issue for issue in report["issues"])
    assert not any(
        "steps mismatch:" in issue or "sample_every mismatch:" in issue
        for issue in report["issues"]
    )


def test_manuscript_consistency_reports_all_missing_inputs(tmp_path: Path) -> None:
    from scripts.check_manuscript_consistency import run_checks

    report = run_checks(
        tmp_path / "missing_main.tex",
        tmp_path / "missing_manifest.json",
        tmp_path / "missing_registry.json",
    )
    assert report["ok"] is False
    assert len(report["issues"]) == 3
