from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest

import scripts.analyze_coupling as analyze_coupling
from scripts.analyze_coupling import phase_randomize, te_robustness_summary
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
    # Imported inline to keep this module decoupled from analyze_phenotype load-time deps.
    from scripts.analyze_phenotype import persistence_claim_gate

    assert persistence_claim_gate(0.2999, threshold=0.30) is False
    assert persistence_claim_gate(0.3000, threshold=0.30) is True


def test_te_robustness_summary_shape() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=120)
    y = 0.2 * np.roll(x, 1) + rng.normal(size=120)
    rows = te_robustness_summary(
        x,
        y,
        bin_settings=[3],
        permutation_settings=[20],
        rng_seed=7,
        phase_surrogate_samples=8,
        surrogate_permutation_floor=8,
        surrogate_permutation_divisor=2,
    )

    assert len(rows) == 1
    assert rows[0]["bins"] == 3
    assert rows[0]["permutations"] == 20
    assert "te" in rows[0]
    assert "p_value" in rows[0]


def test_te_robustness_summary_excludes_none_surrogates(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = {"n": 0}

    def fake_te(*args, **kwargs):  # type: ignore[no-untyped-def]
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"te": 0.4, "p_value": 0.2, "null_mean": 0.0, "null_std": 0.0}
        if call_count["n"] in (3, 5):
            return None
        return {"te": 0.1, "p_value": 0.3, "null_mean": 0.0, "null_std": 0.0}

    monkeypatch.setattr(analyze_coupling, "transfer_entropy_lag1", fake_te)

    x = np.array([1, 2, 3, 4, 5, 6], dtype=float)
    y = np.array([2, 3, 4, 5, 6, 7], dtype=float)
    rows = te_robustness_summary(
        x,
        y,
        bin_settings=[3],
        permutation_settings=[20],
        rng_seed=7,
        phase_surrogate_samples=4,
        surrogate_permutation_floor=8,
        surrogate_permutation_divisor=2,
    )
    assert len(rows) == 1
    assert rows[0]["phase_surrogate_valid_n"] == 2
    assert rows[0]["phase_surrogate_te_mean"] == 0.1


def test_phase_randomize_even_keeps_nyquist_bin_real_and_fixed() -> None:
    rng = np.random.default_rng(123)
    series = np.random.default_rng(9).normal(size=8)
    before = np.fft.rfft(series)
    after = np.fft.rfft(phase_randomize(series, rng))

    assert np.isclose(after[0].imag, 0.0, atol=1e-10)
    assert np.isclose(after[-1], before[-1], atol=1e-8)


def test_phase_randomize_odd_randomizes_last_complex_bin_phase() -> None:
    rng = np.random.default_rng(456)
    series = np.random.default_rng(10).normal(size=9)
    before = np.fft.rfft(series)
    after = np.fft.rfft(phase_randomize(series, rng))

    assert np.isclose(abs(after[-1]), abs(before[-1]), atol=1e-8)
    assert not np.isclose(after[-1], before[-1], atol=1e-8)


def test_phase_randomize_small_n_returns_copy() -> None:
    rng = np.random.default_rng(777)
    series = np.array([0.1, -0.2, 0.3], dtype=float)
    out = phase_randomize(series, rng)

    assert out.dtype == float
    assert len(out) == len(series)
    assert np.allclose(out, series)
    assert out is not series


def test_main_rejects_unknown_robustness_profile() -> None:
    with pytest.raises(ValueError):
        analyze_coupling.main(robustness_profile="unknown")


def test_manuscript_consistency_check_detects_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Imported inline to keep this module focused on checker behavior.
    import scripts.check_manuscript_consistency
    from scripts.check_manuscript_consistency import run_checks

    # Isolate test from repository state
    monkeypatch.setattr(scripts.check_manuscript_consistency, "EXPERIMENT_SCRIPTS", [])

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
                "source_git_commit": "abc1234",
                "source_generated_at_utc": "2026-02-17T00:00:00Z",
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
    assert any("steps mismatch:" in issue for issue in report["issues"])


def test_manuscript_consistency_handles_non_numeric_manifest_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Imported inline to keep this module focused on checker behavior.
    import scripts.check_manuscript_consistency
    from scripts.check_manuscript_consistency import run_checks

    # Isolate test from repository state
    monkeypatch.setattr(scripts.check_manuscript_consistency, "EXPERIMENT_SCRIPTS", [])

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
    # Imported inline to keep this module focused on checker behavior.
    from scripts.check_manuscript_consistency import run_checks

    report = run_checks(
        tmp_path / "missing_main.tex",
        tmp_path / "missing_manifest.json",
        tmp_path / "missing_registry.json",
    )
    assert report["ok"] is False
    assert len(report["issues"]) == 3


def test_manuscript_consistency_checks_script_paper_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # run_checks parses hardcoded EXPERIMENT_SCRIPTS; if scripts add new paper_ref
    # labels, this fixture must include matching paper labels/bindings.
    # We patch EXPERIMENT_SCRIPTS to a controlled list to avoid brittleness.
    import scripts.check_manuscript_consistency
    from scripts.check_manuscript_consistency import run_checks

    # Create dummy script
    script_path = tmp_path / "experiment_dummy.py"
    script_path.write_text('..."paper_ref": "fig:dummy"...')

    monkeypatch.setattr(
        scripts.check_manuscript_consistency, "EXPERIMENT_SCRIPTS", [script_path]
    )

    paper = tmp_path / "main.tex"
    manifest = tmp_path / "final_graph_manifest_reference.json"
    registry = tmp_path / "result_manifest_bindings.json"
    paper.write_text(
        """
Each simulation runs for 2000 timesteps with population sampled every 50
steps.
\\label{fig:dummy}
""".strip()
    )
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "source_git_commit": "abc1234",
                "source_generated_at_utc": "2026-02-17T00:00:00Z",
                "steps": 2000,
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
                        "result_id": "dummy_result",
                        "paper_ref": "fig:dummy",
                        "manifest": "experiments/final_graph_manifest.json",
                        "source_files": ["experiments/dummy.json"],
                    },
                ]
            }
        )
    )

    report = run_checks(paper, manifest, registry)
    assert report["ok"] is True


def test_manuscript_consistency_reports_invalid_registry_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Imported inline to keep this module focused on checker behavior.
    import scripts.check_manuscript_consistency
    from scripts.check_manuscript_consistency import run_checks

    # Isolate test from repository state
    monkeypatch.setattr(scripts.check_manuscript_consistency, "EXPERIMENT_SCRIPTS", [])

    paper = tmp_path / "main.tex"
    manifest = tmp_path / "manifest.json"
    registry = tmp_path / "registry.json"
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
                "source_git_commit": "abc1234",
                "source_generated_at_utc": "2026-02-17T00:00:00Z",
                "steps": 2000,
                "sample_every": 50,
                "base_config": {"mutation_point_rate": 0.02, "mutation_scale": 0.15},
            }
        )
    )
    registry.write_text("{invalid json")

    report = run_checks(paper, manifest, registry)
    assert report["ok"] is False
    assert any("invalid JSON in" in issue for issue in report["issues"])


def test_experiment_niche_defaults_and_long_horizon_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = types.SimpleNamespace()
    calls: list[tuple[int, int, list[int]]] = []

    def fake_version() -> str:
        return "test"

    def fake_run_niche(
        config_json: str, steps: int, sample_every: int, snapshot_steps_json: str
    ) -> str:
        _ = config_json
        calls.append((steps, sample_every, json.loads(snapshot_steps_json)))
        payload = {"final_alive_count": 1, "organism_snapshots": [{"organisms": [{"id": 1}]}]}
        return json.dumps(payload)

    fake.version = fake_version
    fake.run_niche_experiment_json = fake_run_niche
    monkeypatch.setitem(sys.modules, "digital_life", fake)
    monkeypatch.syspath_prepend(str(Path("scripts").resolve()))

    mod = importlib.import_module("scripts.experiment_niche")
    mod = importlib.reload(mod)

    assert mod.SEEDS == list(range(100, 130))

    monkeypatch.setattr(mod, "SEEDS", [100])
    monkeypatch.setattr(mod, "make_config", lambda seed, overrides: "{}")
    monkeypatch.setattr(
        sys,
        "argv",
        ["experiment_niche.py", "--long-horizon", "--output", str(tmp_path / "custom_long.json")],
    )
    mod.main()
    assert calls[-1][0] == mod.LONG_HORIZON_STEPS
    assert calls[-1][1] == mod.SAMPLE_EVERY
    assert calls[-1][2] == mod.LONG_HORIZON_SNAPSHOT_STEPS
    assert (tmp_path / "custom_long.json").exists()

    monkeypatch.setattr(
        sys,
        "argv",
        ["experiment_niche.py", "--output", str(tmp_path / "niche_normal.json")],
    )
    mod.main()
    assert calls[-1][0] == mod.STEPS
    assert calls[-1][1] == mod.SAMPLE_EVERY
    assert calls[-1][2] == mod.SNAPSHOT_STEPS
    assert (tmp_path / "niche_normal.json").exists()

def test_experiment_regimes_seed_count_is_n30(monkeypatch: pytest.MonkeyPatch) -> None:
    script_dir = Path(__file__).resolve().parents[1] / "scripts"
    script_path = script_dir / "experiment_regimes.py"

    fake_digital_life = types.SimpleNamespace(version=lambda: "test")
    fake_utils = types.SimpleNamespace(
        CONDITIONS={},
        log=lambda *args, **kwargs: None,
        run_single=lambda *args, **kwargs: {},
        safe_path=lambda out_dir, name: out_dir / name,
    )
    monkeypatch.setitem(sys.modules, "digital_life", fake_digital_life)
    monkeypatch.setitem(sys.modules, "experiment_utils", fake_utils)

    spec = importlib.util.spec_from_file_location("experiment_regimes_under_test", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert hasattr(module, "SEEDS")
    assert len(module.SEEDS) == 30
    assert module.SEEDS[0] == 100
    assert module.SEEDS[-1] == 129
