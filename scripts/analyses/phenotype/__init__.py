"""Phenotype clustering and niche analysis package.

Analyzes evolution experiment data to identify emergent phenotypic clusters
and spatial niche associations among populations.

Entry point: ``main()`` for CLI use.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _project_root import PROJECT_ROOT

from .clustering import (
    PERSISTENCE_CLAIM_THRESHOLD,
    _compute_clustering_ari,
    _summarize_window,
    cluster_phenotypes,
    persistence_claim_gate,
)
from .trait_extraction import (
    _collect_organism_traits,
    _extract_shared_traits,
    _extract_traits_at_step,
    extract_organism_traits,
)

try:
    from experiment_common import log
except ImportError:

    def log(msg: str) -> None:  # type: ignore[misc]
        print(msg, file=sys.stderr)


def parse_args() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(
        description="Analyze phenotype clustering and temporal persistence."
    )
    parser.add_argument(
        "--exp-dir",
        type=Path,
        default=PROJECT_ROOT / "experiments",
        help="Experiments directory containing JSON inputs.",
    )
    parser.add_argument(
        "--niche-long-path",
        type=Path,
        default=None,
        help=(
            "Optional path to long-horizon niche JSON. "
            "Defaults to <exp-dir>/niche_normal_long.json if present."
        ),
    )
    return parser.parse_args()


def load_evolution_data(exp_dir: Path) -> list[dict]:
    """Load evolution experiment JSON files."""
    results = []
    for name in ["evolution_long_normal", "evolution_shift_normal"]:
        path = exp_dir / f"{name}.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            results.extend(data)
            log(f"  Loaded {len(data)} seeds from {path.name}")
    if not results:
        # Fall back to final_graph data
        path = exp_dir / "final_graph_normal.json"
        if path.exists():
            with open(path) as f:
                results = json.load(f)
            log(f"  Loaded {len(results)} seeds from {path.name}")
    return results


def analyze_temporal_persistence(exp_dir: Path) -> dict:
    """Analyze persistence of phenotypic clusters across early and late windows.

    Compares k-means clustering at an early window (~step 750) and late window
    (~step 1750) using adjusted Rand index to measure temporal stability.
    """
    path = exp_dir / "final_graph_normal.json"
    if not path.exists():
        return {"error": "final_graph_normal.json not found"}

    with open(path) as f:
        results = json.load(f)
    log(f"  Loaded {len(results)} seeds for temporal persistence analysis")

    trait_names = [
        "energy_mean",
        "waste_mean",
        "boundary_mean",
        "genome_diversity",
        "mean_generation",
    ]

    early_traits = _extract_traits_at_step(results, 750)
    late_traits = _extract_traits_at_step(results, 1750)

    if len(early_traits) < 4 or len(late_traits) < 4:
        return {"error": "insufficient data for temporal analysis"}

    ari, early_labels, late_labels = _compute_clustering_ari(early_traits, late_traits)

    early_summary = _summarize_window(
        early_labels, early_traits, None, 2, trait_names, include_extra=False
    )
    late_summary = _summarize_window(
        late_labels, late_traits, None, 2, trait_names, include_extra=False
    )

    if ari > 0.6:
        interp = (
            f"Strong temporal persistence (ARI={ari:.3f}): phenotypic "
            f"clusters remain stable from early to late windows."
        )
    elif ari > 0.3:
        interp = (
            f"Moderate temporal persistence (ARI={ari:.3f}): clusters "
            f"partially reorganize between early and late windows."
        )
    else:
        interp = (
            f"Weak temporal persistence (ARI={ari:.3f}): cluster "
            f"assignments change substantially between windows."
        )

    log(f"  Temporal persistence ARI={ari:.3f}")
    return {
        "early_clusters": early_summary,
        "late_clusters": late_summary,
        "adjusted_rand_index": round(float(ari), 4),
        "claim_gate_threshold": PERSISTENCE_CLAIM_THRESHOLD,
        "claim_gate_passed": persistence_claim_gate(float(ari)),
        "interpretation": interp,
    }


def analyze_organism_level_persistence(exp_dir: Path, niche_path: Path | None = None) -> dict:
    """Analyze persistence of per-organism phenotype clusters across time windows."""
    path = niche_path or exp_dir / "niche_normal.json"
    if not path.exists():
        return {"error": f"{path.name} not found"}

    with open(path) as f:
        results = json.load(f)
    log(f"  Loaded {len(results)} seeds for organism-level persistence")

    trait_names = ["energy", "waste", "boundary_integrity", "maturity", "generation"]

    frame_count = min((len(r.get("organism_snapshots", [])) for r in results), default=0)
    if frame_count < 4:
        return {"error": f"insufficient snapshots for persistence analysis: {frame_count}"}

    # Pair 1 (early): frames 0,1
    # Pair 2 (late): use final two frames so long-horizon runs compare truly late windows.
    early_pair = (0, 1)
    late_pair = (frame_count - 2, frame_count - 1)

    early_a = _collect_organism_traits(results, early_pair[0], trait_names)
    early_b = _collect_organism_traits(results, early_pair[1], trait_names)
    late_a = _collect_organism_traits(results, late_pair[0], trait_names)
    late_b = _collect_organism_traits(results, late_pair[1], trait_names)

    # Report frame steps
    frame_steps = []
    for r in results[:1]:
        for frame in r.get("organism_snapshots", []):
            frame_steps.append(frame["step"])
    log(f"  Snapshot steps: {frame_steps}")

    # Use early pair (a→b) for the main persistence analysis
    shared_keys, pair_traits_a, pair_traits_b = _extract_shared_traits(early_a, early_b)

    log(f"  Early A organisms: {len(early_a)}, Early B: {len(early_b)}, Shared: {len(shared_keys)}")

    if pair_traits_a is None:
        return {
            "error": "insufficient shared organisms for temporal analysis",
            "n_early_a": len(early_a),
            "n_early_b": len(early_b),
            "n_late_a": len(late_a),
            "n_late_b": len(late_b),
            "n_shared": len(shared_keys),
        }

    ari, early_labels, late_labels = _compute_clustering_ari(pair_traits_a, pair_traits_b)

    early_summary = _summarize_window(
        early_labels, pair_traits_a, len(early_a), 2, trait_names, prefix="mean_"
    )
    late_summary = _summarize_window(
        late_labels, pair_traits_b, len(early_b), 2, trait_names, prefix="mean_"
    )

    if ari > 0.6:
        interp = (
            f"Strong temporal persistence (ARI={ari:.3f}): individual organisms "
            f"maintain consistent ecological strategies from early to late windows."
        )
    elif ari > 0.3:
        interp = (
            f"Moderate temporal persistence (ARI={ari:.3f}): organisms show "
            f"partial consistency in ecological roles across time windows."
        )
    else:
        interp = (
            f"Weak temporal persistence (ARI={ari:.3f}): organism-level cluster "
            f"assignments change substantially between time windows, suggesting "
            f"ecological roles are dynamic rather than fixed."
        )

    log(f"  Organism-level ARI (early pair, ~200 steps)={ari:.3f}")

    # Also compute late pair ARI and cross-pair ARI
    _, lp_early, lp_late = _extract_shared_traits(late_a, late_b)
    late_pair_ari = None
    if lp_early is not None:
        late_pair_ari, _, _ = _compute_clustering_ari(lp_early, lp_late)
        late_pair_ari = round(float(late_pair_ari), 4)
        log(f"  Late pair ARI (~200 steps)={late_pair_ari}")

    cross_keys, cr_early, cr_late = _extract_shared_traits(early_a, late_b)
    cross_ari = None
    if cr_early is not None:
        cross_ari, _, _ = _compute_clustering_ari(cr_early, cr_late)
        cross_ari = round(float(cross_ari), 4)
        log(f"  Cross-pair ARI (~2500 steps)={cross_ari}, n_shared={len(cross_keys)}")
    else:
        log(f"  Cross-pair: only {len(cross_keys)} shared organisms (insufficient)")

    return {
        "early_window": early_summary,
        "late_window": late_summary,
        "early_pair_frames": list(early_pair),
        "late_pair_frames": list(late_pair),
        "adjusted_rand_index": round(float(ari), 4),
        "claim_gate_threshold": PERSISTENCE_CLAIM_THRESHOLD,
        "claim_gate_passed": persistence_claim_gate(float(ari)),
        "late_pair_ari": late_pair_ari,
        "cross_pair_ari": cross_ari,
        "n_cross_pair_shared": len(cross_keys),
        "frame_steps": frame_steps,
        "interpretation": interp,
        "trait_names": trait_names,
        "early_traits": [[round(float(v), 4) for v in row] for row in pair_traits_a],
        "late_traits": [[round(float(v), 4) for v in row] for row in pair_traits_b],
        "early_labels": [int(label) for label in early_labels],
        "late_labels": [int(label) for label in late_labels],
    }


def analyze_long_horizon_sensitivity(
    exp_dir: Path,
    niche_long_path: Path | None = None,
    standard_persistence: dict | None = None,
) -> dict:
    """Compare organism-level persistence between standard and long-horizon runs."""
    standard_path = exp_dir / "niche_normal.json"
    long_path = niche_long_path or exp_dir / "niche_normal_long.json"
    if not long_path.exists():
        return {
            "available": False,
            "reason": f"{long_path.name} not found",
        }

    standard = standard_persistence or analyze_organism_level_persistence(exp_dir, standard_path)
    if "error" in standard:
        return {
            "available": False,
            "reason": f"standard run unavailable: {standard['error']}",
        }

    long_run = analyze_organism_level_persistence(exp_dir, long_path)
    if "error" in long_run:
        return {
            "available": False,
            "reason": f"long-horizon run unavailable: {long_run['error']}",
        }

    metrics = [
        "adjusted_rand_index",
        "late_pair_ari",
        "cross_pair_ari",
        "n_cross_pair_shared",
    ]
    comparison: dict[str, dict[str, float | int | None]] = {}
    for metric in metrics:
        standard_value = standard.get(metric)
        long_value = long_run.get(metric)
        delta = None
        if isinstance(standard_value, (int, float)) and isinstance(long_value, (int, float)):
            delta = round(float(long_value) - float(standard_value), 4)
        comparison[metric] = {
            "standard": standard_value,
            "long_horizon": long_value,
            "delta_long_minus_standard": delta,
        }

    return {
        "available": True,
        "standard_path": str(standard_path),
        "long_horizon_path": str(long_path),
        "standard_claim_gate_passed": standard.get("claim_gate_passed"),
        "long_horizon_claim_gate_passed": long_run.get("claim_gate_passed"),
        "comparison": comparison,
        "standard_frame_steps": standard.get("frame_steps"),
        "long_horizon_frame_steps": long_run.get("frame_steps"),
    }


def main() -> None:
    """Analyze phenotype clustering from evolution experiment data."""
    args = parse_args()
    exp_dir = args.exp_dir

    log("Phenotype clustering analysis")
    log("Loading evolution experiment data...")
    results = load_evolution_data(exp_dir)
    if not results:
        log("ERROR: no evolution data found in experiments/")
        sys.exit(1)
    log(f"  Total seeds: {len(results)}")

    log("Extracting organism traits...")
    traits = extract_organism_traits(results)
    log(f"  Trait matrix: {traits.shape}")

    if traits.shape[0] < 4:
        log("ERROR: insufficient data for clustering")
        sys.exit(1)

    log("Clustering phenotypes...")
    analysis = cluster_phenotypes(traits)
    log(f"  Best k={analysis['n_clusters']}, silhouette={analysis.get('silhouette_score', 'N/A')}")

    for cp in analysis.get("cluster_profiles", []):
        log(
            f"  Cluster {cp['cluster_id']}: n={cp['count']}, "
            f"energy={cp['energy_mean']:.3f}, "
            f"boundary={cp['boundary_mean']:.3f}"
        )

    log("Analyzing temporal persistence (seed-level)...")
    temporal = analyze_temporal_persistence(exp_dir)

    log("Analyzing organism-level persistence...")
    organism_persistence = analyze_organism_level_persistence(exp_dir)
    log("Analyzing long-horizon niche sensitivity...")
    long_horizon_sensitivity = analyze_long_horizon_sensitivity(
        exp_dir,
        args.niche_long_path,
        organism_persistence,
    )

    output = {
        "analysis": "phenotype_clustering",
        "n_seeds": len(results),
        "n_trait_vectors": traits.shape[0],
        **analysis,
        "temporal_persistence": temporal,
        "organism_level_persistence": organism_persistence,
        "long_horizon_sensitivity": long_horizon_sensitivity,
    }

    print(json.dumps(output, indent=2))
    log("Done.")
