"""Phenotype clustering and niche analysis.

Analyzes evolution experiment data to identify emergent phenotypic clusters
and spatial niche associations among populations at the final timestep.

Usage:
    uv run python scripts/analyze_phenotype.py > experiments/phenotype_analysis.json

Output: JSON analysis to stdout + progress to stderr.
"""

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

try:
    from .experiment_common import log
except ImportError:
    from experiment_common import log


PERSISTENCE_CLAIM_THRESHOLD = 0.30


def persistence_claim_gate(ari: float, threshold: float = PERSISTENCE_CLAIM_THRESHOLD) -> bool:
    """Return True when ARI meets the threshold for stronger persistence claims."""
    return bool(ari >= threshold)


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


def extract_organism_traits(results: list[dict]) -> np.ndarray:
    """Extract per-seed population-level traits from final timestep samples.

    Returns array of shape (n_seeds, 5) with columns:
    [energy_mean, waste_mean, boundary_mean, genome_diversity, mean_generation]
    """
    traits = []
    for r in results:
        if "samples" not in r or not r["samples"]:
            continue
        final = r["samples"][-1]
        traits.append(
            [
                final.get("energy_mean", 0),
                final.get("waste_mean", 0),
                final.get("boundary_mean", 0),
                final.get("genome_diversity", 0),
                final.get("mean_generation", 0),
            ]
        )
    return np.array(traits) if traits else np.empty((0, 5))


def cluster_phenotypes(traits: np.ndarray, max_k: int = 5) -> dict:
    """Perform k-means clustering on trait vectors, selecting k by silhouette score."""
    if len(traits) < 4:
        return {"n_clusters": 0, "error": "insufficient data"}

    scaler = StandardScaler()
    scaled = scaler.fit_transform(traits)

    # Try k=2..max_k and pick best silhouette
    best_k = 2
    best_score = -1.0
    best_model = None
    for k in range(2, min(max_k + 1, len(traits))):
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        cur_labels = km.fit_predict(scaled)
        score = silhouette_score(scaled, cur_labels)
        if score > best_score:
            best_score = score
            best_k = k
            best_model = km

    labels = best_model.predict(scaled)

    # Compute per-cluster trait means
    cluster_profiles = []
    trait_names = [
        "energy_mean",
        "waste_mean",
        "boundary_mean",
        "genome_diversity",
        "mean_generation",
    ]
    for c in range(best_k):
        mask = labels == c
        profile = {
            "cluster_id": c,
            "count": int(mask.sum()),
        }
        for i, name in enumerate(trait_names):
            profile[name] = round(float(traits[mask, i].mean()), 4)
            profile[f"{name}_std"] = round(float(traits[mask, i].std()), 4)
        cluster_profiles.append(profile)

    return {
        "n_clusters": best_k,
        "silhouette_score": round(float(best_score), 4),
        "cluster_profiles": cluster_profiles,
        "labels": [int(label) for label in labels],
        "trait_names": trait_names,
        "traits": [[round(float(v), 4) for v in row] for row in traits],
    }


def _extract_traits_at_step(results: list[dict], target_step: int) -> np.ndarray:
    """Extract trait vectors from the sample closest to target_step."""
    trait_names = [
        "energy_mean",
        "waste_mean",
        "boundary_mean",
        "genome_diversity",
        "mean_generation",
    ]
    traits = []
    for r in results:
        if "samples" not in r or not r["samples"]:
            continue
        # Find sample closest to target_step
        best = min(r["samples"], key=lambda s: abs(s.get("step", 0) - target_step))
        traits.append([best.get(name, 0) for name in trait_names])
    return np.array(traits) if traits else np.empty((0, 5))


def _collect_organism_traits(
    results: list[dict], frame_idx: int, trait_names: list[str]
) -> dict[tuple[int, int], list[float]]:
    """Collect per-organism traits from a specific snapshot frame index."""
    orgs: dict[tuple[int, int], list[float]] = {}
    for r in results:
        seed = r.get("seed", 0)
        frames = r.get("organism_snapshots", [])
        if frame_idx >= len(frames):
            continue
        frame = frames[frame_idx]
        for org in frame.get("organisms", []):
            stable_id = org.get("stable_id")
            if stable_id is None:
                continue
            key = (seed, stable_id)
            orgs[key] = [float(org.get(name, 0.0)) for name in trait_names]
    return orgs


def _extract_shared_traits(
    dict_a: dict[tuple[int, int], list[float]],
    dict_b: dict[tuple[int, int], list[float]],
) -> tuple[list[tuple[int, int]], np.ndarray | None, np.ndarray | None]:
    """Find shared organisms between two snapshots and return their traits."""
    shared_keys = sorted(set(dict_a.keys()) & set(dict_b.keys()))
    if len(shared_keys) < 4:
        return shared_keys, None, None
    traits_a = np.array([dict_a[k] for k in shared_keys])
    traits_b = np.array([dict_b[k] for k in shared_keys])
    return shared_keys, traits_a, traits_b


def _compute_clustering_ari(
    traits_a: np.ndarray, traits_b: np.ndarray, k: int = 2
) -> tuple[float, np.ndarray, np.ndarray]:
    """Standardize and cluster two sets of traits, then compute ARI."""
    scaled_a = StandardScaler().fit_transform(traits_a)
    km_a = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels_a = km_a.fit_predict(scaled_a)

    scaled_b = StandardScaler().fit_transform(traits_b)
    km_b = KMeans(n_clusters=k, n_init=10, random_state=42)
    labels_b = km_b.fit_predict(scaled_b)

    ari = adjusted_rand_score(labels_a, labels_b)
    return float(ari), labels_a, labels_b


def _summarize_window(
    labels: np.ndarray,
    traits_raw: np.ndarray,
    n_total: int | None,
    k: int,
    trait_names: list[str],
    prefix: str = "",
    include_extra: bool = True,
) -> dict:
    """Summarize clustering for a time window."""
    profiles = []
    proportions = []
    for c in range(k):
        mask = labels == c
        count = int(mask.sum())
        proportions.append(round(count / len(labels), 4))
        profile = {"cluster_id": c, "count": count}
        for i, name in enumerate(trait_names):
            mean_val = float(traits_raw[mask, i].mean()) if count > 0 else 0.0
            profile[f"{prefix}{name}"] = round(mean_val, 4)
        profiles.append(profile)

    res = {
        "n_clusters": k,
        "cluster_proportions": proportions,
        "cluster_profiles": profiles,
    }

    if include_extra:
        if n_total is not None:
            res["n_total_organisms"] = n_total
        res["n_shared_organisms"] = len(labels)
        # Silhouette score only if we have enough samples
        if len(traits_raw) > k and len(np.unique(labels)) > 1:
            scaled = StandardScaler().fit_transform(traits_raw)
            sil = silhouette_score(scaled, labels)
        else:
            sil = 0.0
        res["silhouette_score"] = round(float(sil), 4)

    return res


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


def analyze_organism_level_persistence(exp_dir: Path) -> dict:
    """Analyze persistence of per-organism phenotype clusters across time windows.

    Uses per-organism snapshots from the niche experiment to test whether
    individual organisms differentiate into persistent ecological strategies.

    The snapshot schedule contains paired windows: (early_a, early_b) at the
    start and (late_a, late_b) near the end, spaced ~200 steps apart so that
    many organisms survive both snapshots within a pair.  We measure:
      1. Within-pair ARI (short gap) — do cluster assignments persist over
         ~200 steps?
      2. Cross-pair ARI (long gap) — do cluster assignments persist across
         thousands of steps (using organisms that survive both)?
    """
    path = exp_dir / "niche_normal.json"
    if not path.exists():
        return {"error": "niche_normal.json not found"}

    with open(path) as f:
        results = json.load(f)
    log(f"  Loaded {len(results)} seeds for organism-level persistence")

    trait_names = ["energy", "waste", "boundary_integrity", "maturity", "generation"]

    # Snapshot layout: [early_a, early_b, late_a, late_b]
    # Pair 1 (early): frames 0,1  —  Pair 2 (late): frames 2,3
    early_a = _collect_organism_traits(results, 0, trait_names)
    early_b = _collect_organism_traits(results, 1, trait_names)
    late_a = _collect_organism_traits(results, 2, trait_names)
    late_b = _collect_organism_traits(results, 3, trait_names)

    # Report frame steps
    frame_steps = []
    for r in results[:1]:
        for frame in r.get("organism_snapshots", []):
            frame_steps.append(frame["step"])
    log(f"  Snapshot steps: {frame_steps}")

    # Use early pair (a→b) for the main persistence analysis
    shared_keys, early_traits, late_traits = _extract_shared_traits(early_a, early_b)

    log(f"  Early organisms: {len(early_a)}, Late: {len(early_b)}, Shared: {len(shared_keys)}")

    if early_traits is None:
        return {
            "error": "insufficient shared organisms for temporal analysis",
            "n_early_a": len(early_a),
            "n_early_b": len(early_b),
            "n_late_a": len(late_a),
            "n_late_b": len(late_b),
            "n_shared": len(shared_keys),
        }

    ari, early_labels, late_labels = _compute_clustering_ari(early_traits, late_traits)

    early_summary = _summarize_window(
        early_labels, early_traits, len(early_a), 2, trait_names, prefix="mean_"
    )
    late_summary = _summarize_window(
        late_labels, late_traits, len(early_b), 2, trait_names, prefix="mean_"
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

    # Also export per-organism traits for figure generation
    return {
        "early_window": early_summary,
        "late_window": late_summary,
        "adjusted_rand_index": round(float(ari), 4),
        "claim_gate_threshold": PERSISTENCE_CLAIM_THRESHOLD,
        "claim_gate_passed": persistence_claim_gate(float(ari)),
        "late_pair_ari": late_pair_ari,
        "cross_pair_ari": cross_ari,
        "n_cross_pair_shared": len(cross_keys),
        "frame_steps": frame_steps,
        "interpretation": interp,
        "trait_names": trait_names,
        "early_traits": [[round(float(v), 4) for v in row] for row in early_traits],
        "late_traits": [[round(float(v), 4) for v in row] for row in late_traits],
        "early_labels": [int(label) for label in early_labels],
        "late_labels": [int(label) for label in late_labels],
    }


def main():
    """Analyze phenotype clustering from evolution experiment data."""
    exp_dir = Path(__file__).resolve().parent.parent / "experiments"

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

    output = {
        "analysis": "phenotype_clustering",
        "n_seeds": len(results),
        "n_trait_vectors": traits.shape[0],
        **analysis,
        "temporal_persistence": temporal,
        "organism_level_persistence": organism_persistence,
    }

    print(json.dumps(output, indent=2))
    log("Done.")


if __name__ == "__main__":
    main()
