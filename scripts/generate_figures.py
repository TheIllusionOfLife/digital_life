"""Generate all paper figures from experimental data.

Outputs PDF figures to paper/figures/ for inclusion in the LaTeX manuscript.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import json
import numpy as np
from collections import defaultdict

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_TSV = PROJECT_ROOT / "experiments" / "final_graph_data.tsv"
FIG_DIR = PROJECT_ROOT / "paper" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Okabe-Ito colorblind-safe palette
COLORS = {
    "normal": "#000000",       # black
    "no_metabolism": "#E69F00", # orange
    "no_boundary": "#56B4E9",  # sky blue
    "no_homeostasis": "#009E73",# bluish green
    "no_growth": "#F0E442",    # yellow
    "no_reproduction": "#0072B2",# blue
    "no_response": "#D55E00",  # vermillion
    "no_evolution": "#CC79A7", # reddish purple
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
plt.rcParams.update({
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
})


VALID_CONDITIONS = set(COLORS.keys())


def parse_tsv(path: Path) -> list[dict]:
    """Parse TSV with stderr preamble and interleaved summary lines.

    Detects header by content, then only parses lines whose first field
    is a known condition name (skips seed-summary lines, condition headers, etc.).
    """
    rows = []
    header = None
    n_fields = 0
    with open(path) as f:
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
            for col, val in zip(header, fields):
                try:
                    row[col] = float(val)
                except ValueError:
                    row[col] = val
            rows.append(row)
    return rows


def generate_timeseries(data: list[dict]) -> None:
    """Figure 2: Population dynamics time-series with confidence bands."""
    # Group by (condition, step) → list of alive_count values
    groups: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in data:
        key = (row["condition"], int(row["step"]))
        groups[key].append(row["alive_count"])

    fig, ax = plt.subplots(figsize=(7, 3.2))

    for condition in CONDITION_ORDER:
        steps = sorted({s for (c, s) in groups if c == condition})
        means = []
        sems = []
        for step in steps:
            vals = groups[(condition, step)]
            arr = np.array(vals)
            means.append(arr.mean())
            sems.append(arr.std(ddof=1) / np.sqrt(len(arr)) if len(arr) >= 2 else 0.0)

        means = np.array(means)
        sems = np.array(sems)
        color = COLORS[condition]
        lw = 2.0 if condition == "normal" else 1.2
        ls = "-" if condition == "normal" else "--"
        ax.plot(steps, means, color=color, linewidth=lw, linestyle=ls,
                label=LABELS[condition], zorder=10 if condition == "normal" else 5)
        ax.fill_between(steps, means - sems, means + sems,
                        color=color, alpha=0.15, zorder=2)

    ax.set_xlabel("Simulation Step")
    ax.set_ylabel("Mean Alive Count ($n$=30)")
    ax.set_xlim(0, 2000)
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper right", ncol=2, framealpha=0.9, edgecolor="0.8")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.savefig(FIG_DIR / "fig_timeseries.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_timeseries.pdf'}")


def generate_architecture() -> None:
    """Figure 1: Architecture diagram showing two-layer hierarchy."""
    fig, ax = plt.subplots(figsize=(7, 4.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6.5)
    ax.set_aspect("equal")
    ax.axis("off")

    # Environment box
    env_rect = mpatches.FancyBboxPatch(
        (0.3, 0.3), 9.4, 5.9, boxstyle="round,pad=0.1",
        facecolor="#F5F5F5", edgecolor="#333333", linewidth=1.5)
    ax.add_patch(env_rect)
    ax.text(5.0, 5.85, "Environment (Toroidal 2D, 100$\\times$100)",
            ha="center", va="center", fontsize=10, fontweight="bold",
            color="#333333")

    # Resource field
    ax.text(1.2, 5.35, "Resource Field", ha="left", va="center",
            fontsize=7, fontstyle="italic", color="#666666")

    # Single organism shown in detail (left side)
    ox, oy = 0.8, 0.8
    org_rect = mpatches.FancyBboxPatch(
        (ox, oy), 4.8, 4.2, boxstyle="round,pad=0.08",
        facecolor="#FFFFFF", edgecolor="#0072B2", linewidth=1.2)
    ax.add_patch(org_rect)
    ax.text(ox + 2.4, oy + 3.85, "Organism (10-50 per environment)",
            ha="center", va="center", fontsize=8, fontweight="bold",
            color="#0072B2")

    # Internal components (wider boxes for the single organism)
    components = [
        ("Genome\n(7 segments, 256 floats)", ox + 0.2, oy + 2.7, 2.1, 0.85, "#E69F00"),
        ("NN Controller\n(8>16>4, 212 wt)", ox + 2.5, oy + 2.7, 2.1, 0.85, "#009E73"),
        ("Graph Metabolism\n(2-4 nodes, directed)", ox + 0.2, oy + 1.3, 2.1, 0.85, "#D55E00"),
        ("Boundary Maintenance\n(10-50 swarm agents)", ox + 2.5, oy + 1.3, 2.1, 0.85, "#56B4E9"),
    ]

    for label, cx, cy, w, h, color in components:
        comp_rect = mpatches.FancyBboxPatch(
            (cx, cy), w, h, boxstyle="round,pad=0.05",
            facecolor=color, edgecolor="none", alpha=0.2)
        ax.add_patch(comp_rect)
        comp_border = mpatches.FancyBboxPatch(
            (cx, cy), w, h, boxstyle="round,pad=0.05",
            facecolor="none", edgecolor=color, linewidth=0.8)
        ax.add_patch(comp_border)
        ax.text(cx + w / 2, cy + h / 2, label,
                ha="center", va="center", fontsize=6, color="#333333")

    # Arrows: Genome -> NN, Genome -> Metabolism
    ax.annotate("", xy=(ox + 2.5, oy + 3.12), xytext=(ox + 2.3, oy + 3.12),
                arrowprops=dict(arrowstyle="->", color="#888", lw=0.8))
    ax.annotate("", xy=(ox + 1.25, oy + 2.7), xytext=(ox + 1.25, oy + 2.15),
                arrowprops=dict(arrowstyle="->", color="#888", lw=0.8))
    # NN -> Boundary (response to stimuli)
    ax.annotate("", xy=(ox + 3.55, oy + 2.7), xytext=(ox + 3.55, oy + 2.15),
                arrowprops=dict(arrowstyle="->", color="#888", lw=0.8))
    # Metabolism <-> Boundary (energy <-> integrity)
    ax.annotate("", xy=(ox + 2.5, oy + 1.72), xytext=(ox + 2.3, oy + 1.72),
                arrowprops=dict(arrowstyle="<->", color="#888", lw=0.8))

    # Internal state label
    ax.text(ox + 2.4, oy + 0.45, "Internal State Vector (homeostatic regulation)",
            ha="center", va="center", fontsize=6, fontstyle="italic",
            color="#666666")

    # Criteria mapping sidebar (right side, clearly separated)
    sidebar_x = 6.2
    sidebar_rect = mpatches.FancyBboxPatch(
        (sidebar_x, 0.8), 3.2, 4.2, boxstyle="round,pad=0.08",
        facecolor="#FFFFFF", edgecolor="#999999", linewidth=0.8,
        linestyle="--")
    ax.add_patch(sidebar_rect)
    ax.text(sidebar_x + 1.6, 4.65, "7 Criteria", fontsize=8,
            fontweight="bold", ha="center", color="#333333")

    criteria_items = [
        ("(1) Cellular Org.", "#56B4E9"),
        ("(2) Metabolism", "#D55E00"),
        ("(3) Homeostasis", "#009E73"),
        ("(4) Growth/Dev.", "#CC79A7"),
        ("(5) Reproduction", "#0072B2"),
        ("(6) Response", "#009E73"),
        ("(7) Evolution", "#E69F00"),
    ]
    for j, (label, color) in enumerate(criteria_items):
        yy = 4.25 - j * 0.47
        ax.plot(sidebar_x + 0.3, yy, "s", color=color, markersize=5)
        ax.text(sidebar_x + 0.55, yy, label, fontsize=6.5, color="#333333",
                va="center")

    fig.savefig(FIG_DIR / "fig_architecture.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_architecture.pdf'}")


PROXY_COLORS = {
    "counter": "#56B4E9",  # sky blue
    "toy": "#E69F00",      # orange
    "graph": "#009E73",    # bluish green
}

PROXY_LABELS = {
    "counter": "Counter (minimal)",
    "toy": "Toy (single-step + waste)",
    "graph": "Graph (multi-step network)",
}


def load_json(path: Path) -> list[dict]:
    """Load experiment results from a JSON file."""
    with open(path) as f:
        return json.load(f)


def generate_proxy() -> None:
    """Figure 3: Proxy control comparison — 3 metabolism modes."""
    exp_dir = PROJECT_ROOT / "experiments"
    modes = ["counter", "toy", "graph"]

    # Collect time-series data per mode, skipping missing files
    available_modes = []
    mode_data: dict[str, dict[int, list[float]]] = {}
    for mode in modes:
        path = exp_dir / f"proxy_{mode}.json"
        if not path.exists():
            print(f"  SKIP mode '{mode}': {path} not found")
            continue
        available_modes.append(mode)
        results = load_json(path)
        step_vals: dict[int, list[float]] = defaultdict(list)
        for r in results:
            for s in r["samples"]:
                step_vals[s["step"]].append(s["alive_count"])
        mode_data[mode] = step_vals

    if len(available_modes) < 2:
        print("  SKIP figure: need at least 2 modes for comparison")
        return
    modes = available_modes

    fig, axes = plt.subplots(1, 3, figsize=(7, 2.4))

    # Panel 1: Alive count time-series
    ax = axes[0]
    for mode in modes:
        steps = sorted(mode_data[mode].keys())
        means = [np.mean(mode_data[mode][s]) for s in steps]
        sems = [np.std(mode_data[mode][s], ddof=1) / np.sqrt(len(mode_data[mode][s]))
                for s in steps]
        means, sems = np.array(means), np.array(sems)
        ax.plot(steps, means, color=PROXY_COLORS[mode], label=PROXY_LABELS[mode])
        ax.fill_between(steps, means - sems, means + sems,
                        color=PROXY_COLORS[mode], alpha=0.15)
    ax.set_xlabel("Step")
    ax.set_ylabel("Alive Count")
    ax.set_ylim(bottom=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Panel 2: Final alive count boxplot
    ax = axes[1]
    final_alive = {m: np.array([r["final_alive_count"] for r in load_json(exp_dir / f"proxy_{m}.json")])
                   for m in modes}
    bp = ax.boxplot([final_alive[m] for m in modes], labels=[m.capitalize() for m in modes],
                    patch_artist=True, widths=0.6)
    for patch, mode in zip(bp["boxes"], modes, strict=True):
        patch.set_facecolor(PROXY_COLORS[mode])
        patch.set_alpha(0.4)
    ax.set_ylabel("Final Alive")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Panel 3: Genome diversity boxplot (reuse loaded data from panel 2)
    ax = axes[2]
    final_div = {m: np.array([r["samples"][-1].get("genome_diversity", 0) for r in load_json(exp_dir / f"proxy_{m}.json")])
                 for m in modes}
    bp = ax.boxplot([final_div[m] for m in modes], labels=[m.capitalize() for m in modes],
                    patch_artist=True, widths=0.6)
    for patch, mode in zip(bp["boxes"], modes, strict=True):
        patch.set_facecolor(PROXY_COLORS[mode])
        patch.set_alpha(0.4)
    ax.set_ylabel("Genome Diversity")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Shared legend
    handles = [mlines.Line2D([], [], color=PROXY_COLORS[m], label=PROXY_LABELS[m])
               for m in modes]
    fig.legend(handles=handles, loc="upper center", ncol=3, fontsize=7,
               framealpha=0.9, bbox_to_anchor=(0.5, 1.08))

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_proxy.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_proxy.pdf'}")


def generate_evolution() -> None:
    """Figure 4: Evolution strengthening — long run + env shift."""
    exp_dir = PROJECT_ROOT / "experiments"

    conditions = {
        "long_normal": ("Normal", "#000000"),
        "long_no_evolution": ("No Evolution", "#CC79A7"),
        "shift_normal": ("Normal", "#000000"),
        "shift_no_evolution": ("No Evolution", "#CC79A7"),
    }

    # Load time-series
    cond_data: dict[str, dict[int, list[float]]] = {}
    for cond in conditions:
        path = exp_dir / f"evolution_{cond}.json"
        if not path.exists():
            print(f"  SKIP: {path} not found")
            return
        results = load_json(path)
        step_vals: dict[int, list[float]] = defaultdict(list)
        for r in results:
            for s in r["samples"]:
                step_vals[s["step"]].append(s["alive_count"])
        cond_data[cond] = step_vals

    fig, axes = plt.subplots(2, 1, figsize=(3.4, 4.0), sharex=False)

    # Top: Long run (10K steps)
    ax = axes[0]
    for cond in ["long_normal", "long_no_evolution"]:
        label, color = conditions[cond]
        steps = sorted(cond_data[cond].keys())
        means = [np.mean(cond_data[cond][s]) for s in steps]
        sems = [np.std(cond_data[cond][s], ddof=1) / np.sqrt(len(cond_data[cond][s]))
                for s in steps]
        means, sems = np.array(means), np.array(sems)
        ls = "-" if "normal" in cond and "no_" not in cond else "--"
        ax.plot(steps, means, color=color, linestyle=ls, label=label)
        ax.fill_between(steps, means - sems, means + sems,
                        color=color, alpha=0.15)
    ax.set_ylabel("Alive Count")
    ax.set_title("Long run (10,000 steps)", fontsize=9)
    ax.set_ylim(bottom=0)
    ax.legend(loc="lower right", fontsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Bottom: Shift run (5K steps)
    ax = axes[1]
    for cond in ["shift_normal", "shift_no_evolution"]:
        label, color = conditions[cond]
        steps = sorted(cond_data[cond].keys())
        means = [np.mean(cond_data[cond][s]) for s in steps]
        sems = [np.std(cond_data[cond][s], ddof=1) / np.sqrt(len(cond_data[cond][s]))
                for s in steps]
        means, sems = np.array(means), np.array(sems)
        ls = "-" if "normal" in cond and "no_" not in cond else "--"
        ax.plot(steps, means, color=color, linestyle=ls, label=label)
        ax.fill_between(steps, means - sems, means + sems,
                        color=color, alpha=0.15)
    ax.axvline(x=2500, color="#888888", linestyle=":", linewidth=0.8, label="Env. shift")
    ax.set_xlabel("Step")
    ax.set_ylabel("Alive Count")
    ax.set_title("Environmental shift at step 2,500", fontsize=9)
    ax.set_ylim(bottom=0)
    ax.legend(loc="lower right", fontsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_evolution.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_evolution.pdf'}")


def generate_homeostasis() -> None:
    """Figure 5: Homeostasis trajectory — internal state regulation over time.

    Panel A: mean internal_state_mean[0] over time for Normal vs No Homeostasis.
    Panel B: mean internal_state_std[0] over time — population-level variance.
    """
    exp_dir = PROJECT_ROOT / "experiments"
    conditions = {
        "normal": ("Normal", "#000000", "-"),
        "no_homeostasis": ("No Homeostasis", "#009E73", "--"),
    }

    # Load JSON data and extract internal_state trajectories
    cond_data: dict[str, dict[int, list[tuple[float, float]]]] = {}
    for cond, (_label, _color, _ls) in conditions.items():
        path = exp_dir / f"final_graph_{cond}.json"
        if not path.exists():
            print(f"  SKIP: {path} not found")
            return
        results = load_json(path)
        step_vals: dict[int, list[tuple[float, float]]] = defaultdict(list)
        for r in results:
            for s in r["samples"]:
                is_mean = s.get("internal_state_mean", [0, 0, 0, 0])
                is_std = s.get("internal_state_std", [0, 0, 0, 0])
                step_vals[s["step"]].append((is_mean[0], is_std[0]))
        cond_data[cond] = step_vals

    # Check that data has non-zero internal_state values
    sample_vals = list(cond_data["normal"].values())
    if not sample_vals or all(v[0] == 0.0 for v in sample_vals[0]):
        print("  SKIP: internal_state_mean data is all zeros (regenerate JSONs)")
        return

    def _plot_panel(ax, val_index: int, conditions, cond_data):
        """Plot one panel of the homeostasis figure (mean±SEM for each condition)."""
        for cond, (label, color, ls) in conditions.items():
            steps = sorted(cond_data[cond].keys())
            means = []
            sems = []
            for step in steps:
                vals = [v[val_index] for v in cond_data[cond][step]]
                arr = np.array(vals)
                means.append(arr.mean())
                sems.append(arr.std(ddof=1) / np.sqrt(len(arr)) if len(arr) >= 2 else 0.0)
            means_arr = np.array(means)
            sems_arr = np.array(sems)
            lw = 2.0 if cond == "normal" else 1.2
            ax.plot(steps, means_arr, color=color, linewidth=lw, linestyle=ls, label=label)
            ax.fill_between(steps, means_arr - sems_arr, means_arr + sems_arr,
                            color=color, alpha=0.15)
        ax.set_xlabel("Simulation Step")
        ax.set_xlim(0, 2000)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig, axes = plt.subplots(1, 2, figsize=(7, 2.8))

    # Panel A: internal_state_mean[0] over time
    _plot_panel(axes[0], 0, conditions, cond_data)
    axes[0].set_ylabel("Internal State Mean [0]")
    axes[0].set_title("(A) Homeostatic Regulation", fontsize=9)
    axes[0].set_ylim(0, 1)
    axes[0].legend(loc="lower left", fontsize=7)

    # Panel B: internal_state_std[0] over time
    _plot_panel(axes[1], 1, conditions, cond_data)
    axes[1].set_ylabel("Internal State Std [0]")
    axes[1].set_title("(B) Population Variance", fontsize=9)
    axes[1].set_ylim(bottom=0)
    axes[1].legend(loc="upper left", fontsize=7)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_homeostasis.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_homeostasis.pdf'}")


if __name__ == "__main__":
    print("Generating paper figures...")

    print("Figure 1: Architecture diagram")
    generate_architecture()

    print("Figure 2: Time-series plot")
    data = parse_tsv(DATA_TSV)
    print(f"  Parsed {len(data)} rows from {DATA_TSV.name}")
    generate_timeseries(data)

    print("Figure 3: Proxy control comparison")
    generate_proxy()

    print("Figure 4: Evolution strengthening")
    generate_evolution()

    print("Figure 5: Homeostasis trajectory")
    generate_homeostasis()

    print("Done.")
