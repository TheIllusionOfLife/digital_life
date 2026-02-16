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

from experiment_common import log


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

    # Standardize and cluster each window independently
    k = 2
    early_scaled = StandardScaler().fit_transform(early_traits)
    late_scaled = StandardScaler().fit_transform(late_traits)

    early_km = KMeans(n_clusters=k, n_init=10, random_state=42)
    late_km = KMeans(n_clusters=k, n_init=10, random_state=42)

    early_labels = early_km.fit_predict(early_scaled)
    late_labels = late_km.fit_predict(late_scaled)

    # Compute adjusted Rand index
    ari = adjusted_rand_score(early_labels, late_labels)

    def _cluster_summary(labels, traits_raw):
        profiles = []
        proportions = []
        for c in range(k):
            mask = labels == c
            count = int(mask.sum())
            proportions.append(round(count / len(labels), 4))
            profile = {"cluster_id": c, "count": count}
            for i, name in enumerate(trait_names):
                profile[name] = round(float(traits_raw[mask, i].mean()), 4)
            profiles.append(profile)
        return {
            "n_clusters": k,
            "cluster_proportions": proportions,
            "cluster_profiles": profiles,
        }

    early_summary = _cluster_summary(early_labels, early_traits)
    late_summary = _cluster_summary(late_labels, late_traits)

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
        "interpretation": interp,
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
    log(
        f"  Best k={analysis['n_clusters']}, "
        f"silhouette={analysis.get('silhouette_score', 'N/A')}"
    )

    for cp in analysis.get("cluster_profiles", []):
        log(
            f"  Cluster {cp['cluster_id']}: n={cp['count']}, "
            f"energy={cp['energy_mean']:.3f}, "
            f"boundary={cp['boundary_mean']:.3f}"
        )

    log("Analyzing temporal persistence...")
    temporal = analyze_temporal_persistence(exp_dir)

    output = {
        "analysis": "phenotype_clustering",
        "n_seeds": len(results),
        "n_trait_vectors": traits.shape[0],
        **analysis,
        "temporal_persistence": temporal,
    }

    print(json.dumps(output, indent=2))
    log("Done.")


if __name__ == "__main__":
    main()
