from unittest.mock import MagicMock

import pytest

# We need to import the module to patch it, but we can't import the function yet.
import scripts.generate_figures as gf


def test_plot_violin_strip():
    # Mock the ax object
    ax = MagicMock()

    # Dummy data
    data = {
        "normal": [1.0, 1.1, 0.9],
        "no_reproduction": [0.5, 0.6, 0.4],
        "no_response": [0.5, 0.6, 0.4],
        "no_metabolism": [0.5, 0.6, 0.4],
        "no_homeostasis": [0.5, 0.6, 0.4],
        "no_growth": [0.5, 0.6, 0.4],
        "no_boundary": [0.5, 0.6, 0.4],
        "no_evolution": [0.5, 0.6, 0.4],
    }

    # Mock the violinplot return value because the code iterates over parts["bodies"]
    mock_bodies = [MagicMock() for _ in range(8)]
    ax.violinplot.return_value = {"bodies": mock_bodies}

    # Call the function (assuming it will be added to gf)
    # We might need to reload or just access it if it were there.
    # Since it's not there yet, this test will fail if run now.

    if not hasattr(gf, "plot_violin_strip"):
        pytest.fail("plot_violin_strip not found in scripts.generate_figures")

    gf.plot_violin_strip(
        ax,
        data,
        title="Test Title",
        ylabel="Test Label",
        baseline_fmt=".1f",
        seed=42,
    )

    # Verify calls

    # 1. violinplot called
    assert ax.violinplot.called

    # 2. bodies properties set
    for body in mock_bodies:
        assert body.set_facecolor.called
        assert body.set_alpha.called

    # 3. scatter called for strip plot and medians
    # 8 conditions * 2 calls (strip + median) = 16 calls
    assert ax.scatter.call_count == 16

    # 4. axhline called for baseline
    assert ax.axhline.called
    _args, kwargs = ax.axhline.call_args
    # Check if label is formatted correctly
    # normal mean is 1.0
    assert "Normal mean (1.0)" in kwargs["label"]

    # 5. title and labels set
    ax.set_title.assert_called_with("Test Title", fontsize=9)
    ax.set_ylabel.assert_called_with("Test Label")
