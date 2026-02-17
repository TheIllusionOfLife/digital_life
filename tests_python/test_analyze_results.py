import json
import sys
from unittest.mock import patch

import numpy as np
import pytest

from scripts import analyze_results


def test_cohens_d():
    a = np.array([1, 2, 3, 4, 5])
    b = np.array([2, 3, 4, 5, 6])
    d = analyze_results.cohens_d(a, b)
    # Mean a = 3, var a = 2.5
    # Mean b = 4, var b = 2.5
    # Pooled SD = sqrt(2.5) = 1.5811
    # d = (3 - 4) / 1.5811 = -0.6324
    assert np.isclose(d, -0.6324, atol=0.001)

def test_cliffs_delta():
    a = np.array([1, 2, 3])
    b = np.array([2, 3, 4])
    delta = analyze_results.cliffs_delta(a, b)
    # 1 vs 2: -1
    # 1 vs 3: -1
    # 1 vs 4: -1
    # 2 vs 2: 0
    # 2 vs 3: -1
    # 2 vs 4: -1
    # 3 vs 2: 1
    # 3 vs 3: 0
    # 3 vs 4: -1
    # sum: -3 + -2 + 0 = -5. delta = -5/9 = -0.555
    assert np.isclose(delta, -5.0/9.0, atol=0.001)

@patch("scripts.analyze_results.load_condition")
@patch("scripts.analyze_results.analyze_graded")
@patch("scripts.analyze_results.analyze_cyclic")
@patch("scripts.analyze_results.analyze_sham")
def test_main_flow(mock_sham, mock_cyclic, mock_graded, mock_load, capsys):
    # Setup mock data: 5 seeds for each condition
    # Normal: all 100
    # Ablated: all 50 (should be significant)

    def side_effect(prefix, cond):
        if cond == "normal":
            return [
                {
                    "final_alive_count": 100,
                    "lifespans": [1000],
                    "samples": [
                        {"step": 0, "alive_count": 10},
                        {"step": 500, "alive_count": 100},
                    ],
                }
            ] * 5
        else:
            return [
                {
                    "final_alive_count": 50,
                    "lifespans": [500],
                    "samples": [
                        {"step": 0, "alive_count": 10},
                        {"step": 500, "alive_count": 50},
                    ],
                }
            ] * 5

    mock_load.side_effect = side_effect
    mock_graded.return_value = None
    mock_cyclic.return_value = None
    mock_sham.return_value = None

    # Mock argv
    with patch.object(sys, 'argv', ["analyze_results.py", "experiments/test"]):
        analyze_results.main()

    captured = capsys.readouterr()
    # Check stdout for JSON
    try:
        output = json.loads(captured.out)
    except json.JSONDecodeError:
        pytest.fail(f"Output is not valid JSON: {captured.out}")

    assert output["experiment"] == "criterion_ablation"
    assert output["n_per_condition"] == 5
    # Check that we have comparisons
    assert len(output["comparisons"]) > 0
    first_comp = output["comparisons"][0]
    assert first_comp["normal_mean"] == 100.0
    assert first_comp["ablation_mean"] == 50.0
    # Should be significant
    assert first_comp["significant"] is True
