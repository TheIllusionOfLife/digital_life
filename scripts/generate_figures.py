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
        ax.plot(
            steps,
            means,
            color=color,
            linewidth=lw,
            linestyle=ls,
            label=LABELS[condition],
            zorder=10 if condition == "normal" else 5,
        )
        ax.fill_between(
            steps, means - sems, means + sems, color=color, alpha=0.15, zorder=2
        )

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
        (0.3, 0.3),
        9.4,
        5.9,
        boxstyle="round,pad=0.1",
        facecolor="#F5F5F5",
        edgecolor="#333333",
        linewidth=1.5,
    )
    ax.add_patch(env_rect)
    ax.text(
        5.0,
        5.85,
        "Environment (Toroidal 2D, 100$\\times$100)",
        ha="center",
        va="center",
        fontsize=10,
        fontweight="bold",
        color="#333333",
    )

    # Resource field
    ax.text(
        1.2,
        5.35,
        "Resource Field",
        ha="left",
        va="center",
        fontsize=7,
        fontstyle="italic",
        color="#666666",
    )

    # Single organism shown in detail (left side)
    ox, oy = 0.8, 0.8
    org_rect = mpatches.FancyBboxPatch(
        (ox, oy),
        4.8,
        4.2,
        boxstyle="round,pad=0.08",
        facecolor="#FFFFFF",
        edgecolor="#0072B2",
        linewidth=1.2,
    )
    ax.add_patch(org_rect)
    ax.text(
        ox + 2.4,
        oy + 3.85,
        "Organism (10-50 per environment)",
        ha="center",
        va="center",
        fontsize=8,
        fontweight="bold",
        color="#0072B2",
    )

    # Internal components (wider boxes for the single organism)
    components = [
        ("Genome\n(7 segments, 256 floats)", ox + 0.2, oy + 2.7, 2.1, 0.85, "#E69F00"),
        ("NN Controller\n(8>16>4, 212 wt)", ox + 2.5, oy + 2.7, 2.1, 0.85, "#009E73"),
        (
            "Graph Metabolism\n(2-4 nodes, directed)",
            ox + 0.2,
            oy + 1.3,
            2.1,
            0.85,
            "#D55E00",
        ),
        (
            "Boundary Maintenance\n(10-50 swarm agents)",
            ox + 2.5,
            oy + 1.3,
            2.1,
            0.85,
            "#56B4E9",
        ),
    ]

    for label, cx, cy, w, h, color in components:
        comp_rect = mpatches.FancyBboxPatch(
            (cx, cy),
            w,
            h,
            boxstyle="round,pad=0.05",
            facecolor=color,
            edgecolor="none",
            alpha=0.2,
        )
        ax.add_patch(comp_rect)
        comp_border = mpatches.FancyBboxPatch(
            (cx, cy),
            w,
            h,
            boxstyle="round,pad=0.05",
            facecolor="none",
            edgecolor=color,
            linewidth=0.8,
        )
        ax.add_patch(comp_border)
        ax.text(
            cx + w / 2,
            cy + h / 2,
            label,
            ha="center",
            va="center",
            fontsize=6,
            color="#333333",
        )

    # Arrows: Genome -> NN, Genome -> Metabolism
    ax.annotate(
        "",
        xy=(ox + 2.5, oy + 3.12),
        xytext=(ox + 2.3, oy + 3.12),
        arrowprops=dict(arrowstyle="->", color="#888", lw=0.8),
    )
    ax.annotate(
        "",
        xy=(ox + 1.25, oy + 2.7),
        xytext=(ox + 1.25, oy + 2.15),
        arrowprops=dict(arrowstyle="->", color="#888", lw=0.8),
    )
    # NN -> Boundary (response to stimuli)
    ax.annotate(
        "",
        xy=(ox + 3.55, oy + 2.7),
        xytext=(ox + 3.55, oy + 2.15),
        arrowprops=dict(arrowstyle="->", color="#888", lw=0.8),
    )
    # Metabolism <-> Boundary (energy <-> integrity)
    ax.annotate(
        "",
        xy=(ox + 2.5, oy + 1.72),
        xytext=(ox + 2.3, oy + 1.72),
        arrowprops=dict(arrowstyle="<->", color="#888", lw=0.8),
    )

    # Internal state label
    ax.text(
        ox + 2.4,
        oy + 0.45,
        "Internal State Vector (homeostatic regulation)",
        ha="center",
        va="center",
        fontsize=6,
        fontstyle="italic",
        color="#666666",
    )

    # Criteria mapping sidebar (right side, clearly separated)
    sidebar_x = 6.2
    sidebar_rect = mpatches.FancyBboxPatch(
        (sidebar_x, 0.8),
        3.2,
        4.2,
        boxstyle="round,pad=0.08",
        facecolor="#FFFFFF",
        edgecolor="#999999",
        linewidth=0.8,
        linestyle="--",
    )
    ax.add_patch(sidebar_rect)
    ax.text(
        sidebar_x + 1.6,
        4.65,
        "7 Criteria",
        fontsize=8,
        fontweight="bold",
        ha="center",
        color="#333333",
    )

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
        ax.text(sidebar_x + 0.55, yy, label, fontsize=6.5, color="#333333", va="center")

    fig.savefig(FIG_DIR / "fig_architecture.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_architecture.pdf'}")


PROXY_COLORS = {
    "counter": "#56B4E9",  # sky blue
    "toy": "#E69F00",  # orange
    "graph": "#009E73",  # bluish green
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
        sems = [
            np.std(mode_data[mode][s], ddof=1) / np.sqrt(len(mode_data[mode][s]))
            for s in steps
        ]
        means, sems = np.array(means), np.array(sems)
        ax.plot(steps, means, color=PROXY_COLORS[mode], label=PROXY_LABELS[mode])
        ax.fill_between(
            steps, means - sems, means + sems, color=PROXY_COLORS[mode], alpha=0.15
        )
    ax.set_xlabel("Step")
    ax.set_ylabel("Alive Count")
    ax.set_ylim(bottom=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Panel 2: Final alive count boxplot
    ax = axes[1]
    final_alive = {
        m: np.array(
            [r["final_alive_count"] for r in load_json(exp_dir / f"proxy_{m}.json")]
        )
        for m in modes
    }
    bp = ax.boxplot(
        [final_alive[m] for m in modes],
        tick_labels=[m.capitalize() for m in modes],
        patch_artist=True,
        widths=0.6,
    )
    for patch, mode in zip(bp["boxes"], modes, strict=True):
        patch.set_facecolor(PROXY_COLORS[mode])
        patch.set_alpha(0.4)
    ax.set_ylabel("Final Alive")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Panel 3: Genome diversity boxplot (reuse loaded data from panel 2)
    ax = axes[2]
    final_div = {
        m: np.array(
            [
                r["samples"][-1].get("genome_diversity", 0)
                for r in load_json(exp_dir / f"proxy_{m}.json")
            ]
        )
        for m in modes
    }
    bp = ax.boxplot(
        [final_div[m] for m in modes],
        tick_labels=[m.capitalize() for m in modes],
        patch_artist=True,
        widths=0.6,
    )
    for patch, mode in zip(bp["boxes"], modes, strict=True):
        patch.set_facecolor(PROXY_COLORS[mode])
        patch.set_alpha(0.4)
    ax.set_ylabel("Genome Diversity")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Shared legend
    handles = [
        mlines.Line2D([], [], color=PROXY_COLORS[m], label=PROXY_LABELS[m])
        for m in modes
    ]
    fig.legend(
        handles=handles,
        loc="upper center",
        ncol=3,
        fontsize=7,
        framealpha=0.9,
        bbox_to_anchor=(0.5, 1.08),
    )

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
        sems = [
            np.std(cond_data[cond][s], ddof=1) / np.sqrt(len(cond_data[cond][s]))
            for s in steps
        ]
        means, sems = np.array(means), np.array(sems)
        ls = "-" if "normal" in cond and "no_" not in cond else "--"
        ax.plot(steps, means, color=color, linestyle=ls, label=label)
        ax.fill_between(steps, means - sems, means + sems, color=color, alpha=0.15)
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
        sems = [
            np.std(cond_data[cond][s], ddof=1) / np.sqrt(len(cond_data[cond][s]))
            for s in steps
        ]
        means, sems = np.array(means), np.array(sems)
        ls = "-" if "normal" in cond and "no_" not in cond else "--"
        ax.plot(steps, means, color=color, linestyle=ls, label=label)
        ax.fill_between(steps, means - sems, means + sems, color=color, alpha=0.15)
    ax.axvline(
        x=2500, color="#888888", linestyle=":", linewidth=0.8, label="Env. shift"
    )
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
                sems.append(
                    arr.std(ddof=1) / np.sqrt(len(arr)) if len(arr) >= 2 else 0.0
                )
            means_arr = np.array(means)
            sems_arr = np.array(sems)
            lw = 2.0 if cond == "normal" else 1.2
            ax.plot(
                steps, means_arr, color=color, linewidth=lw, linestyle=ls, label=label
            )
            ax.fill_between(
                steps,
                means_arr - sems_arr,
                means_arr + sems_arr,
                color=color,
                alpha=0.15,
            )
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


def generate_ablation_distributions() -> None:
    """Figure 6: Violin/strip plots showing per-seed distributions for each condition."""
    exp_dir = PROJECT_ROOT / "experiments"

    # Collect final alive counts per condition
    condition_data: dict[str, np.ndarray] = {}
    for condition in CONDITION_ORDER:
        path = exp_dir / f"final_graph_{condition}.json"
        if not path.exists():
            print(f"  SKIP: {path} not found")
            return
        results = load_json(path)
        condition_data[condition] = np.array(
            [r["final_alive_count"] for r in results if "samples" in r]
        )

    if condition_data["normal"].size == 0:
        print("  SKIP: No valid 'normal' condition data found")
        return
    normal_mean = float(np.mean(condition_data["normal"]))

    fig, ax = plt.subplots(figsize=(7, 3.0))

    positions = list(range(len(CONDITION_ORDER)))
    data_list = [condition_data[c] for c in CONDITION_ORDER]

    parts = ax.violinplot(
        data_list,
        positions=positions,
        showmeans=False,
        showmedians=False,
        showextrema=False,
    )
    for i, body in enumerate(parts["bodies"]):
        color = COLORS[CONDITION_ORDER[i]]
        body.set_facecolor(color)
        body.set_alpha(0.3)
        body.set_edgecolor(color)
        body.set_linewidth(0.8)

    # Overlay individual data points (strip plot)
    rng = np.random.default_rng(0)
    for i, condition in enumerate(CONDITION_ORDER):
        vals = condition_data[condition]
        jitter = rng.uniform(-0.15, 0.15, size=len(vals))
        ax.scatter(
            i + jitter,
            vals,
            s=8,
            alpha=0.6,
            color=COLORS[condition],
            edgecolors="none",
            zorder=5,
        )
        # Median marker
        ax.scatter(
            i,
            np.median(vals),
            s=30,
            color=COLORS[condition],
            edgecolors="white",
            linewidths=0.8,
            zorder=10,
            marker="D",
        )

    # Normal baseline reference line
    ax.axhline(
        y=normal_mean,
        color="#000000",
        linestyle=":",
        linewidth=0.8,
        alpha=0.5,
        label=f"Normal mean ({normal_mean:.0f})",
    )

    ax.set_xticks(positions)
    ax.set_xticklabels([LABELS[c] for c in CONDITION_ORDER], rotation=30, ha="right")
    ax.set_ylabel("Final Alive Count ($N_T$)")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper right", fontsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_distributions.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_distributions.pdf'}")


def generate_graded() -> None:
    """Figure 7: Graded ablation dose-response curve."""
    exp_dir = PROJECT_ROOT / "experiments"
    levels = [1.0, 0.75, 0.5, 0.25, 0.0]

    level_data: dict[float, np.ndarray] = {}
    for level in levels:
        path = exp_dir / f"graded_graded_{level:.2f}.json"
        if not path.exists():
            print(f"  SKIP: {path} not found")
            return
        results = load_json(path)
        level_data[level] = np.array(
            [r["final_alive_count"] for r in results if "samples" in r]
        )

    fig, ax = plt.subplots(figsize=(3.4, 2.8))

    medians = [float(np.median(level_data[lv])) for lv in levels]
    q25s = [float(np.percentile(level_data[lv], 25)) for lv in levels]
    q75s = [float(np.percentile(level_data[lv], 75)) for lv in levels]

    ax.plot(levels, medians, "o-", color="#0072B2", linewidth=1.5, markersize=5)
    ax.fill_between(levels, q25s, q75s, color="#0072B2", alpha=0.2)

    ax.set_xlabel("Metabolism Efficiency Multiplier")
    ax.set_ylabel("Final Alive Count ($N_T$)")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(bottom=0)
    ax.invert_xaxis()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_graded.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_graded.pdf'}")


def generate_cyclic() -> None:
    """Figure 8: Cyclic environment — population dynamics under periodic stress."""
    exp_dir = PROJECT_ROOT / "experiments"

    conditions = {
        "cyclic_evo_on": ("Evolution On", "#000000", "-"),
        "cyclic_evo_off": ("Evolution Off", "#CC79A7", "--"),
    }

    cond_data: dict[str, dict[int, list[float]]] = {}
    for cond in conditions:
        path = exp_dir / f"cyclic_{cond}.json"
        if not path.exists():
            print(f"  SKIP: {path} not found")
            return
        results = load_json(path)
        step_vals: dict[int, list[float]] = defaultdict(list)
        for r in results:
            for s in r["samples"]:
                step_vals[s["step"]].append(s["alive_count"])
        cond_data[cond] = step_vals

    fig, ax = plt.subplots(figsize=(3.4, 2.8))

    for cond, (label, color, ls) in conditions.items():
        steps = sorted(cond_data[cond].keys())
        means = [np.mean(cond_data[cond][s]) for s in steps]
        sems = [
            np.std(cond_data[cond][s], ddof=1) / np.sqrt(len(cond_data[cond][s]))
            for s in steps
        ]
        means, sems = np.array(means), np.array(sems)
        lw = 2.0 if "evo_on" in cond else 1.2
        ax.plot(steps, means, color=color, linewidth=lw, linestyle=ls, label=label)
        ax.fill_between(steps, means - sems, means + sems, color=color, alpha=0.15)

    # Mark cycle boundaries
    cycle_period = 2000
    for i in range(1, 6):
        ax.axvline(x=i * cycle_period, color="#888888", linestyle=":", linewidth=0.5)

    # Shade low-rate phases
    max_step = max(max(cond_data[c].keys()) for c in conditions)
    phase = 0
    for start in range(0, int(max_step) + 1, cycle_period):
        if phase % 2 == 1:
            ax.axvspan(
                start, min(start + cycle_period, max_step), color="#FF0000", alpha=0.03
            )
        phase += 1

    ax.set_xlabel("Simulation Step")
    ax.set_ylabel("Mean Alive Count ($n$=30)")
    ax.set_ylim(bottom=0)
    ax.legend(loc="lower right", fontsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_cyclic.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_cyclic.pdf'}")


def generate_phenotype() -> None:
    """Figure 9: Phenotype clustering scatter plot."""
    analysis_path = PROJECT_ROOT / "experiments" / "phenotype_analysis.json"
    if not analysis_path.exists():
        print(f"  SKIP: {analysis_path} not found")
        return

    with open(analysis_path) as f:
        analysis = json.load(f)

    traits = np.array(analysis.get("traits", []))
    labels = np.array(analysis.get("labels", []))

    if traits.shape[0] < 4 or traits.shape[1] < 2:
        print("  SKIP: insufficient trait data for phenotype plot")
        return

    # Use PCA for 2D projection if >2 dimensions
    from sklearn.decomposition import PCA

    pca = PCA(n_components=2, random_state=42)
    proj = pca.fit_transform(traits)

    n_clusters = analysis.get("n_clusters", 2)
    cluster_colors = ["#0072B2", "#D55E00", "#009E73", "#E69F00", "#CC79A7"]

    fig, ax = plt.subplots(figsize=(3.4, 3.0))

    for c in range(n_clusters):
        mask = labels == c
        ax.scatter(
            proj[mask, 0],
            proj[mask, 1],
            s=15,
            alpha=0.6,
            color=cluster_colors[c % len(cluster_colors)],
            label=f"Cluster {c} (n={mask.sum()})",
            edgecolors="none",
        )

    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.0%} var)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.0%} var)")
    ax.legend(loc="best", fontsize=7, markerscale=1.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_phenotype.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_phenotype.pdf'}")


def generate_coupling() -> None:
    """Figure 10: Criterion coupling graph — directed edges with correlation coefficients."""
    analysis_path = PROJECT_ROOT / "experiments" / "coupling_analysis.json"
    if not analysis_path.exists():
        print(f"  SKIP: {analysis_path} not found")
        return

    with open(analysis_path) as f:
        analysis = json.load(f)

    pairs = analysis.get("pairs", [])
    if not pairs:
        print("  SKIP: no coupling pairs found")
        return

    fig, ax = plt.subplots(figsize=(4.0, 4.0))
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.5, 1.5)
    ax.set_aspect("equal")
    ax.axis("off")

    # 7 criteria arranged in a circle
    criteria = [
        "Cellular Org.",
        "Metabolism",
        "Homeostasis",
        "Growth/Dev.",
        "Reproduction",
        "Response",
        "Evolution",
    ]
    short_names = {
        "energy_mean": "Metabolism",
        "boundary_mean": "Cellular Org.",
        "internal_state_mean_0": "Homeostasis",
    }
    # Ensure all metric keys from coupling data have a mapping so no pairs are silently dropped
    for pair in pairs:
        for key in ("var_a", "var_b"):
            metric = pair[key]
            if metric not in short_names:
                # Generate a readable fallback from the metric key
                short_names[metric] = metric.replace("_", " ").title()

    n = len(criteria)
    angles = [2 * np.pi * i / n - np.pi / 2 for i in range(n)]
    positions = {name: (np.cos(a), np.sin(a)) for name, a in zip(criteria, angles)}

    # Draw nodes
    node_colors = [
        "#56B4E9",
        "#D55E00",
        "#009E73",
        "#CC79A7",
        "#0072B2",
        "#E69F00",
        "#CC79A7",
    ]
    for i, (name, (x, y)) in enumerate(positions.items()):
        circle = plt.Circle(
            (x, y),
            0.18,
            facecolor=node_colors[i],
            alpha=0.3,
            edgecolor=node_colors[i],
            linewidth=1.2,
        )
        ax.add_patch(circle)
        ax.text(x, y, name, ha="center", va="center", fontsize=5.5, fontweight="bold")

    # Draw edges from coupling analysis
    for pair in pairs:
        var_a = short_names.get(pair["var_a"], pair["var_a"])
        var_b = short_names.get(pair["var_b"], pair["var_b"])
        r = pair["best_pearson_r"]
        lag = pair["best_lag"]

        if var_a not in positions or var_b not in positions:
            continue

        x1, y1 = positions[var_a]
        x2, y2 = positions[var_b]

        # Shorten arrow to not overlap nodes
        dx, dy = x2 - x1, y2 - y1
        dist = np.sqrt(dx**2 + dy**2)
        if dist < 0.01:
            continue
        shrink = 0.22 / dist
        sx1, sy1 = x1 + dx * shrink, y1 + dy * shrink
        sx2, sy2 = x2 - dx * shrink, y2 - dy * shrink

        lw = max(0.5, min(3.0, abs(r) * 4))
        color = "#0072B2" if r > 0 else "#D55E00"
        ax.annotate(
            "",
            xy=(sx2, sy2),
            xytext=(sx1, sy1),
            arrowprops=dict(arrowstyle="->", color=color, lw=lw),
        )

        # Label at midpoint
        mx, my = (sx1 + sx2) / 2, (sy1 + sy2) / 2
        ax.text(
            mx,
            my + 0.08,
            f"r={r:.2f}\nlag={lag}",
            ha="center",
            va="center",
            fontsize=5,
            color=color,
            bbox=dict(
                boxstyle="round,pad=0.1", facecolor="white", edgecolor="none", alpha=0.8
            ),
        )

    # Intervention effects text box (from coupling_analysis.json)
    interventions = analysis.get("intervention_effects", {})
    if interventions:
        matrix = interventions.get("matrix", [])
        # Find top 3 by max absolute pct_change across metrics
        effects_summary = []
        for row in matrix:
            criterion = row["ablated_criterion"]
            metric_effects = []
            for key in (
                "energy_mean",
                "waste_mean",
                "boundary_mean",
                "internal_state_mean_0",
            ):
                val = row.get(key, 0.0)
                if abs(val) > 20:
                    short_key = key.replace("_mean", "").replace("_0", "")
                    sign = "-" if val > 0 else "+"
                    metric_effects.append(f"{short_key} {sign}{abs(val):.0f}%")
            if metric_effects:
                effects_summary.append(f"  {criterion}: {', '.join(metric_effects)}")
        if effects_summary:
            # Show top entries (sorted by first effect magnitude)
            box_text = "Intervention effects:\n" + "\n".join(effects_summary[:4])
            ax.text(
                -1.45,
                -1.45,
                box_text,
                fontsize=5,
                va="bottom",
                ha="left",
                family="monospace",
                bbox=dict(
                    boxstyle="round,pad=0.3",
                    facecolor="#F5F5F5",
                    edgecolor="0.7",
                    alpha=0.9,
                ),
            )

    # Design-based edges (from Table 2)
    design_edges = [
        ("Growth/Dev.", "Reproduction", "gate"),
        ("Metabolism", "Cellular Org.", "energy"),
        ("Homeostasis", "Cellular Org.", "repair"),
    ]
    for src, dst, _label in design_edges:
        if src not in positions or dst not in positions:
            continue
        # Check if already drawn from data
        already = any(
            (short_names.get(p["var_a"]) == src and short_names.get(p["var_b"]) == dst)
            or (
                short_names.get(p["var_a"]) == dst
                and short_names.get(p["var_b"]) == src
            )
            for p in pairs
        )
        if already:
            continue
        x1, y1 = positions[src]
        x2, y2 = positions[dst]
        dx, dy = x2 - x1, y2 - y1
        dist = np.sqrt(dx**2 + dy**2)
        if dist < 0.01:
            continue
        shrink = 0.22 / dist
        sx1, sy1 = x1 + dx * shrink, y1 + dy * shrink
        sx2, sy2 = x2 - dx * shrink, y2 - dy * shrink
        ax.annotate(
            "",
            xy=(sx2, sy2),
            xytext=(sx1, sy1),
            arrowprops=dict(arrowstyle="->", color="#888888", lw=0.8, linestyle="--"),
        )

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_coupling.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_coupling.pdf'}")


def generate_spatial() -> None:
    """Figure 11: Spatial cohesion under boundary ablation."""
    exp_dir = PROJECT_ROOT / "experiments"

    conditions = {
        "normal": ("Normal", "#000000"),
        "no_boundary": ("No Boundary", "#56B4E9"),
    }

    cond_data: dict[str, list[float]] = {}
    for cond, (_label, _color) in conditions.items():
        path = exp_dir / f"spatial_{cond}.json"
        if not path.exists():
            print(f"  SKIP: {path} not found")
            return
        results = load_json(path)
        # Collect final spatial_cohesion_mean from each seed
        finals = []
        for r in results:
            if r.get("samples"):
                last = r["samples"][-1]
                finals.append(last.get("spatial_cohesion_mean", 0.0))
        cond_data[cond] = finals

    if not all(cond_data.values()):
        print("  SKIP: insufficient spatial data")
        return

    fig, ax = plt.subplots(figsize=(3.4, 2.8))

    cond_list = list(conditions.keys())
    data_list = [np.array(cond_data[c]) for c in cond_list]
    labels = [conditions[c][0] for c in cond_list]
    colors = [conditions[c][1] for c in cond_list]

    bp = ax.boxplot(data_list, tick_labels=labels, patch_artist=True, widths=0.5)
    for patch, color in zip(bp["boxes"], colors, strict=True):
        patch.set_facecolor(color)
        patch.set_alpha(0.3)

    # Overlay individual points
    rng = np.random.default_rng(0)
    for i, (vals, color) in enumerate(zip(data_list, colors, strict=True)):
        jitter = rng.uniform(-0.1, 0.1, size=len(vals))
        ax.scatter(
            i + 1 + jitter,
            vals,
            s=12,
            alpha=0.5,
            color=color,
            edgecolors="none",
            zorder=5,
        )

    ax.set_ylabel("Spatial Cohesion (mean pairwise dist.)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_spatial.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_spatial.pdf'}")


def generate_lineage() -> None:
    """Figure 12: Phylogenetic depth plot — generation vs step, colored by seed."""
    analysis_path = PROJECT_ROOT / "experiments" / "lineage_analysis.json"
    if not analysis_path.exists():
        print(f"  SKIP: {analysis_path} not found")
        return

    with open(analysis_path) as f:
        analysis = json.load(f)

    events = analysis.get("events", [])
    if len(events) < 5:
        print("  SKIP: insufficient lineage events")
        return

    fig, ax = plt.subplots(figsize=(3.4, 2.8))

    steps = [e["step"] for e in events]
    gens = [e["generation"] for e in events]
    seeds = [e["seed"] for e in events]

    ax.scatter(steps, gens, c=seeds, s=4, alpha=0.4, cmap="viridis", edgecolors="none")
    ax.set_xlabel("Simulation Step")
    ax.set_ylabel("Generation")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Depth stats annotation
    ds = analysis.get("depth_stats", {})
    if ds:
        ax.text(
            0.98,
            0.95,
            f"Max gen: {ds.get('max', 0)}\nMean: {ds.get('mean', 0):.1f}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=7,
            bbox=dict(
                boxstyle="round,pad=0.3", facecolor="white", edgecolor="0.8", alpha=0.9
            ),
        )

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_lineage.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_lineage.pdf'}")


def generate_orthogonal() -> None:
    """Figure 14: Orthogonal outcome metrics — spatial cohesion and median lifespan per condition."""
    exp_dir = PROJECT_ROOT / "experiments"

    # Panel A: spatial cohesion from final_graph_{condition}.json (last sample)
    # Panel B: median lifespan from lifespans list
    spatial_data: dict[str, list[float]] = {}
    lifespan_data: dict[str, list[float]] = {}

    for condition in CONDITION_ORDER:
        path = exp_dir / f"final_graph_{condition}.json"
        if not path.exists():
            print(f"  SKIP: {path} not found")
            return
        results = load_json(path)
        cohesions = []
        medians = []
        for r in results:
            if r.get("samples"):
                last = r["samples"][-1]
                cohesions.append(last.get("spatial_cohesion_mean", 0.0))
            ls = r.get("lifespans", [])
            if ls:
                medians.append(float(sorted(ls)[len(ls) // 2]))
            else:
                medians.append(0.0)
        spatial_data[condition] = cohesions
        lifespan_data[condition] = medians

    normal_cohesion_mean = float(np.mean(spatial_data.get("normal", [0])))
    normal_lifespan_mean = float(np.mean(lifespan_data.get("normal", [0])))

    fig, axes = plt.subplots(1, 2, figsize=(7, 3.0))

    # Panel A: Spatial cohesion violin+strip
    ax = axes[0]
    positions = list(range(len(CONDITION_ORDER)))
    data_list = [np.array(spatial_data[c]) for c in CONDITION_ORDER]

    parts = ax.violinplot(
        data_list,
        positions=positions,
        showmeans=False,
        showmedians=False,
        showextrema=False,
    )
    for i, body in enumerate(parts["bodies"]):
        color = COLORS[CONDITION_ORDER[i]]
        body.set_facecolor(color)
        body.set_alpha(0.3)
        body.set_edgecolor(color)
        body.set_linewidth(0.8)

    rng = np.random.default_rng(0)
    for i, condition in enumerate(CONDITION_ORDER):
        vals = np.array(spatial_data[condition])
        jitter = rng.uniform(-0.15, 0.15, size=len(vals))
        ax.scatter(
            i + jitter,
            vals,
            s=8,
            alpha=0.6,
            color=COLORS[condition],
            edgecolors="none",
            zorder=5,
        )
        ax.scatter(
            i,
            np.median(vals),
            s=30,
            color=COLORS[condition],
            edgecolors="white",
            linewidths=0.8,
            zorder=10,
            marker="D",
        )

    ax.axhline(
        y=normal_cohesion_mean,
        color="#000000",
        linestyle=":",
        linewidth=0.8,
        alpha=0.5,
        label=f"Normal mean ({normal_cohesion_mean:.1f})",
    )
    ax.set_xticks(positions)
    ax.set_xticklabels([LABELS[c] for c in CONDITION_ORDER], rotation=30, ha="right")
    ax.set_ylabel("Spatial Cohesion")
    ax.set_title("(A) Spatial Cohesion", fontsize=9)
    ax.legend(loc="upper right", fontsize=6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Panel B: Median lifespan violin+strip
    ax = axes[1]
    data_list = [np.array(lifespan_data[c]) for c in CONDITION_ORDER]

    parts = ax.violinplot(
        data_list,
        positions=positions,
        showmeans=False,
        showmedians=False,
        showextrema=False,
    )
    for i, body in enumerate(parts["bodies"]):
        color = COLORS[CONDITION_ORDER[i]]
        body.set_facecolor(color)
        body.set_alpha(0.3)
        body.set_edgecolor(color)
        body.set_linewidth(0.8)

    rng = np.random.default_rng(1)
    for i, condition in enumerate(CONDITION_ORDER):
        vals = np.array(lifespan_data[condition])
        jitter = rng.uniform(-0.15, 0.15, size=len(vals))
        ax.scatter(
            i + jitter,
            vals,
            s=8,
            alpha=0.6,
            color=COLORS[condition],
            edgecolors="none",
            zorder=5,
        )
        ax.scatter(
            i,
            np.median(vals),
            s=30,
            color=COLORS[condition],
            edgecolors="white",
            linewidths=0.8,
            zorder=10,
            marker="D",
        )

    ax.axhline(
        y=normal_lifespan_mean,
        color="#000000",
        linestyle=":",
        linewidth=0.8,
        alpha=0.5,
        label=f"Normal mean ({normal_lifespan_mean:.0f})",
    )
    ax.set_xticks(positions)
    ax.set_xticklabels([LABELS[c] for c in CONDITION_ORDER], rotation=30, ha="right")
    ax.set_ylabel("Median Lifespan (steps)")
    ax.set_title("(B) Median Lifespan", fontsize=9)
    ax.legend(loc="upper right", fontsize=6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_orthogonal.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_orthogonal.pdf'}")


def generate_evolution_evidence() -> None:
    """Figure 15: Evolution evidence — genome drift trajectories and cyclic recovery rates."""
    exp_dir = PROJECT_ROOT / "experiments"
    evidence_path = exp_dir / "evolution_evidence.json"
    if not evidence_path.exists():
        print(f"  SKIP: {evidence_path} not found")
        return

    with open(evidence_path) as f:
        evidence = json.load(f)

    drift = evidence.get("drift_trajectories", {})
    trajectory_steps = drift.get("trajectory_steps", [])
    trajectory_normal = drift.get("trajectory_normal_mean", [])
    trajectory_no_evo = drift.get("trajectory_no_evo_mean", [])

    if not trajectory_steps or not trajectory_normal:
        print("  SKIP: missing drift trajectory data")
        return

    cyclic = evidence.get("cyclic_recovery", {})
    per_cycle = cyclic.get("per_cycle", [])

    fig, axes = plt.subplots(1, 2, figsize=(7, 3.0))

    # Panel A: Genome drift trajectories
    ax = axes[0]
    ax.plot(
        trajectory_steps,
        trajectory_normal,
        color="#000000",
        linewidth=1.5,
        linestyle="-",
        label="Normal",
    )
    ax.plot(
        trajectory_steps,
        trajectory_no_evo,
        color="#CC79A7",
        linewidth=1.5,
        linestyle="--",
        label="No Evolution",
    )
    ax.set_xlabel("Simulation Step")
    ax.set_ylabel("Mean Genome Drift")
    ax.set_title("(A) Genome Drift Trajectories", fontsize=9)
    ax.legend(loc="upper left", fontsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Panel B: Per-cycle recovery rates
    ax = axes[1]
    if per_cycle:
        n_cycles = len(per_cycle)
        x = np.arange(n_cycles)
        width = 0.35
        evo_on_rates = [c["evo_on_rate_mean"] for c in per_cycle]
        evo_off_rates = [c["evo_off_rate_mean"] for c in per_cycle]
        cycle_labels = [f"{c['high_start']}-{c['high_end']}" for c in per_cycle]

        ax.bar(
            x - width / 2,
            evo_on_rates,
            width,
            label="Evo On",
            color="#000000",
            alpha=0.6,
        )
        ax.bar(
            x + width / 2,
            evo_off_rates,
            width,
            label="Evo Off",
            color="#CC79A7",
            alpha=0.6,
        )
        ax.set_xticks(x)
        ax.set_xticklabels(cycle_labels)
        ax.set_xlabel("Cycle Window (steps)")
    ax.set_ylabel("Recovery Rate")
    ax.set_title("(B) Per-Cycle Recovery Rates", fontsize=9)
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper right", fontsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_evolution_evidence.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_evolution_evidence.pdf'}")


def generate_persistent_clusters() -> None:
    """Figure 16: Per-organism phenotype clusters — PCA scatter at early vs late windows."""
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    analysis_path = PROJECT_ROOT / "experiments" / "phenotype_analysis.json"
    if not analysis_path.exists():
        print(f"  SKIP: {analysis_path} not found")
        return

    with open(analysis_path) as f:
        analysis = json.load(f)

    olp = analysis.get("organism_level_persistence")
    if not olp or "error" in olp:
        print("  SKIP: no organism_level_persistence data in phenotype_analysis.json")
        return

    ari = olp.get("adjusted_rand_index", 0.0)
    cluster_colors = ["#0072B2", "#D55E00"]

    fig, axes = plt.subplots(1, 2, figsize=(7, 3.0))

    n_shared_early = olp["early_window"]["n_shared_organisms"]
    n_shared_late = olp["late_window"]["n_shared_organisms"]

    for panel_idx, (traits_key, labels_key, window_key, title) in enumerate(
        [
            ("early_traits", "early_labels", "early_window",
             f"(A) Early Window (n={n_shared_early})"),
            ("late_traits", "late_labels", "late_window",
             f"(B) Late Window (n={n_shared_late})"),
        ]
    ):
        ax = axes[panel_idx]
        raw_traits = olp.get(traits_key, [])
        raw_labels = olp.get(labels_key, [])

        if len(raw_traits) < 4:
            ax.text(
                0.5, 0.5, "Insufficient data",
                ha="center", va="center", transform=ax.transAxes,
            )
            continue

        traits = np.array(raw_traits)
        labels = np.array(raw_labels)

        scaled = StandardScaler().fit_transform(traits)
        pca = PCA(n_components=2, random_state=42)
        proj = pca.fit_transform(scaled)

        for c in sorted(set(raw_labels)):
            mask = labels == c
            ax.scatter(
                proj[mask, 0],
                proj[mask, 1],
                s=12,
                alpha=0.5,
                color=cluster_colors[c % len(cluster_colors)],
                label=f"Cluster {c} (n={mask.sum()})",
                edgecolors="none",
            )

        ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.0%} var)")
        ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.0%} var)")
        ax.set_title(title, fontsize=9)
        ax.legend(loc="best", fontsize=6, markerscale=1.5)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # Annotate cluster proportions and silhouette
        window = olp.get(window_key, {})
        proportions = window.get("cluster_proportions", [])
        sil = window.get("silhouette_score", 0.0)
        prop_text = ", ".join(f"{p:.0%}" for p in proportions) if proportions else ""
        ax.text(
            0.02, 0.98,
            f"Prop: {prop_text}\nSil: {sil:.3f}",
            transform=ax.transAxes, ha="left", va="top", fontsize=6,
            bbox=dict(
                boxstyle="round,pad=0.2", facecolor="white",
                edgecolor="0.8", alpha=0.9,
            ),
        )

    fig.text(
        0.5, 0.01,
        f"Organism-level ARI: {ari:.3f} (early vs late window)",
        ha="center", va="bottom", fontsize=8,
        bbox=dict(
            boxstyle="round,pad=0.3", facecolor="#FFF9C4",
            edgecolor="0.8", alpha=0.9,
        ),
    )

    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(FIG_DIR / "fig_persistent_clusters.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_persistent_clusters.pdf'}")


def generate_cyclic_sweep() -> None:
    """Update cyclic figure with period sweep data."""
    exp_dir = PROJECT_ROOT / "experiments"
    periods = [500, 1000, 2000, 5000]

    # Collect final alive counts per period x condition
    period_data: dict[int, dict[str, list[float]]] = {}
    for period in periods:
        period_data[period] = {}
        for evo_label in ["evo_on", "evo_off"]:
            path = exp_dir / f"cyclic_sweep_sweep_p{period}_{evo_label}.json"
            if not path.exists():
                print(f"  SKIP: {path} not found")
                return
            results = load_json(path)
            period_data[period][evo_label] = [
                r["final_alive_count"] for r in results if "samples" in r
            ]

    fig, ax = plt.subplots(figsize=(3.4, 2.8))

    x = np.arange(len(periods))
    width = 0.35

    def safe_mean(arr: list[float]) -> float:
        return float(np.mean(arr)) if len(arr) >= 1 else np.nan

    def safe_sem(arr: list[float]) -> float:
        if len(arr) < 2:
            return 0.0
        return float(np.std(arr, ddof=1) / np.sqrt(len(arr)))

    evo_on_means = [safe_mean(period_data[p]["evo_on"]) for p in periods]
    evo_on_sems = [safe_sem(period_data[p]["evo_on"]) for p in periods]
    evo_off_means = [safe_mean(period_data[p]["evo_off"]) for p in periods]
    evo_off_sems = [safe_sem(period_data[p]["evo_off"]) for p in periods]

    ax.bar(
        x - width / 2,
        evo_on_means,
        width,
        yerr=evo_on_sems,
        label="Evolution On",
        color="#000000",
        alpha=0.6,
        capsize=3,
    )
    ax.bar(
        x + width / 2,
        evo_off_means,
        width,
        yerr=evo_off_sems,
        label="Evolution Off",
        color="#CC79A7",
        alpha=0.6,
        capsize=3,
    )

    ax.set_xlabel("Cycle Period (steps)")
    ax.set_ylabel("Final Alive Count")
    ax.set_xticks(x)
    ax.set_xticklabels([str(p) for p in periods])
    ax.set_ylim(bottom=0)
    ax.legend(loc="best", fontsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_cyclic_sweep.pdf", format="pdf")
    plt.close(fig)
    print(f"  Saved {FIG_DIR / 'fig_cyclic_sweep.pdf'}")


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

    print("Figure 6: Ablation distributions")
    generate_ablation_distributions()

    print("Figure 7: Graded ablation dose-response")
    generate_graded()

    print("Figure 8: Cyclic environment")
    generate_cyclic()

    print("Figure 9: Phenotype clustering")
    generate_phenotype()

    print("Figure 10: Coupling graph")
    generate_coupling()

    print("Figure 11: Spatial cohesion")
    generate_spatial()

    print("Figure 12: Lineage phylogeny")
    generate_lineage()

    print("Figure 13: Cyclic period sweep")
    generate_cyclic_sweep()

    print("Figure 14: Orthogonal metrics")
    generate_orthogonal()

    print("Figure 15: Evolution evidence")
    generate_evolution_evidence()

    print("Figure 16: Persistent clusters")
    generate_persistent_clusters()

    print("Done.")
