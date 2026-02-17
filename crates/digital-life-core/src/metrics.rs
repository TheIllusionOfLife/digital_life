use crate::agent::Agent;
use crate::organism::OrganismRuntime;
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha12Rng;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize, Default)]
#[serde(default)]
pub struct StepMetrics {
    pub step: usize,
    pub energy_mean: f32,
    pub waste_mean: f32,
    pub boundary_mean: f32,
    pub alive_count: usize,
    pub resource_total: f64,
    pub birth_count: usize,
    pub death_count: usize,
    pub population_size: usize,
    pub mean_generation: f32,
    pub mean_genome_drift: f32,
    pub agent_id_exhaustion_events: usize,
    // Extended metrics for peer review response
    pub energy_std: f32,
    pub waste_std: f32,
    pub boundary_std: f32,
    pub mean_age: f32,
    pub internal_state_mean: [f32; 4],
    pub internal_state_std: [f32; 4],
    pub genome_diversity: f32,
    pub max_generation: usize,
    pub maturity_mean: f32,
    pub spatial_cohesion_mean: f32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LineageEvent {
    pub step: usize,
    pub parent_stable_id: u64,
    pub child_stable_id: u64,
    pub generation: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OrganismSnapshot {
    pub stable_id: u64,
    pub generation: u32,
    pub age_steps: usize,
    pub energy: f32,
    pub waste: f32,
    pub boundary_integrity: f32,
    pub maturity: f32,
    pub center_x: f64,
    pub center_y: f64,
    pub n_agents: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SnapshotFrame {
    pub step: usize,
    pub organisms: Vec<OrganismSnapshot>,
}

fn default_schema_version() -> u32 {
    1
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RunSummary {
    #[serde(default = "default_schema_version")]
    pub schema_version: u32,
    pub steps: usize,
    pub sample_every: usize,
    pub final_alive_count: usize,
    pub samples: Vec<StepMetrics>,
    #[serde(default)]
    pub lifespans: Vec<usize>,
    #[serde(default)]
    pub total_reproduction_events: usize,
    #[serde(default)]
    pub lineage_events: Vec<LineageEvent>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub organism_snapshots: Vec<SnapshotFrame>,
}

#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct PopulationStats {
    pub population_size: usize,
    pub alive_count: usize,
    pub total_births: usize,
    pub total_deaths: usize,
    pub mean_generation: f32,
}

fn l2_distance(a: &[f32], b: &[f32]) -> f32 {
    a.iter()
        .zip(b.iter())
        .map(|(x, y)| (x - y).powi(2))
        .sum::<f32>()
        .sqrt()
}

fn genome_drift(org: &OrganismRuntime) -> f32 {
    let current = org.genome.nn_weights();
    let ancestor = org.ancestor_genome.nn_weights();
    let len = current.len().min(ancestor.len());
    if len == 0 {
        return 0.0;
    }
    let sum_abs = current
        .iter()
        .zip(ancestor.iter())
        .map(|(a, b)| (a - b).abs())
        .sum::<f32>();
    sum_abs / len as f32
}

fn compute_genome_diversity(organisms: &[OrganismRuntime], step_index: usize) -> f32 {
    let alive_genomes: Vec<&[f32]> = organisms
        .iter()
        .filter(|o| o.alive)
        .map(|o| o.genome.data())
        .collect();
    let n = alive_genomes.len();
    if n < 2 {
        return 0.0;
    }

    // Sample up to 50 random pairs to avoid O(n^2) cost
    let max_pairs = 50usize;
    let total_pairs = n * (n - 1) / 2;

    if total_pairs <= max_pairs {
        // Enumerate all pairs
        let mut sum = 0.0f32;
        for i in 0..n {
            for j in (i + 1)..n {
                sum += l2_distance(alive_genomes[i], alive_genomes[j]);
            }
        }
        sum / total_pairs as f32
    } else {
        // Use deterministic sampling based on step_index for reproducibility
        let mut sample_rng = ChaCha12Rng::seed_from_u64(step_index as u64);
        let mut sum = 0.0f32;
        for _ in 0..max_pairs {
            let i = sample_rng.random_range(0..n);
            let mut j = sample_rng.random_range(0..n - 1);
            if j >= i {
                j += 1;
            }
            sum += l2_distance(alive_genomes[i], alive_genomes[j]);
        }
        sum / max_pairs as f32
    }
}

/// Compute mean pairwise agent distance per alive organism (toroidal-aware).
/// Lower values indicate tighter spatial cohesion.
fn compute_spatial_cohesion(
    agents: &[Agent],
    organisms: &[OrganismRuntime],
    world_size: f64,
) -> f32 {
    let half = world_size * 0.5;
    let mut org_cohesions = Vec::new();

    for org in organisms.iter().filter(|o| o.alive) {
        let positions: Vec<[f64; 2]> = agents
            .iter()
            .filter(|a| a.organism_id == org.id)
            .map(|a| a.position)
            .collect();
        let n = positions.len();
        if n < 2 {
            continue;
        }
        let mut dist_sum = 0.0f64;
        let pairs = n * (n - 1) / 2;
        for i in 0..n {
            for j in (i + 1)..n {
                let mut dx = (positions[i][0] - positions[j][0]).abs();
                if dx > half {
                    dx = world_size - dx;
                }
                let mut dy = (positions[i][1] - positions[j][1]).abs();
                if dy > half {
                    dy = world_size - dy;
                }
                dist_sum += (dx * dx + dy * dy).sqrt();
            }
        }
        org_cohesions.push((dist_sum / pairs as f64) as f32);
    }

    if org_cohesions.is_empty() {
        0.0
    } else {
        org_cohesions.iter().sum::<f32>() / org_cohesions.len() as f32
    }
}

#[allow(clippy::too_many_arguments)]
pub fn collect_step_metrics(
    step: usize,
    step_index: usize,
    world_size: f64,
    resource_total: f64,
    birth_count: usize,
    death_count: usize,
    exhaustion_events: usize,
    organisms: &[OrganismRuntime],
    agents: &[Agent],
) -> StepMetrics {
    let alive = organisms.iter().filter(|o| o.alive).count();
    let denom = alive.max(1) as f32;

    let mut energy_sum = 0.0f32;
    let mut waste_sum = 0.0f32;
    let mut boundary_sum = 0.0f32;
    let mut generation_sum = 0.0f32;
    let mut drift_sum = 0.0f32;
    let mut age_sum = 0.0f32;
    let mut maturity_sum = 0.0f32;
    let mut max_gen: usize = 0;

    // Collect values for SD computation
    let mut energies = Vec::with_capacity(alive);
    let mut wastes = Vec::with_capacity(alive);
    let mut boundaries = Vec::with_capacity(alive);

    for org in organisms.iter().filter(|o| o.alive) {
        energy_sum += org.metabolic_state.energy;
        waste_sum += org.metabolic_state.waste;
        boundary_sum += org.boundary_integrity;
        generation_sum += org.generation as f32;
        drift_sum += genome_drift(org);
        age_sum += org.age_steps as f32;
        maturity_sum += org.maturity;
        max_gen = max_gen.max(org.generation as usize);

        energies.push(org.metabolic_state.energy);
        wastes.push(org.metabolic_state.waste);
        boundaries.push(org.boundary_integrity);
    }

    let energy_mean = energy_sum / denom;
    let waste_mean = waste_sum / denom;
    let boundary_mean = boundary_sum / denom;

    let std_dev = |vals: &[f32], mean: f32| -> f32 {
        if vals.len() < 2 {
            return 0.0;
        }
        let var =
            vals.iter().map(|v| (v - mean).powi(2)).sum::<f32>() / (vals.len() - 1) as f32;
        var.sqrt()
    };

    // Internal state: mean and SD across all alive agents.
    // Calculate mean and variance in two passes to avoid allocation.
    let is_alive = |a: &&Agent| {
        organisms
            .get(a.organism_id as usize)
            .map(|o| o.alive)
            .unwrap_or(false)
    };

    let mut is_count = 0usize;
    let mut is_sums = [0.0f32; 4];

    // Pass 1: Sums and count
    for agent in agents.iter().filter(is_alive) {
        is_count += 1;
        for (s, &v) in is_sums.iter_mut().zip(&agent.internal_state) {
            *s += v;
        }
    }

    let is_denom = is_count.max(1) as f32;
    let internal_state_mean = [
        is_sums[0] / is_denom,
        is_sums[1] / is_denom,
        is_sums[2] / is_denom,
        is_sums[3] / is_denom,
    ];

    let mut is_var = [0.0f32; 4];
    // Pass 2: Variance
    if is_count >= 2 {
        for agent in agents.iter().filter(is_alive) {
            for ((v, &s), &m) in is_var
                .iter_mut()
                .zip(&agent.internal_state)
                .zip(&internal_state_mean)
            {
                *v += (s - m).powi(2);
            }
        }
        for v in &mut is_var {
            *v = (*v / (is_count - 1) as f32).sqrt();
        }
    }

    // Genome diversity: mean L2 distance between sampled pairs of alive organism genomes
    let genome_diversity = compute_genome_diversity(organisms, step_index);

    // Spatial cohesion: mean pairwise agent distance per organism (toroidal-aware)
    let spatial_cohesion_mean = compute_spatial_cohesion(agents, organisms, world_size);

    StepMetrics {
        step,
        energy_mean,
        waste_mean,
        boundary_mean,
        alive_count: alive,
        resource_total,
        birth_count,
        death_count,
        population_size: organisms.len(),
        mean_generation: generation_sum / denom,
        mean_genome_drift: drift_sum / denom,
        agent_id_exhaustion_events: exhaustion_events,
        energy_std: std_dev(&energies, energy_mean),
        waste_std: std_dev(&wastes, waste_mean),
        boundary_std: std_dev(&boundaries, boundary_mean),
        mean_age: age_sum / denom,
        internal_state_mean,
        internal_state_std: is_var,
        genome_diversity,
        max_generation: max_gen,
        maturity_mean: maturity_sum / denom,
        spatial_cohesion_mean,
    }
}
