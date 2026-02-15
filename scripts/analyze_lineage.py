"""Lineage tree analysis.

Builds a phylogenetic tree from lineage events recorded in experiment JSON,
computing depth, breadth, and generational statistics.

Usage:
    uv run python scripts/analyze_lineage.py
"""

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "experiments" / "final_graph_normal.json"
OUTPUT_PATH = PROJECT_ROOT / "experiments" / "lineage_analysis.json"


def analyze_lineage(results: list[dict]) -> dict:
    """Analyze lineage events across all seeds."""
    all_depths = []
    all_breadths = []  # children per parent
    all_events = []

    for seed_idx, r in enumerate(results):
        events = r.get("lineage_events", [])
        if not events:
            continue

        # Build parent -> children map
        children_map: dict[int, list[int]] = defaultdict(list)
        node_gen: dict[int, int] = {}
        node_step: dict[int, int] = {}

        for e in events:
            parent_id = e["parent_stable_id"]
            child_id = e["child_stable_id"]
            children_map[parent_id].append(child_id)
            node_gen[child_id] = e["generation"]
            node_step[child_id] = e["step"]

        # Compute depths (max generation reached)
        if node_gen:
            max_gen = max(node_gen.values())
            all_depths.append(max_gen)

        # Compute breadth (number of children per parent)
        for _parent_id, children in children_map.items():
            all_breadths.append(len(children))

        # Collect events with seed index for visualization
        for e in events:
            all_events.append({
                "seed": seed_idx,  # 0-based run index within the results list
                "step": e["step"],
                "generation": e["generation"],
                "parent_stable_id": e["parent_stable_id"],
                "child_stable_id": e["child_stable_id"],
            })

    output = {
        "n_seeds": len(results),
        "seeds_with_lineage": sum(1 for r in results if r.get("lineage_events")),
        "total_events": len(all_events),
        "depth_stats": {},
        "breadth_stats": {},
        "events": all_events[:1000],  # Cap for file size
    }

    if all_depths:
        output["depth_stats"] = {
            "mean": float(np.mean(all_depths)),
            "std": float(np.std(all_depths, ddof=1)) if len(all_depths) > 1 else 0.0,
            "max": int(np.max(all_depths)),
            "min": int(np.min(all_depths)),
        }

    if all_breadths:
        output["breadth_stats"] = {
            "mean": float(np.mean(all_breadths)),
            "std": float(np.std(all_breadths, ddof=1)) if len(all_breadths) > 1 else 0.0,
            "max": int(np.max(all_breadths)),
        }

    return output


def main():
    """Run lineage analysis."""
    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found")
        return

    with open(DATA_PATH) as f:
        results = json.load(f)

    print(f"Analyzing lineage from {len(results)} seeds...")
    output = analyze_lineage(results)

    print(f"Seeds with lineage data: {output['seeds_with_lineage']}/{output['n_seeds']}")
    print(f"Total lineage events: {output['total_events']}")
    if output["depth_stats"]:
        ds = output["depth_stats"]
        print(f"Max generation depth: mean={ds['mean']:.1f}, max={ds['max']}")
    if output["breadth_stats"]:
        bs = output["breadth_stats"]
        print(f"Children per parent: mean={bs['mean']:.2f}, max={bs['max']}")

    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
