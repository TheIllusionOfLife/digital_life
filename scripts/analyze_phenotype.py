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

    def _collect_orgs(results: list[dict], frame_idx: int
                      ) -> dict[tuple[int, int], list[float]]:
        """Collect per-organism traits from a specific snapshot frame index."""
        orgs: dict[tuple[int, int], list[float]] = {}
        for r in results:
            seed = r.get("seed", 0)
            frames = r.get("organism_snapshots", [])
            if frame_idx >= len(frames):
                continue
            for org in frames[frame_idx]["organisms"]:
                key = (seed, org["stable_id"])
                orgs[key] = [
                    org["energy"],
                    org["waste"],
                    org["boundary_integrity"],
                    org["maturity"],
                    float(org["generation"]),
                ]
        return orgs

    # Snapshot layout: [early_a, early_b, late_a, late_b]
    # Pair 1 (early): frames 0,1  —  Pair 2 (late): frames 2,3
    early_a = _collect_orgs(results, 0)
    early_b = _collect_orgs(results, 1)
    late_a = _collect_orgs(results, 2)
    late_b = _collect_orgs(results, 3)

    # Report frame steps
    frame_steps = []
    for r in results[:1]:
        for frame in r.get("organism_snapshots", []):
            frame_steps.append(frame["step"])
    log(f"  Snapshot steps: {frame_steps}")

    # Use early pair (a→b) for the main persistence analysis
    early_orgs = early_a
    late_orgs = early_b

    # Find organisms present in both windows
    shared_keys = sorted(set(early_orgs.keys()) & set(late_orgs.keys()))
    log(f"  Early organisms: {len(early_orgs)}, Late: {len(late_orgs)}, "
        f"Shared: {len(shared_keys)}")

    if len(shared_keys) < 4:
        return {
            "error": "insufficient shared organisms for temporal analysis",
            "n_early": len(early_orgs),
            "n_late": len(late_orgs),
            "n_shared": len(shared_keys),
        }

    early_traits = np.array([early_orgs[k] for k in shared_keys])
    late_traits = np.array([late_orgs[k] for k in shared_keys])

    k = 2
    scaler = StandardScaler()

    early_scaled = scaler.fit_transform(early_traits)
    early_km = KMeans(n_clusters=k, n_init=10, random_state=42)
    early_labels = early_km.fit_predict(early_scaled)

    late_scaler = StandardScaler()
    late_scaled = late_scaler.fit_transform(late_traits)
    late_km = KMeans(n_clusters=k, n_init=10, random_state=42)
    late_labels = late_km.fit_predict(late_scaled)

    ari = adjusted_rand_score(early_labels, late_labels)

    def _window_summary(labels, traits_raw, all_orgs_dict):
        """Summarize clustering for a time window."""
        n_total = len(all_orgs_dict)
        profiles = []
        proportions = []
        sil = silhouette_score(
            StandardScaler().fit_transform(traits_raw), labels
        ) if len(traits_raw) > k else 0.0
        for c in range(k):
            mask = labels == c
            count = int(mask.sum())
            proportions.append(round(count / len(labels), 4))
            profile = {"cluster_id": c, "count": count}
            for i, name in enumerate(trait_names):
                profile[f"mean_{name}"] = round(float(traits_raw[mask, i].mean()), 4)
            profiles.append(profile)
        return {
            "n_total_organisms": n_total,
            "n_shared_organisms": len(labels),
            "n_clusters": k,
            "silhouette_score": round(float(sil), 4),
            "cluster_proportions": proportions,
            "cluster_profiles": profiles,
        }

    early_summary = _window_summary(early_labels, early_traits, early_orgs)
    late_summary = _window_summary(late_labels, late_traits, late_orgs)

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
    late_pair_shared = sorted(set(late_a.keys()) & set(late_b.keys()))
    late_pair_ari = None
    if len(late_pair_shared) >= 4:
        lp_early = np.array([late_a[k] for k in late_pair_shared])
        lp_late = np.array([late_b[k] for k in late_pair_shared])
        lp_e_labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(
            StandardScaler().fit_transform(lp_early))
        lp_l_labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(
            StandardScaler().fit_transform(lp_late))
        late_pair_ari = round(float(adjusted_rand_score(lp_e_labels, lp_l_labels)), 4)
        log(f"  Late pair ARI (~200 steps)={late_pair_ari}")

    cross_shared = sorted(set(early_a.keys()) & set(late_b.keys()))
    cross_ari = None
    if len(cross_shared) >= 4:
        cr_early = np.array([early_a[k] for k in cross_shared])
        cr_late = np.array([late_b[k] for k in cross_shared])
        cr_e_labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(
            StandardScaler().fit_transform(cr_early))
        cr_l_labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(
            StandardScaler().fit_transform(cr_late))
        cross_ari = round(float(adjusted_rand_score(cr_e_labels, cr_l_labels)), 4)
        log(f"  Cross-pair ARI (~2500 steps)={cross_ari}, n_shared={len(cross_shared)}")
    else:
        log(f"  Cross-pair: only {len(cross_shared)} shared organisms (insufficient)")

    # Also export per-organism traits for figure generation
    return {
        "early_window": early_summary,
        "late_window": late_summary,
        "adjusted_rand_index": round(float(ari), 4),
        "late_pair_ari": late_pair_ari,
        "cross_pair_ari": cross_ari,
        "n_cross_pair_shared": len(cross_shared),
        "frame_steps": frame_steps,
        "interpretation": interp,
        "trait_names": trait_names,
        "early_traits": [[round(float(v), 4) for v in row] for row in early_traits],
        "late_traits": [[round(float(v), 4) for v in row] for row in late_traits],
        "early_labels": [int(l) for l in early_labels],
        "late_labels": [int(l) for l in late_labels],
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
