"""Shared constants, imports, and helpers for all figure modules."""

import json
from pathlib import Path

import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_TSV = PROJECT_ROOT / "experiments" / "final_graph_data.tsv"
FIG_DIR = PROJECT_ROOT / "paper" / "figures"

# ---------------------------------------------------------------------------
# Okabe-Ito colorblind-safe palette
# ---------------------------------------------------------------------------
COLORS = {
    "normal": "#000000",  # black
    "no_metabolism": "#E69F00",  # orange
    "no_boundary": "#56B4E9",  # sky blue
    "no_homeostasis": "#009E73",  # bluish green
    "no_growth": "#F0E442",  # yellow
    "no_reproduction": "#0072B2",  # blue
    "no_response": "#D55E00",  # vermillion
    "no_evolution": "#CC79A7",  # reddish purple
}

LABELS = {
    "normal": "Normal",
    "no_metabolism": "No Metabolism",
    "no_boundary": "No Boundary",
    "no_homeostasis": "No Homeostasis",
    "no_growth": "No Growth",
    "no_reproduction": "No Reproduction",
    "no_response": "No Response",
    "no_evolution": "No Evolution",
}

# Condition ordering: normal first, then by effect size (strongest first)
CONDITION_ORDER = [
    "normal",
    "no_reproduction",
    "no_response",
    "no_metabolism",
    "no_homeostasis",
    "no_growth",
    "no_boundary",
    "no_evolution",
]

# Global matplotlib style for LaTeX compatibility
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 9,
        "axes.labelsize": 10,
        "axes.titlesize": 10,
        "legend.fontsize": 7,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "lines.linewidth": 1.2,
        "figure.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
    }
)

VALID_CONDITIONS = set(COLORS.keys())

COUPLING_CRITERIA = [
    "Cellular Org.",
    "Metabolism",
    "Homeostasis",
    "Growth/Dev.",
    "Reproduction",
    "Response",
    "Evolution",
]

# Initial mapping for short names
COUPLING_METRIC_MAPPING = {
    "energy_mean": "Metabolism",
    "boundary_mean": "Cellular Org.",
    "internal_state_mean_0": "Homeostasis",
}

COUPLING_NODE_COLORS = [
    COLORS["no_boundary"],
    COLORS["no_metabolism"],
    COLORS["no_homeostasis"],
    COLORS["no_growth"],
    COLORS["no_reproduction"],
    COLORS["no_response"],
    COLORS["no_evolution"],
]

INTERVENTION_METRICS = (
    "energy_mean",
    "waste_mean",
    "boundary_mean",
    "internal_state_mean_0",
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def parse_tsv(path: Path) -> list[dict]:
    """Parse TSV with stderr preamble and interleaved summary lines.

    Detects header by content, then only parses lines whose first field
    is a known condition name (skips seed-summary lines, condition headers, etc.).
    """
    rows = []
    header = None
    n_fields = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith(" ") or line.startswith("---"):
                continue
            if header is None:
                if line.startswith("condition\t"):
                    header = line.split("\t")
                    n_fields = len(header)
                continue
            fields = line.split("\t")
            if len(fields) != n_fields:
                continue
            if fields[0] not in VALID_CONDITIONS:
                continue
            row = {}
            for col, val in zip(header, fields, strict=True):
                try:
                    row[col] = float(val)
                except ValueError:
                    row[col] = val
            rows.append(row)
    return rows


def get_coupling_best(pair: dict) -> tuple[float | None, int | None]:
    """Read best r/lag from v2 coupling schema, with legacy fallback."""
    lagged = pair.get("lagged_correlation", {})
    r = lagged.get("best_pearson_r", pair.get("best_pearson_r"))
    lag = lagged.get("best_lag", pair.get("best_lag"))
    return r, lag


def load_json(path: Path) -> list[dict]:
    """Load experiment results from a JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
