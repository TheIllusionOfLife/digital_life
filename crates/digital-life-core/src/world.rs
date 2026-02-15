use crate::agent::Agent;
use crate::config::{MetabolismMode, SimConfig};
use crate::genome::{Genome, MutationRates};
use crate::metabolism::{MetabolicState, MetabolismEngine};
use crate::nn::NeuralNet;
use crate::organism::{DevelopmentalProgram, OrganismRuntime};
use crate::resource::ResourceField;
use crate::spatial;
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha12Rng;
use serde::{Deserialize, Serialize};
use std::f64::consts::PI;
use std::time::Instant;
use std::{error::Error, fmt};

fn l2_distance(a: &[f32], b: &[f32]) -> f32 {
    a.iter()
        .zip(b.iter())
        .map(|(x, y)| (x - y).powi(2))
        .sum::<f32>()
        .sqrt()
}

/// Decode a genome's metabolic segment into a per-organism `MetabolismEngine`.
///
/// Returns `Some(engine)` in Graph mode, `None` in Toy/Counter mode (uses shared engine).
fn decode_organism_metabolism(genome: &Genome, mode: MetabolismMode) -> Option<MetabolismEngine> {
    match mode {
        MetabolismMode::Graph => {
            let gm = crate::metabolism::decode_graph_metabolism(genome.segment_data(1));
            Some(MetabolismEngine::Graph(gm))
        }
        MetabolismMode::Toy | MetabolismMode::Counter => None,
    }
}

#[derive(Clone, Debug)]
pub struct StepTimings {
    pub spatial_build_us: u64,
    pub nn_query_us: u64,
    pub state_update_us: u64,
    pub total_us: u64,
}

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
pub struct RunSummary {
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
}

#[derive(Clone, Debug, Serialize, Deserialize, Default)]
pub struct PopulationStats {
    pub population_size: usize,
    pub alive_count: usize,
    pub total_births: usize,
    pub total_deaths: usize,
    pub mean_generation: f32,
}

pub struct World {
    pub agents: Vec<Agent>,
    organisms: Vec<OrganismRuntime>,
    config: SimConfig,
    metabolism: MetabolismEngine,
    resource_field: ResourceField,
    org_toroidal_sums: Vec<[f64; 4]>,
    org_counts: Vec<usize>,
    rng: ChaCha12Rng,
    next_agent_id: u32,
    step_index: usize,
    births_last_step: usize,
    deaths_last_step: usize,
    total_births: usize,
    total_deaths: usize,
    mutation_rates: MutationRates,
    next_organism_stable_id: u64,
    agent_id_exhaustions_last_step: usize,
    total_agent_id_exhaustions: usize,
    lifespans: Vec<usize>,
    lineage_events: Vec<LineageEvent>,
    /// Runtime resource regeneration rate, separate from config to avoid mutating
    /// config at runtime during environment shifts.
    current_resource_rate: f32,
}

#[derive(Debug, Clone, PartialEq)]
pub enum WorldInitError {
    InvalidWorldSize,
    InvalidDt,
    InvalidMaxSpeed,
    InvalidSensingRadius,
    InvalidNeighborNorm,
    InvalidMetabolicViabilityFloor,
    InvalidBoundaryDecayBaseRate,
    InvalidBoundaryDecayEnergyScale,
    InvalidBoundaryWastePressureScale,
    InvalidBoundaryRepairWastePenaltyScale,
    InvalidBoundaryRepairRate,
    InvalidBoundaryCollapseThreshold,
    InvalidDeathEnergyThreshold,
    InvalidDeathBoundaryThreshold,
    InvalidReproductionMinEnergy,
    InvalidReproductionMinBoundary,
    InvalidReproductionEnergyCost,
    InvalidReproductionEnergyBalance,
    InvalidReproductionChildMinAgents,
    InvalidReproductionSpawnRadius,
    InvalidCrowdingNeighborThreshold,
    InvalidCrowdingBoundaryDecay,
    InvalidMaxOrganismAgeSteps,
    InvalidCompactionIntervalSteps,
    InvalidMutationPointRate,
    InvalidMutationPointScale,
    InvalidMutationResetRate,
    InvalidMutationScaleRate,
    InvalidMutationScaleBounds,
    InvalidMutationValueLimit,
    InvalidMutationProbabilityBudget,
    InvalidHomeostasisDecayRate,
    InvalidGrowthMaturationSteps,
    InvalidGrowthImmatureMetabolicEfficiency,
    InvalidResourceRegenerationRate,
    InvalidEnvironmentShiftResourceRate,
    InvalidMetabolismEfficiencyMultiplier,
    InvalidEnvironmentCycleLowRate,
    ConflictingEnvironmentFeatures,
    WorldSizeTooLarge { max: f64, actual: f64 },
    AgentCountOverflow,
    TooManyAgents { max: usize, actual: usize },
    NumOrganismsMismatch { expected: usize, actual: usize },
    AgentCountMismatch { expected: usize, actual: usize },
    InvalidOrganismId,
}

impl fmt::Display for WorldInitError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            WorldInitError::InvalidWorldSize => write!(f, "world_size must be positive and finite"),
            WorldInitError::InvalidDt => write!(f, "dt must be positive and finite"),
            WorldInitError::InvalidMaxSpeed => write!(f, "max_speed must be positive and finite"),
            WorldInitError::InvalidSensingRadius => {
                write!(f, "sensing_radius must be non-negative and finite")
            }
            WorldInitError::InvalidNeighborNorm => {
                write!(f, "neighbor_norm must be positive and finite")
            }
            WorldInitError::InvalidMetabolicViabilityFloor => {
                write!(f, "metabolic_viability_floor must be finite and non-negative")
            }
            WorldInitError::InvalidBoundaryDecayBaseRate => {
                write!(f, "boundary_decay_base_rate must be finite and non-negative")
            }
            WorldInitError::InvalidBoundaryDecayEnergyScale => {
                write!(f, "boundary_decay_energy_scale must be finite and non-negative")
            }
            WorldInitError::InvalidBoundaryWastePressureScale => {
                write!(f, "boundary_waste_pressure_scale must be finite and non-negative")
            }
            WorldInitError::InvalidBoundaryRepairWastePenaltyScale => {
                write!(
                    f,
                    "boundary_repair_waste_penalty_scale must be finite and non-negative"
                )
            }
            WorldInitError::InvalidBoundaryRepairRate => {
                write!(f, "boundary_repair_rate must be finite and non-negative")
            }
            WorldInitError::InvalidBoundaryCollapseThreshold => {
                write!(f, "boundary_collapse_threshold must be finite and within [0,1]")
            }
            WorldInitError::InvalidDeathEnergyThreshold => {
                write!(f, "death_energy_threshold must be finite and non-negative")
            }
            WorldInitError::InvalidDeathBoundaryThreshold => {
                write!(f, "death_boundary_threshold must be finite and within [0,1]")
            }
            WorldInitError::InvalidReproductionMinEnergy => {
                write!(f, "reproduction_min_energy must be finite and non-negative")
            }
            WorldInitError::InvalidReproductionMinBoundary => {
                write!(f, "reproduction_min_boundary must be finite and within [0,1]")
            }
            WorldInitError::InvalidReproductionEnergyCost => {
                write!(f, "reproduction_energy_cost must be finite and positive")
            }
            WorldInitError::InvalidReproductionEnergyBalance => {
                write!(
                    f,
                    "reproduction_min_energy must be greater than or equal to reproduction_energy_cost"
                )
            }
            WorldInitError::InvalidReproductionChildMinAgents => {
                write!(f, "reproduction_child_min_agents must be positive")
            }
            WorldInitError::InvalidReproductionSpawnRadius => {
                write!(f, "reproduction_spawn_radius must be finite and non-negative")
            }
            WorldInitError::InvalidCrowdingNeighborThreshold => {
                write!(f, "crowding_neighbor_threshold must be finite and non-negative")
            }
            WorldInitError::InvalidCrowdingBoundaryDecay => {
                write!(f, "crowding_boundary_decay must be finite and non-negative")
            }
            WorldInitError::InvalidMaxOrganismAgeSteps => {
                write!(f, "max_organism_age_steps must be positive")
            }
            WorldInitError::InvalidCompactionIntervalSteps => {
                write!(f, "compaction_interval_steps must be positive")
            }
            WorldInitError::InvalidMutationPointRate => {
                write!(f, "mutation_point_rate must be finite and within [0,1]")
            }
            WorldInitError::InvalidMutationPointScale => {
                write!(f, "mutation_point_scale must be finite and non-negative")
            }
            WorldInitError::InvalidMutationResetRate => {
                write!(f, "mutation_reset_rate must be finite and within [0,1]")
            }
            WorldInitError::InvalidMutationScaleRate => {
                write!(f, "mutation_scale_rate must be finite and within [0,1]")
            }
            WorldInitError::InvalidMutationScaleBounds => {
                write!(
                    f,
                    "mutation_scale_min/mutation_scale_max must be finite, positive, and ordered"
                )
            }
            WorldInitError::InvalidMutationValueLimit => {
                write!(f, "mutation_value_limit must be finite and positive")
            }
            WorldInitError::InvalidMutationProbabilityBudget => {
                write!(
                    f,
                    "mutation_point_rate + mutation_reset_rate + mutation_scale_rate must be <= 1.0"
                )
            }
            WorldInitError::InvalidHomeostasisDecayRate => {
                write!(f, "homeostasis_decay_rate must be finite and non-negative")
            }
            WorldInitError::InvalidGrowthMaturationSteps => {
                write!(f, "growth_maturation_steps must be positive")
            }
            WorldInitError::InvalidGrowthImmatureMetabolicEfficiency => {
                write!(
                    f,
                    "growth_immature_metabolic_efficiency must be finite and within [0,1]"
                )
            }
            WorldInitError::InvalidResourceRegenerationRate => {
                write!(f, "resource_regeneration_rate must be finite and non-negative")
            }
            WorldInitError::InvalidEnvironmentShiftResourceRate => {
                write!(
                    f,
                    "environment_shift_resource_rate must be finite and non-negative"
                )
            }
            WorldInitError::InvalidMetabolismEfficiencyMultiplier => {
                write!(
                    f,
                    "metabolism_efficiency_multiplier must be finite and within [0,1]"
                )
            }
            WorldInitError::ConflictingEnvironmentFeatures => {
                write!(
                    f,
                    "environment_shift_step and environment_cycle_period are mutually exclusive"
                )
            }
            WorldInitError::InvalidEnvironmentCycleLowRate => {
                write!(
                    f,
                    "environment_cycle_low_rate must be finite and non-negative"
                )
            }
            WorldInitError::WorldSizeTooLarge { max, actual } => {
                write!(f, "world_size ({actual}) exceeds supported maximum ({max})")
            }
            WorldInitError::AgentCountOverflow => {
                write!(f, "num_organisms * agents_per_organism overflows usize")
            }
            WorldInitError::TooManyAgents { max, actual } => {
                write!(f, "total agents ({actual}) exceeds supported maximum ({max})")
            }
            WorldInitError::NumOrganismsMismatch { expected, actual } => write!(
                f,
                "num_organisms ({expected}) must match nns.len() ({actual})"
            ),
            WorldInitError::AgentCountMismatch { expected, actual } => write!(
                f,
                "agents.len() ({actual}) must match num_organisms * agents_per_organism ({expected})"
            ),
            WorldInitError::InvalidOrganismId => {
                write!(f, "all agent organism_ids must be valid indices into nns")
            }
        }
    }
}

impl Error for WorldInitError {}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ExperimentError {
    InvalidSampleEvery,
    TooManySteps { max: usize, actual: usize },
    TooManySamples { max: usize, actual: usize },
}

impl fmt::Display for ExperimentError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ExperimentError::InvalidSampleEvery => write!(f, "sample_every must be positive"),
            ExperimentError::TooManySteps { max, actual } => {
                write!(f, "steps ({actual}) exceed supported maximum ({max})")
            }
            ExperimentError::TooManySamples { max, actual } => {
                write!(
                    f,
                    "sample count ({actual}) exceeds supported maximum ({max})"
                )
            }
        }
    }
}

impl Error for ExperimentError {}

impl World {
    pub const MAX_WORLD_SIZE: f64 = 2048.0;
    pub const MAX_TOTAL_AGENTS: usize = 250_000;
    pub const MAX_EXPERIMENT_STEPS: usize = 1_000_000;
    pub const MAX_EXPERIMENT_SAMPLES: usize = 50_000;

    pub fn new(agents: Vec<Agent>, nns: Vec<NeuralNet>, config: SimConfig) -> Self {
        Self::try_new(agents, nns, config).unwrap_or_else(|e| panic!("{e}"))
    }

    pub fn try_new(
        agents: Vec<Agent>,
        nns: Vec<NeuralNet>,
        config: SimConfig,
    ) -> Result<Self, WorldInitError> {
        Self::validate_config_common(&config)?;
        if config.num_organisms != nns.len() {
            return Err(WorldInitError::NumOrganismsMismatch {
                expected: config.num_organisms,
                actual: nns.len(),
            });
        }
        let expected_agent_count = config
            .num_organisms
            .checked_mul(config.agents_per_organism)
            .ok_or(WorldInitError::AgentCountOverflow)?;
        if expected_agent_count > Self::MAX_TOTAL_AGENTS {
            return Err(WorldInitError::TooManyAgents {
                max: Self::MAX_TOTAL_AGENTS,
                actual: expected_agent_count,
            });
        }
        if agents.len() != expected_agent_count {
            return Err(WorldInitError::AgentCountMismatch {
                expected: expected_agent_count,
                actual: agents.len(),
            });
        }
        if !agents.iter().all(|a| (a.organism_id as usize) < nns.len()) {
            return Err(WorldInitError::InvalidOrganismId);
        }

        let mut organisms: Vec<OrganismRuntime> = nns
            .into_iter()
            .enumerate()
            .map(|(id, nn)| {
                let genome = Genome::with_nn_weights(nn.to_weight_vec());
                let developmental_program = DevelopmentalProgram::decode(genome.segment_data(3));
                OrganismRuntime {
                    id: id as u16,
                    stable_id: id as u64,
                    generation: 0,
                    age_steps: 0,
                    alive: true,
                    boundary_integrity: 1.0,
                    metabolic_state: MetabolicState::default(),
                    genome: genome.clone(),
                    ancestor_genome: genome,
                    nn,
                    agent_ids: Vec::new(),
                    maturity: 1.0,
                    metabolism_engine: None,
                    developmental_program,
                    parent_stable_id: None,
                }
            })
            .collect();

        for agent in &agents {
            organisms[agent.organism_id as usize]
                .agent_ids
                .push(agent.id);
        }

        // Graph mode: initialize each organism's metabolic genome segment with
        // small random values, then decode into per-organism metabolism engines.
        let mut init_rng = ChaCha12Rng::seed_from_u64(config.seed.wrapping_add(1));
        if config.metabolism_mode == MetabolismMode::Graph {
            for org in &mut organisms {
                let mut seg = [0.0f32; Genome::METABOLIC_SIZE];
                for v in &mut seg {
                    *v = init_rng.random_range(-0.5f32..0.5);
                }
                org.genome.set_segment_data(1, &seg);
                org.metabolism_engine =
                    decode_organism_metabolism(&org.genome, config.metabolism_mode);
            }
        }

        let max_agent_id = agents.iter().map(|a| a.id).max().unwrap_or(0);
        let metabolism = match config.metabolism_mode {
            MetabolismMode::Toy => MetabolismEngine::default(),
            MetabolismMode::Counter => {
                MetabolismEngine::Counter(crate::metabolism::CounterMetabolism::default())
            }
            MetabolismMode::Graph => {
                MetabolismEngine::Graph(crate::metabolism::GraphMetabolism::default())
            }
        };

        let world_size = config.world_size;
        let org_count = organisms.len();
        let next_organism_stable_id = org_count as u64;
        Ok(Self {
            agents,
            organisms,
            config: config.clone(),
            metabolism,
            resource_field: ResourceField::new(world_size, 1.0, 1.0),
            org_toroidal_sums: vec![[0.0, 0.0, 0.0, 0.0]; org_count],
            org_counts: vec![0; org_count],
            rng: ChaCha12Rng::seed_from_u64(config.seed),
            next_agent_id: max_agent_id.saturating_add(1),
            step_index: 0,
            births_last_step: 0,
            deaths_last_step: 0,
            total_births: 0,
            total_deaths: 0,
            mutation_rates: Self::mutation_rates_from_config(&config),
            next_organism_stable_id,
            agent_id_exhaustions_last_step: 0,
            total_agent_id_exhaustions: 0,
            lifespans: Vec::new(),
            lineage_events: Vec::new(),
            current_resource_rate: config.resource_regeneration_rate,
        })
    }

    fn mutation_rates_from_config(config: &SimConfig) -> MutationRates {
        MutationRates {
            point_rate: config.mutation_point_rate,
            point_scale: config.mutation_point_scale,
            reset_rate: config.mutation_reset_rate,
            scale_rate: config.mutation_scale_rate,
            scale_min: config.mutation_scale_min,
            scale_max: config.mutation_scale_max,
            value_limit: config.mutation_value_limit,
        }
    }

    fn validate_config_common(config: &SimConfig) -> Result<(), WorldInitError> {
        if !(config.world_size.is_finite() && config.world_size > 0.0) {
            return Err(WorldInitError::InvalidWorldSize);
        }
        if config.world_size > Self::MAX_WORLD_SIZE {
            return Err(WorldInitError::WorldSizeTooLarge {
                max: Self::MAX_WORLD_SIZE,
                actual: config.world_size,
            });
        }
        if !(config.dt.is_finite() && config.dt > 0.0) {
            return Err(WorldInitError::InvalidDt);
        }
        if !(config.max_speed.is_finite() && config.max_speed > 0.0) {
            return Err(WorldInitError::InvalidMaxSpeed);
        }
        if !(config.sensing_radius.is_finite() && config.sensing_radius >= 0.0) {
            return Err(WorldInitError::InvalidSensingRadius);
        }
        if !(config.neighbor_norm.is_finite() && config.neighbor_norm > 0.0) {
            return Err(WorldInitError::InvalidNeighborNorm);
        }
        if !(config.metabolic_viability_floor.is_finite()
            && config.metabolic_viability_floor >= 0.0)
        {
            return Err(WorldInitError::InvalidMetabolicViabilityFloor);
        }
        if !(config.boundary_decay_base_rate.is_finite() && config.boundary_decay_base_rate >= 0.0)
        {
            return Err(WorldInitError::InvalidBoundaryDecayBaseRate);
        }
        if !(config.boundary_decay_energy_scale.is_finite()
            && config.boundary_decay_energy_scale >= 0.0)
        {
            return Err(WorldInitError::InvalidBoundaryDecayEnergyScale);
        }
        if !(config.boundary_waste_pressure_scale.is_finite()
            && config.boundary_waste_pressure_scale >= 0.0)
        {
            return Err(WorldInitError::InvalidBoundaryWastePressureScale);
        }
        if !(config.boundary_repair_waste_penalty_scale.is_finite()
            && config.boundary_repair_waste_penalty_scale >= 0.0)
        {
            return Err(WorldInitError::InvalidBoundaryRepairWastePenaltyScale);
        }
        if !(config.boundary_repair_rate.is_finite() && config.boundary_repair_rate >= 0.0) {
            return Err(WorldInitError::InvalidBoundaryRepairRate);
        }
        if !(config.boundary_collapse_threshold.is_finite()
            && (0.0..=1.0).contains(&config.boundary_collapse_threshold))
        {
            return Err(WorldInitError::InvalidBoundaryCollapseThreshold);
        }
        if !(config.death_energy_threshold.is_finite() && config.death_energy_threshold >= 0.0) {
            return Err(WorldInitError::InvalidDeathEnergyThreshold);
        }
        if !(config.death_boundary_threshold.is_finite()
            && (0.0..=1.0).contains(&config.death_boundary_threshold))
        {
            return Err(WorldInitError::InvalidDeathBoundaryThreshold);
        }
        if !(config.reproduction_min_energy.is_finite() && config.reproduction_min_energy >= 0.0) {
            return Err(WorldInitError::InvalidReproductionMinEnergy);
        }
        if !(config.reproduction_min_boundary.is_finite()
            && (0.0..=1.0).contains(&config.reproduction_min_boundary))
        {
            return Err(WorldInitError::InvalidReproductionMinBoundary);
        }
        if !(config.reproduction_energy_cost.is_finite() && config.reproduction_energy_cost > 0.0) {
            return Err(WorldInitError::InvalidReproductionEnergyCost);
        }
        if config.reproduction_min_energy < config.reproduction_energy_cost {
            return Err(WorldInitError::InvalidReproductionEnergyBalance);
        }
        if config.reproduction_child_min_agents == 0 {
            return Err(WorldInitError::InvalidReproductionChildMinAgents);
        }
        if !(config.reproduction_spawn_radius.is_finite()
            && config.reproduction_spawn_radius >= 0.0)
        {
            return Err(WorldInitError::InvalidReproductionSpawnRadius);
        }
        if !(config.crowding_neighbor_threshold.is_finite()
            && config.crowding_neighbor_threshold >= 0.0)
        {
            return Err(WorldInitError::InvalidCrowdingNeighborThreshold);
        }
        if !(config.crowding_boundary_decay.is_finite() && config.crowding_boundary_decay >= 0.0) {
            return Err(WorldInitError::InvalidCrowdingBoundaryDecay);
        }
        if config.max_organism_age_steps == 0 {
            return Err(WorldInitError::InvalidMaxOrganismAgeSteps);
        }
        if config.compaction_interval_steps == 0 {
            return Err(WorldInitError::InvalidCompactionIntervalSteps);
        }
        if !(config.mutation_point_rate.is_finite()
            && (0.0..=1.0).contains(&config.mutation_point_rate))
        {
            return Err(WorldInitError::InvalidMutationPointRate);
        }
        if !(config.mutation_point_scale.is_finite() && config.mutation_point_scale >= 0.0) {
            return Err(WorldInitError::InvalidMutationPointScale);
        }
        if !(config.mutation_reset_rate.is_finite()
            && (0.0..=1.0).contains(&config.mutation_reset_rate))
        {
            return Err(WorldInitError::InvalidMutationResetRate);
        }
        if !(config.mutation_scale_rate.is_finite()
            && (0.0..=1.0).contains(&config.mutation_scale_rate))
        {
            return Err(WorldInitError::InvalidMutationScaleRate);
        }
        if !(config.mutation_scale_min.is_finite()
            && config.mutation_scale_max.is_finite()
            && config.mutation_scale_min > 0.0
            && config.mutation_scale_max > 0.0
            && config.mutation_scale_min <= config.mutation_scale_max)
        {
            return Err(WorldInitError::InvalidMutationScaleBounds);
        }
        if !(config.mutation_value_limit.is_finite() && config.mutation_value_limit > 0.0) {
            return Err(WorldInitError::InvalidMutationValueLimit);
        }
        let mutation_budget =
            config.mutation_point_rate + config.mutation_reset_rate + config.mutation_scale_rate;
        if mutation_budget > 1.0 + f32::EPSILON {
            return Err(WorldInitError::InvalidMutationProbabilityBudget);
        }
        if !(config.homeostasis_decay_rate.is_finite() && config.homeostasis_decay_rate >= 0.0) {
            return Err(WorldInitError::InvalidHomeostasisDecayRate);
        }
        if config.growth_maturation_steps == 0 {
            return Err(WorldInitError::InvalidGrowthMaturationSteps);
        }
        if !(config.growth_immature_metabolic_efficiency.is_finite()
            && (0.0..=1.0).contains(&config.growth_immature_metabolic_efficiency))
        {
            return Err(WorldInitError::InvalidGrowthImmatureMetabolicEfficiency);
        }
        if !(config.resource_regeneration_rate.is_finite()
            && config.resource_regeneration_rate >= 0.0)
        {
            return Err(WorldInitError::InvalidResourceRegenerationRate);
        }
        if !(config.environment_shift_resource_rate.is_finite()
            && config.environment_shift_resource_rate >= 0.0)
        {
            return Err(WorldInitError::InvalidEnvironmentShiftResourceRate);
        }
        if !(config.metabolism_efficiency_multiplier.is_finite()
            && (0.0..=1.0).contains(&config.metabolism_efficiency_multiplier))
        {
            return Err(WorldInitError::InvalidMetabolismEfficiencyMultiplier);
        }
        if !(config.environment_cycle_low_rate.is_finite()
            && config.environment_cycle_low_rate >= 0.0)
        {
            return Err(WorldInitError::InvalidEnvironmentCycleLowRate);
        }
        if config.environment_shift_step > 0 && config.environment_cycle_period > 0 {
            return Err(WorldInitError::ConflictingEnvironmentFeatures);
        }
        Ok(())
    }

    pub fn config(&self) -> &SimConfig {
        &self.config
    }

    pub fn set_config(&mut self, config: SimConfig) -> Result<(), WorldInitError> {
        let mode_changed = self.config.metabolism_mode != config.metabolism_mode;
        Self::validate_config_common(&config)?;
        if config.num_organisms != self.organisms.len() {
            return Err(WorldInitError::NumOrganismsMismatch {
                expected: config.num_organisms,
                actual: self.organisms.len(),
            });
        }
        let expected_agent_count = config
            .num_organisms
            .checked_mul(config.agents_per_organism)
            .ok_or(WorldInitError::AgentCountOverflow)?;
        if self.agents.len() != expected_agent_count {
            return Err(WorldInitError::AgentCountMismatch {
                expected: expected_agent_count,
                actual: self.agents.len(),
            });
        }
        if (self.config.world_size - config.world_size).abs() > f64::EPSILON {
            self.resource_field = ResourceField::new(config.world_size, 1.0, 1.0);
        }
        self.current_resource_rate = config.resource_regeneration_rate;
        self.config = config;
        self.mutation_rates = Self::mutation_rates_from_config(&self.config);
        if mode_changed {
            self.metabolism = match self.config.metabolism_mode {
                MetabolismMode::Toy => MetabolismEngine::default(),
                MetabolismMode::Counter => {
                    MetabolismEngine::Counter(crate::metabolism::CounterMetabolism::default())
                }
                MetabolismMode::Graph => {
                    MetabolismEngine::Graph(crate::metabolism::GraphMetabolism::default())
                }
            };
        }
        Ok(())
    }

    pub fn set_metabolism_engine(&mut self, engine: MetabolismEngine) {
        self.metabolism = engine;
    }

    pub fn resource_field(&self) -> &ResourceField {
        &self.resource_field
    }

    pub fn resource_field_mut(&mut self) -> &mut ResourceField {
        &mut self.resource_field
    }

    pub fn metabolic_state(&self, organism_id: usize) -> &MetabolicState {
        self.try_metabolic_state(organism_id)
            .expect("organism_id out of range for metabolic_state")
    }

    pub fn try_metabolic_state(&self, organism_id: usize) -> Option<&MetabolicState> {
        self.organisms.get(organism_id).map(|o| &o.metabolic_state)
    }

    pub fn organism_count(&self) -> usize {
        self.organisms.len()
    }

    pub fn population_stats(&self) -> PopulationStats {
        let alive = self.alive_count();
        let generation_sum = self
            .organisms
            .iter()
            .filter(|o| o.alive)
            .map(|o| o.generation as f32)
            .sum::<f32>();
        PopulationStats {
            population_size: alive,
            alive_count: alive,
            total_births: self.total_births,
            total_deaths: self.total_deaths,
            mean_generation: if alive > 0 {
                generation_sum / alive as f32
            } else {
                0.0
            },
        }
    }

    fn live_flags(&self) -> Vec<bool> {
        self.organisms.iter().map(|o| o.alive).collect()
    }

    fn alive_count(&self) -> usize {
        self.organisms.iter().filter(|o| o.alive).count()
    }

    fn terminal_boundary_threshold(&self) -> f32 {
        self.config
            .boundary_collapse_threshold
            .max(self.config.death_boundary_threshold)
    }

    fn next_agent_id_checked(&mut self) -> Option<u32> {
        if self.next_agent_id == u32::MAX {
            return None;
        }
        let id = self.next_agent_id;
        self.next_agent_id += 1;
        Some(id)
    }

    fn compute_organism_centers(&self) -> Vec<Option<[f64; 2]>> {
        let world_size = self.config.world_size;
        let tau_over_world = (2.0 * PI) / world_size;
        let mut sums = vec![[0.0f64, 0.0, 0.0, 0.0]; self.organisms.len()];
        let mut counts = vec![0usize; self.organisms.len()];

        for agent in &self.agents {
            let idx = agent.organism_id as usize;
            if !self.organisms.get(idx).map(|o| o.alive).unwrap_or(false) {
                continue;
            }
            let theta_x = agent.position[0] * tau_over_world;
            let theta_y = agent.position[1] * tau_over_world;
            sums[idx][0] += theta_x.sin();
            sums[idx][1] += theta_x.cos();
            sums[idx][2] += theta_y.sin();
            sums[idx][3] += theta_y.cos();
            counts[idx] += 1;
        }

        let mut centers = vec![None; self.organisms.len()];
        for idx in 0..self.organisms.len() {
            if counts[idx] == 0 {
                continue;
            }
            centers[idx] = Some([
                Self::toroidal_mean_coord(sums[idx][0], sums[idx][1], world_size),
                Self::toroidal_mean_coord(sums[idx][2], sums[idx][3], world_size),
            ]);
        }
        centers
    }

    fn prune_dead_entities(&mut self) {
        if self.organisms.iter().all(|o| o.alive) {
            return;
        }

        let old_organisms = std::mem::take(&mut self.organisms);
        let mut remap = vec![None::<u16>; old_organisms.len()];
        let mut new_organisms = Vec::with_capacity(old_organisms.len());
        for (old_idx, mut org) in old_organisms.into_iter().enumerate() {
            if !org.alive {
                continue;
            }
            let new_id = new_organisms.len() as u16;
            remap[old_idx] = Some(new_id);
            org.id = new_id;
            org.agent_ids.clear();
            new_organisms.push(org);
        }

        let old_agents = std::mem::take(&mut self.agents);
        let mut new_agents = Vec::with_capacity(old_agents.len());
        for mut agent in old_agents {
            if let Some(new_org_id) = remap
                .get(agent.organism_id as usize)
                .and_then(|mapped| *mapped)
            {
                agent.organism_id = new_org_id;
                new_agents.push(agent);
            }
        }

        self.organisms = new_organisms;
        self.agents = new_agents;
        for agent in &self.agents {
            self.organisms[agent.organism_id as usize]
                .agent_ids
                .push(agent.id);
        }
        self.org_toroidal_sums
            .resize(self.organisms.len(), [0.0, 0.0, 0.0, 0.0]);
        self.org_counts.resize(self.organisms.len(), 0);
        self.org_toroidal_sums.fill([0.0, 0.0, 0.0, 0.0]);
        self.org_counts.fill(0);
    }

    fn toroidal_mean_coord(sum_sin: f64, sum_cos: f64, world_size: f64) -> f64 {
        if sum_sin == 0.0 && sum_cos == 0.0 {
            return 0.0;
        }
        let angle = sum_sin.atan2(sum_cos);
        (angle.rem_euclid(2.0 * PI) / (2.0 * PI)) * world_size
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

    fn collect_step_metrics(&self, step: usize) -> StepMetrics {
        let alive = self.alive_count();
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

        for org in self.organisms.iter().filter(|o| o.alive) {
            energy_sum += org.metabolic_state.energy;
            waste_sum += org.metabolic_state.waste;
            boundary_sum += org.boundary_integrity;
            generation_sum += org.generation as f32;
            drift_sum += Self::genome_drift(org);
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

        // Internal state: mean and SD across all alive agents (single-pass collection)
        let alive_states: Vec<[f32; 4]> = self
            .agents
            .iter()
            .filter(|a| {
                self.organisms
                    .get(a.organism_id as usize)
                    .map(|o| o.alive)
                    .unwrap_or(false)
            })
            .map(|a| a.internal_state)
            .collect();

        let is_count = alive_states.len();
        let is_denom = is_count.max(1) as f32;
        let mut is_sums = [0.0f32; 4];
        for state in &alive_states {
            for (s, &v) in is_sums.iter_mut().zip(state) {
                *s += v;
            }
        }
        let internal_state_mean = [
            is_sums[0] / is_denom,
            is_sums[1] / is_denom,
            is_sums[2] / is_denom,
            is_sums[3] / is_denom,
        ];

        let mut is_var = [0.0f32; 4];
        if is_count >= 2 {
            for state in &alive_states {
                for ((v, &s), &m) in is_var.iter_mut().zip(state).zip(&internal_state_mean) {
                    *v += (s - m).powi(2);
                }
            }
            for v in &mut is_var {
                *v = (*v / (is_count - 1) as f32).sqrt();
            }
        }

        // Genome diversity: mean L2 distance between sampled pairs of alive organism genomes
        let genome_diversity = self.compute_genome_diversity();

        // Spatial cohesion: mean pairwise agent distance per organism (toroidal-aware)
        let spatial_cohesion_mean = self.compute_spatial_cohesion();

        StepMetrics {
            step,
            energy_mean,
            waste_mean,
            boundary_mean,
            alive_count: alive,
            resource_total: self.resource_field.total(),
            birth_count: self.births_last_step,
            death_count: self.deaths_last_step,
            population_size: self.organisms.len(),
            mean_generation: generation_sum / denom,
            mean_genome_drift: drift_sum / denom,
            agent_id_exhaustion_events: self.agent_id_exhaustions_last_step,
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

    fn compute_genome_diversity(&self) -> f32 {
        let alive_genomes: Vec<&[f32]> = self
            .organisms
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
            let mut sample_rng = ChaCha12Rng::seed_from_u64(self.step_index as u64);
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

    /// Effective sensing radius for an organism, accounting for developmental stage.
    fn effective_sensing_radius(&self, org_idx: usize) -> f64 {
        let dev_sensing = if self.config.enable_growth {
            self.organisms[org_idx]
                .developmental_program
                .stage_factors(self.organisms[org_idx].maturity)
                .1
        } else {
            1.0
        };
        self.config.sensing_radius * dev_sensing as f64
    }

    /// Compute mean pairwise agent distance per alive organism (toroidal-aware).
    /// Lower values indicate tighter spatial cohesion.
    fn compute_spatial_cohesion(&self) -> f32 {
        let world_size = self.config.world_size;
        let half = world_size * 0.5;
        let mut org_cohesions = Vec::new();

        for org in self.organisms.iter().filter(|o| o.alive) {
            let positions: Vec<[f64; 2]> = self
                .agents
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

    pub fn run_experiment(&mut self, steps: usize, sample_every: usize) -> RunSummary {
        self.try_run_experiment(steps, sample_every)
            .unwrap_or_else(|e| panic!("{e}"))
    }

    pub fn try_run_experiment(
        &mut self,
        steps: usize,
        sample_every: usize,
    ) -> Result<RunSummary, ExperimentError> {
        if sample_every == 0 {
            return Err(ExperimentError::InvalidSampleEvery);
        }
        if steps > Self::MAX_EXPERIMENT_STEPS {
            return Err(ExperimentError::TooManySteps {
                max: Self::MAX_EXPERIMENT_STEPS,
                actual: steps,
            });
        }
        let estimated_samples = if steps == 0 {
            0
        } else {
            ((steps - 1) / sample_every) + 1
        };
        if estimated_samples > Self::MAX_EXPERIMENT_SAMPLES {
            return Err(ExperimentError::TooManySamples {
                max: Self::MAX_EXPERIMENT_SAMPLES,
                actual: estimated_samples,
            });
        }

        self.lifespans.clear();
        self.lineage_events.clear();
        let births_before = self.total_births;
        let mut samples = Vec::with_capacity(estimated_samples);
        for step in 1..=steps {
            self.step();
            if step % sample_every == 0 || step == steps {
                samples.push(self.collect_step_metrics(step));
            }
        }
        Ok(RunSummary {
            steps,
            sample_every,
            final_alive_count: self.alive_count(),
            samples,
            lifespans: std::mem::take(&mut self.lifespans),
            total_reproduction_events: self.total_births - births_before,
            lineage_events: std::mem::take(&mut self.lineage_events),
        })
    }

    fn mark_dead(&mut self, org_idx: usize) {
        if let Some(org) = self.organisms.get_mut(org_idx) {
            if org.alive {
                self.lifespans.push(org.age_steps);
                org.alive = false;
                org.boundary_integrity = 0.0;
                self.deaths_last_step += 1;
                self.total_deaths += 1;
            }
        }
    }

    fn maybe_reproduce(&mut self) {
        let child_agents =
            (self.config.agents_per_organism / 2).max(self.config.reproduction_child_min_agents);
        let parent_indices: Vec<usize> = self
            .organisms
            .iter()
            .enumerate()
            .filter_map(|(idx, org)| {
                let mature_enough = org.maturity >= 1.0;
                (org.alive
                    && org.metabolic_state.energy >= self.config.reproduction_min_energy
                    && org.boundary_integrity >= self.config.reproduction_min_boundary
                    && mature_enough)
                    .then_some(idx)
            })
            .collect();
        if parent_indices.is_empty() {
            return;
        }
        let centers = self.compute_organism_centers();

        for parent_idx in parent_indices {
            if self
                .agents
                .len()
                .checked_add(child_agents)
                .map(|n| n > Self::MAX_TOTAL_AGENTS)
                .unwrap_or(true)
            {
                break;
            }
            let remaining_ids = u32::MAX as u64 - self.next_agent_id as u64;
            if remaining_ids + 1 < child_agents as u64 {
                self.agent_id_exhaustions_last_step += 1;
                self.total_agent_id_exhaustions += 1;
                break;
            }

            let center = centers
                .get(parent_idx)
                .and_then(|c| *c)
                .unwrap_or([0.0, 0.0]);
            let (parent_generation, parent_stable_id, parent_ancestor, mut child_genome) = {
                let parent = &self.organisms[parent_idx];
                if !parent.alive
                    || parent.metabolic_state.energy < self.config.reproduction_energy_cost
                {
                    continue;
                }
                (
                    parent.generation,
                    parent.stable_id,
                    parent.ancestor_genome.clone(),
                    parent.genome.clone(),
                )
            };

            self.organisms[parent_idx].metabolic_state.energy -=
                self.config.reproduction_energy_cost;

            if self.config.enable_evolution {
                child_genome.mutate(&mut self.rng, &self.mutation_rates);
            }
            let child_weights = if child_genome.nn_weights().len() == NeuralNet::WEIGHT_COUNT {
                child_genome.nn_weights().to_vec()
            } else {
                self.organisms[parent_idx].nn.to_weight_vec()
            };
            let child_nn = NeuralNet::from_weights(child_weights.into_iter());
            let child_id = match u16::try_from(self.organisms.len()) {
                Ok(id) => id,
                Err(_) => break,
            };
            let mut child_agent_ids = Vec::with_capacity(child_agents);

            for _ in 0..child_agents {
                let theta = self.rng.random::<f64>() * 2.0 * PI;
                let radius =
                    self.rng.random::<f64>().sqrt() * self.config.reproduction_spawn_radius;
                let pos = [
                    (center[0] + radius * theta.cos()).rem_euclid(self.config.world_size),
                    (center[1] + radius * theta.sin()).rem_euclid(self.config.world_size),
                ];
                let Some(id) = self.next_agent_id_checked() else {
                    break;
                };
                let mut agent = Agent::new(id, child_id, pos);
                agent.internal_state[2] = 1.0;
                child_agent_ids.push(id);
                self.agents.push(agent);
            }
            if child_agent_ids.is_empty() {
                break;
            }

            let metabolic_state = MetabolicState {
                energy: self.config.reproduction_energy_cost,
                ..MetabolicState::default()
            };
            let child_metabolism_engine =
                decode_organism_metabolism(&child_genome, self.config.metabolism_mode);
            let developmental_program = DevelopmentalProgram::decode(child_genome.segment_data(3));
            let child_stable_id = self.next_organism_stable_id;
            let child_generation = parent_generation + 1;
            let child = OrganismRuntime {
                id: child_id,
                stable_id: child_stable_id,
                generation: child_generation,
                age_steps: 0,
                alive: true,
                boundary_integrity: 1.0,
                metabolic_state,
                genome: child_genome,
                ancestor_genome: parent_ancestor,
                nn: child_nn,
                agent_ids: child_agent_ids,
                maturity: 0.0,
                metabolism_engine: child_metabolism_engine,
                developmental_program,
                parent_stable_id: Some(parent_stable_id),
            };
            self.next_organism_stable_id = self.next_organism_stable_id.saturating_add(1);
            self.lineage_events.push(LineageEvent {
                step: self.step_index,
                parent_stable_id,
                child_stable_id,
                generation: child_generation,
            });
            self.organisms.push(child);
            self.org_toroidal_sums.push([0.0, 0.0, 0.0, 0.0]);
            self.org_counts.push(0);
            self.births_last_step += 1;
            self.total_births += 1;
        }
    }

    pub fn step(&mut self) -> StepTimings {
        let total_start = Instant::now();
        self.step_index = self.step_index.saturating_add(1);
        self.births_last_step = 0;
        self.deaths_last_step = 0;
        self.agent_id_exhaustions_last_step = 0;
        let boundary_terminal_threshold = self.terminal_boundary_threshold();

        let t0 = Instant::now();
        let live_flags = self.live_flags();
        let tree = spatial::build_index_active(&self.agents, &live_flags);
        let spatial_build_us = t0.elapsed().as_micros() as u64;

        let t1 = Instant::now();
        let mut deltas: Vec<[f32; 4]> = Vec::with_capacity(self.agents.len());
        let mut neighbor_sums = vec![0.0f32; self.organisms.len()];
        let mut neighbor_counts = vec![0usize; self.organisms.len()];

        for agent in &self.agents {
            let org_idx = agent.organism_id as usize;
            if !self
                .organisms
                .get(org_idx)
                .map(|o| o.alive)
                .unwrap_or(false)
            {
                deltas.push([0.0; 4]);
                continue;
            }
            let effective_radius = self.effective_sensing_radius(org_idx);
            let neighbor_count = spatial::count_neighbors(
                &tree,
                agent.position,
                effective_radius,
                agent.id,
                self.config.world_size,
            );

            neighbor_sums[org_idx] += neighbor_count as f32;
            neighbor_counts[org_idx] += 1;

            let input: [f32; 8] = [
                (agent.position[0] / self.config.world_size) as f32,
                (agent.position[1] / self.config.world_size) as f32,
                (agent.velocity[0] / self.config.max_speed) as f32,
                (agent.velocity[1] / self.config.max_speed) as f32,
                agent.internal_state[0],
                agent.internal_state[1],
                agent.internal_state[2],
                neighbor_count as f32 / self.config.neighbor_norm as f32,
            ];
            let nn = &self.organisms[org_idx].nn;
            deltas.push(nn.forward(&input));
        }
        let nn_query_us = t1.elapsed().as_micros() as u64;

        let t2 = Instant::now();
        for (agent, delta) in self.agents.iter_mut().zip(deltas.iter()) {
            let org_idx = agent.organism_id as usize;
            if !self.organisms[org_idx].alive {
                agent.velocity = [0.0, 0.0];
                continue;
            }

            if self.config.enable_response {
                agent.velocity[0] += delta[0] as f64 * self.config.dt;
                agent.velocity[1] += delta[1] as f64 * self.config.dt;
            }

            let speed_sq =
                agent.velocity[0] * agent.velocity[0] + agent.velocity[1] * agent.velocity[1];
            if speed_sq > self.config.max_speed * self.config.max_speed {
                let scale = self.config.max_speed / speed_sq.sqrt();
                agent.velocity[0] *= scale;
                agent.velocity[1] *= scale;
            }

            agent.position[0] = (agent.position[0] + agent.velocity[0] * self.config.dt)
                .rem_euclid(self.config.world_size);
            agent.position[1] = (agent.position[1] + agent.velocity[1] * self.config.dt)
                .rem_euclid(self.config.world_size);

            // Homeostatic entropy: internal state decays toward 0 each step
            let h_decay = self.config.homeostasis_decay_rate * self.config.dt as f32;
            agent.internal_state[0] = (agent.internal_state[0] - h_decay).max(0.0);
            agent.internal_state[1] = (agent.internal_state[1] - h_decay).max(0.0);

            if self.config.enable_homeostasis {
                agent.internal_state[0] =
                    (agent.internal_state[0] + delta[2] * self.config.dt as f32).clamp(0.0, 1.0);
                agent.internal_state[1] =
                    (agent.internal_state[1] + delta[3] * self.config.dt as f32).clamp(0.0, 1.0);
            }
        }

        if self.config.enable_boundary_maintenance {
            // Pre-collect average internal_state[0] per organism for homeostasis coupling
            let homeostasis_factors: Vec<f32> = {
                let mut sums = vec![0.0f32; self.organisms.len()];
                let mut counts = vec![0usize; self.organisms.len()];
                for agent in &self.agents {
                    let idx = agent.organism_id as usize;
                    if self.organisms[idx].alive {
                        sums[idx] += agent.internal_state[0];
                        counts[idx] += 1;
                    }
                }
                sums.iter()
                    .zip(counts.iter())
                    .map(|(&s, &c)| if c > 0 { s / c as f32 } else { 0.5 })
                    .collect()
            };

            let dt = self.config.dt as f32;
            let mut to_kill = Vec::new();
            for (org_idx, org) in self.organisms.iter_mut().enumerate() {
                if !org.alive {
                    org.boundary_integrity = 0.0;
                    continue;
                }

                let energy_deficit =
                    (self.config.metabolic_viability_floor - org.metabolic_state.energy).max(0.0);
                let decay = self.config.boundary_decay_base_rate
                    + self.config.boundary_decay_energy_scale
                        * (energy_deficit
                            + org.metabolic_state.waste
                                * self.config.boundary_waste_pressure_scale);
                let homeostasis_factor = homeostasis_factors[org_idx];
                let dev_boundary = if self.config.enable_growth {
                    org.developmental_program.stage_factors(org.maturity).0
                } else {
                    1.0
                };
                let repair = (org.metabolic_state.energy
                    - org.metabolic_state.waste
                        * self.config.boundary_waste_pressure_scale
                        * self.config.boundary_repair_waste_penalty_scale)
                    .max(0.0)
                    * self.config.boundary_repair_rate
                    * homeostasis_factor
                    * dev_boundary;
                org.boundary_integrity =
                    (org.boundary_integrity - decay * dt + repair * dt).clamp(0.0, 1.0);
                if org.boundary_integrity <= boundary_terminal_threshold {
                    to_kill.push(org_idx);
                }
            }
            for org_idx in to_kill {
                self.mark_dead(org_idx);
            }

            for agent in &mut self.agents {
                let boundary = self.organisms[agent.organism_id as usize].boundary_integrity;
                agent.internal_state[2] = boundary;
            }
        }

        if self.config.enable_metabolism {
            self.org_toroidal_sums.fill([0.0, 0.0, 0.0, 0.0]);
            self.org_counts.fill(0);
            let world_size = self.config.world_size;
            let tau_over_world = (2.0 * PI) / world_size;

            for agent in &self.agents {
                let idx = agent.organism_id as usize;
                if !self.organisms[idx].alive {
                    continue;
                }
                let theta_x = agent.position[0] * tau_over_world;
                let theta_y = agent.position[1] * tau_over_world;
                self.org_toroidal_sums[idx][0] += theta_x.sin();
                self.org_toroidal_sums[idx][1] += theta_x.cos();
                self.org_toroidal_sums[idx][2] += theta_y.sin();
                self.org_toroidal_sums[idx][3] += theta_y.cos();
                self.org_counts[idx] += 1;
            }

            let mut to_kill = Vec::new();
            for (org_idx, org) in self.organisms.iter_mut().enumerate() {
                if !org.alive {
                    continue;
                }
                let center = if self.org_counts[org_idx] > 0 {
                    [
                        Self::toroidal_mean_coord(
                            self.org_toroidal_sums[org_idx][0],
                            self.org_toroidal_sums[org_idx][1],
                            world_size,
                        ),
                        Self::toroidal_mean_coord(
                            self.org_toroidal_sums[org_idx][2],
                            self.org_toroidal_sums[org_idx][3],
                            world_size,
                        ),
                    ]
                } else {
                    [0.0, 0.0]
                };
                let external = self.resource_field.get(center[0], center[1]);
                let pre_energy = org.metabolic_state.energy;
                let engine = org.metabolism_engine.as_ref().unwrap_or(&self.metabolism);
                let flux = engine.step(&mut org.metabolic_state, external, self.config.dt as f32);
                // Graded ablation: scale metabolic energy gains by efficiency multiplier
                // Growth: immature organisms have reduced metabolic efficiency (gains only)
                {
                    let energy_delta = org.metabolic_state.energy - pre_energy;
                    if energy_delta > 0.0 {
                        let growth_factor = if self.config.enable_growth {
                            org.developmental_program.stage_factors(org.maturity).2
                        } else {
                            self.config.growth_immature_metabolic_efficiency
                                + org.maturity
                                    * (1.0 - self.config.growth_immature_metabolic_efficiency)
                        };
                        org.metabolic_state.energy = pre_energy
                            + energy_delta
                                * growth_factor
                                * self.config.metabolism_efficiency_multiplier;
                    }
                    // energy losses from metabolism are preserved as-is
                }
                if flux.consumed_external > 0.0 {
                    let _ = self
                        .resource_field
                        .take(center[0], center[1], flux.consumed_external);
                }

                if org.metabolic_state.energy <= self.config.death_energy_threshold
                    || org.boundary_integrity <= boundary_terminal_threshold
                {
                    to_kill.push(org_idx);
                }
            }
            for org_idx in to_kill {
                self.mark_dead(org_idx);
            }
        }

        let mut to_kill = Vec::new();
        for (org_idx, org) in self.organisms.iter_mut().enumerate() {
            if !org.alive {
                continue;
            }
            org.age_steps = org.age_steps.saturating_add(1);
            if org.age_steps > self.config.max_organism_age_steps {
                to_kill.push(org_idx);
                continue;
            }

            // Growth: advance maturation with genome-encoded rate modifier
            if self.config.enable_growth && org.maturity < 1.0 {
                let base_rate = 1.0 / self.config.growth_maturation_steps as f32;
                let rate = base_rate * org.developmental_program.maturation_rate_modifier;
                org.maturity = (org.maturity + rate).min(1.0);
            }

            let avg_neighbors = if neighbor_counts[org_idx] > 0 {
                neighbor_sums[org_idx] / neighbor_counts[org_idx] as f32
            } else {
                0.0
            };
            if avg_neighbors > self.config.crowding_neighbor_threshold {
                let excess = avg_neighbors - self.config.crowding_neighbor_threshold;
                org.boundary_integrity = (org.boundary_integrity
                    - excess * self.config.crowding_boundary_decay * self.config.dt as f32)
                    .clamp(0.0, 1.0);
            }
            if org.boundary_integrity <= boundary_terminal_threshold {
                to_kill.push(org_idx);
            }
        }
        for org_idx in to_kill {
            self.mark_dead(org_idx);
        }

        if self.config.enable_reproduction {
            self.maybe_reproduce();
        }
        let dead_count = self.organisms.iter().filter(|o| !o.alive).count();
        if dead_count > 0
            && (self
                .step_index
                .is_multiple_of(self.config.compaction_interval_steps)
                || dead_count * 4 >= self.organisms.len().max(1))
        {
            self.prune_dead_entities();
        }

        // Sham process: compute spatial neighbor queries (real work) but discard result.
        // Uses the same spatial tree that real criteria use during this step,
        // matching computational cost without functional effect.
        if self.config.enable_sham_process {
            let mut _sham_sum: f64 = 0.0;
            for agent in &self.agents {
                let org_idx = agent.organism_id as usize;
                if !self.organisms.get(org_idx).is_some_and(|o| o.alive) {
                    continue;
                }
                let effective_radius = self.effective_sensing_radius(org_idx);
                let neighbor_count = spatial::count_neighbors(
                    &tree,
                    agent.position,
                    effective_radius,
                    agent.id,
                    self.config.world_size,
                );
                _sham_sum += neighbor_count as f64;
            }
        }

        // Environment shift: change runtime resource rate at specified step.
        // Uses a separate field to keep self.config immutable at runtime.
        if self.config.environment_shift_step > 0
            && self.step_index == self.config.environment_shift_step
        {
            self.current_resource_rate = self.config.environment_shift_resource_rate;
        }

        // Cyclic environment: alternate resource rate between high and low phases.
        // Separate from one-time environment_shift; this repeats every cycle_period steps.
        if self.config.environment_cycle_period > 0 {
            let phase = (self.step_index / self.config.environment_cycle_period) % 2;
            self.current_resource_rate = if phase == 0 {
                self.config.resource_regeneration_rate
            } else {
                self.config.environment_cycle_low_rate
            };
        }

        if self.current_resource_rate > 0.0 {
            self.resource_field
                .regenerate(self.current_resource_rate * self.config.dt as f32);
        }

        let state_update_us = t2.elapsed().as_micros() as u64;

        StepTimings {
            spatial_build_us,
            nn_query_us,
            state_update_us,
            total_us: total_start.elapsed().as_micros() as u64,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_world(num_agents: usize, world_size: f64) -> World {
        let agents: Vec<Agent> = (0..num_agents)
            .map(|i| Agent::new(i as u32, 0, [50.0, 50.0]))
            .collect();
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.1f32, NeuralNet::WEIGHT_COUNT));
        let config = SimConfig {
            world_size,
            num_organisms: 1,
            agents_per_organism: num_agents,
            ..SimConfig::default()
        };
        World::new(agents, vec![nn], config)
    }

    fn make_config(world_size: f64, dt: f64) -> SimConfig {
        SimConfig {
            world_size,
            dt,
            num_organisms: 1,
            agents_per_organism: 1,
            ..SimConfig::default()
        }
    }

    #[test]
    fn toroidal_wrapping_keeps_positions_in_bounds() {
        let mut world = make_world(1, 100.0);
        world.agents[0].velocity = [100.0, 100.0];
        world.step();
        let pos = world.agents[0].position;
        assert!(pos[0] >= 0.0 && pos[0] < 100.0);
        assert!(pos[1] >= 0.0 && pos[1] < 100.0);
    }

    #[test]
    fn step_returns_nonzero_timings() {
        let mut world = make_world(10, 100.0);
        let t = world.step();
        assert!(t.total_us > 0);
    }

    #[test]
    #[should_panic(expected = "organism_ids must be valid")]
    fn new_panics_on_invalid_organism_id() {
        let agents = vec![Agent::new(0, 5, [0.0, 0.0])];
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
        World::new(agents, vec![nn], make_config(100.0, 0.1));
    }

    #[test]
    #[should_panic(expected = "world_size must be positive and finite")]
    fn new_panics_on_non_positive_world_size() {
        let agents = vec![Agent::new(0, 0, [0.0, 0.0])];
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
        World::new(agents, vec![nn], make_config(0.0, 0.1));
    }

    #[test]
    #[should_panic(expected = "world_size must be positive and finite")]
    fn new_panics_on_non_finite_world_size() {
        let agents = vec![Agent::new(0, 0, [0.0, 0.0])];
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
        World::new(agents, vec![nn], make_config(f64::NAN, 0.1));
    }

    #[test]
    #[should_panic(expected = "exceeds supported maximum")]
    fn new_panics_on_excessive_world_size() {
        let agents = vec![Agent::new(0, 0, [0.0, 0.0])];
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
        World::new(
            agents,
            vec![nn],
            make_config(World::MAX_WORLD_SIZE + 1.0, 0.1),
        );
    }

    #[test]
    fn internal_state_stays_clamped() {
        let mut world = make_world(1, 100.0);
        for _ in 0..100 {
            world.step();
        }
        for &s in &world.agents[0].internal_state {
            assert!((0.0..=1.0).contains(&s));
        }
    }

    #[test]
    fn step_respects_config_dt_for_position_update() {
        let mut world = make_world(1, 100.0);
        world.agents[0].position = [50.0, 50.0];
        world.agents[0].velocity = [1.0, 0.0];
        world.organisms[0].nn =
            NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
        let mut config = world.config().clone();
        config.dt = 0.5;
        world
            .set_config(config)
            .expect("config with positive dt should be valid");
        world.step();
        assert!(
            (world.agents[0].position[0] - 50.5).abs() < 1e-6,
            "expected x to advance by dt-scaled velocity"
        );
    }

    #[test]
    fn toy_metabolism_sustains_energy_for_1000_steps() {
        let mut world = make_world(10, 100.0);
        world.config.enable_boundary_maintenance = false;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        for _ in 0..1000 {
            world.step();
        }
        assert!(world.organism_count() >= 1);
        assert!(world.metabolic_state(0).energy > 0.0);
    }

    #[test]
    fn try_metabolic_state_returns_none_for_out_of_range() {
        let world = make_world(1, 100.0);
        assert!(world.try_metabolic_state(10).is_none());
    }

    #[test]
    fn try_new_rejects_agent_count_mismatch() {
        let agents = vec![Agent::new(0, 0, [0.0, 0.0])];
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
        let mut cfg = make_config(100.0, 0.1);
        cfg.num_organisms = 1;
        cfg.agents_per_organism = 2;
        let result = World::try_new(agents, vec![nn], cfg);
        assert!(matches!(
            result,
            Err(WorldInitError::AgentCountMismatch { .. })
        ));
    }

    #[test]
    fn try_new_rejects_agent_count_overflow() {
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
        let cfg = SimConfig {
            num_organisms: 3,
            agents_per_organism: usize::MAX / 2 + 1,
            ..SimConfig::default()
        };
        let result = World::try_new(Vec::new(), vec![nn.clone(), nn.clone(), nn], cfg);
        assert!(matches!(result, Err(WorldInitError::AgentCountOverflow)));
    }

    #[test]
    fn try_new_rejects_too_many_agents() {
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
        let cfg = SimConfig {
            num_organisms: 1,
            agents_per_organism: World::MAX_TOTAL_AGENTS + 1,
            ..SimConfig::default()
        };
        let result = World::try_new(Vec::new(), vec![nn], cfg);
        assert!(matches!(result, Err(WorldInitError::TooManyAgents { .. })));
    }

    #[test]
    fn set_config_rejects_invalid_update() {
        let mut world = make_world(1, 100.0);
        let mut cfg = world.config().clone();
        cfg.dt = -0.1;
        let result = world.set_config(cfg);
        assert!(matches!(result, Err(WorldInitError::InvalidDt)));
    }

    #[test]
    fn set_config_rejects_structural_mismatch_after_runtime_growth() {
        let mut world = make_world(10, 100.0);
        world.organisms[0].metabolic_state.energy = 1.0;
        world.organisms[0].boundary_integrity = 1.0;
        world.step();
        assert!(world.organism_count() > 1);

        let mut cfg = world.config().clone();
        cfg.num_organisms = 1;
        let result = world.set_config(cfg);
        assert!(matches!(
            result,
            Err(WorldInitError::NumOrganismsMismatch { .. })
        ));
    }

    #[test]
    fn metabolism_consumes_world_resource_field() {
        let mut world = make_world(1, 100.0);
        world.agents[0].position = [10.0, 10.0];
        let before = world.resource_field().get(10.0, 10.0);
        world.step();
        let after = world.resource_field().get(10.0, 10.0);
        assert!(after <= before);
    }

    #[test]
    fn toroidal_center_uses_wrapped_mean_for_resource_sampling() {
        let mut world = make_world(2, 100.0);
        world.config.resource_regeneration_rate = 0.0;
        world.current_resource_rate = 0.0;
        world.agents[0].position = [0.1, 50.0];
        world.agents[1].position = [99.9, 50.0];
        world.resource_field_mut().set(0.0, 50.0, 2.0);
        world.resource_field_mut().set(50.0, 50.0, 0.0);
        world.step();
        let edge_resource = world.resource_field().get(0.0, 50.0);
        let center_resource = world.resource_field().get(50.0, 50.0);
        assert!(edge_resource < 2.0);
        assert!((center_resource - 0.0).abs() < f32::EPSILON);
    }

    #[test]
    fn run_experiment_produces_non_empty_summary() {
        let mut world = make_world(10, 100.0);
        let summary = world.run_experiment(50, 10);
        assert_eq!(summary.steps, 50);
        assert!(!summary.samples.is_empty());
        assert!(summary.final_alive_count <= world.organism_count());
    }

    #[test]
    fn low_energy_org_decays_boundary_faster() {
        let mut low = make_world(10, 100.0);
        let mut high = make_world(10, 100.0);
        low.config.enable_metabolism = false;
        high.config.enable_metabolism = false;
        low.config.metabolic_viability_floor = 0.8;
        high.config.metabolic_viability_floor = 0.8;
        low.config.boundary_decay_energy_scale = 0.08;
        high.config.boundary_decay_energy_scale = 0.08;
        low.organisms[0].metabolic_state.energy = 0.0;
        high.organisms[0].metabolic_state.energy = 1.0;
        low.organisms[0].metabolic_state.waste = 0.8;
        high.organisms[0].metabolic_state.waste = 0.0;

        low.step();
        high.step();

        assert!(
            low.organisms[0].boundary_integrity < high.organisms[0].boundary_integrity,
            "low-energy high-waste organism should lose boundary integrity faster"
        );
    }

    #[test]
    fn graph_mode_selects_graph_engine() {
        let agents = vec![Agent::new(0, 0, [0.0, 0.0])];
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
        let config = SimConfig {
            num_organisms: 1,
            agents_per_organism: 1,
            metabolism_mode: MetabolismMode::Graph,
            ..SimConfig::default()
        };
        let world = World::new(agents, vec![nn], config);
        assert!(matches!(world.metabolism, MetabolismEngine::Graph(_)));
    }

    #[test]
    fn try_new_rejects_invalid_boundary_decay_config() {
        let agents = vec![Agent::new(0, 0, [0.0, 0.0])];
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
        let cfg = SimConfig {
            num_organisms: 1,
            agents_per_organism: 1,
            boundary_decay_base_rate: -0.1,
            ..SimConfig::default()
        };
        let result = World::try_new(agents, vec![nn], cfg);
        assert!(matches!(
            result,
            Err(WorldInitError::InvalidBoundaryDecayBaseRate)
        ));
    }

    #[test]
    fn try_new_rejects_invalid_mutation_probability_budget() {
        let agents = vec![Agent::new(0, 0, [0.0, 0.0])];
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
        let cfg = SimConfig {
            num_organisms: 1,
            agents_per_organism: 1,
            mutation_point_rate: 0.8,
            mutation_reset_rate: 0.3,
            mutation_scale_rate: 0.1,
            ..SimConfig::default()
        };
        let result = World::try_new(agents, vec![nn], cfg);
        assert!(matches!(
            result,
            Err(WorldInitError::InvalidMutationProbabilityBudget)
        ));
    }

    #[test]
    fn try_new_rejects_reproduction_min_energy_below_cost() {
        let agents = vec![Agent::new(0, 0, [0.0, 0.0])];
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
        let cfg = SimConfig {
            num_organisms: 1,
            agents_per_organism: 1,
            reproduction_min_energy: 0.1,
            reproduction_energy_cost: 0.3,
            ..SimConfig::default()
        };
        let result = World::try_new(agents, vec![nn], cfg);
        assert!(matches!(
            result,
            Err(WorldInitError::InvalidReproductionEnergyBalance)
        ));
    }

    #[test]
    fn try_run_experiment_rejects_too_many_steps() {
        let mut world = make_world(1, 100.0);
        let result = world.try_run_experiment(World::MAX_EXPERIMENT_STEPS + 1, 1);
        assert!(matches!(result, Err(ExperimentError::TooManySteps { .. })));
    }

    #[test]
    fn reproduction_increases_population_when_energy_is_high() {
        let mut world = make_world(10, 100.0);
        world.organisms[0].metabolic_state.energy = 1.0;
        world.organisms[0].boundary_integrity = 1.0;
        let before = world.organism_count();
        world.step();
        assert!(world.organism_count() > before);
        assert!(world.population_stats().total_births >= 1);
    }

    #[test]
    fn reproduction_obeys_configured_thresholds() {
        let mut world = make_world(10, 100.0);
        world.config.reproduction_min_energy = 1.1;
        world.config.reproduction_min_boundary = 0.95;
        world.organisms[0].metabolic_state.energy = 1.0;
        world.organisms[0].boundary_integrity = 0.9;
        let before = world.organism_count();
        world.step();
        assert_eq!(world.organism_count(), before);
        assert_eq!(world.population_stats().total_births, 0);
    }

    #[test]
    fn max_organism_age_steps_is_configurable() {
        let mut world = make_world(10, 100.0);
        world.config.enable_metabolism = false;
        world.config.enable_boundary_maintenance = false;
        world.config.max_organism_age_steps = 1;
        world.config.reproduction_min_energy = 10.0;
        world.config.reproduction_min_boundary = 1.0;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.config.death_energy_threshold = 0.0;
        world.organisms[0].metabolic_state.energy = 1.0;
        world.step();
        assert_eq!(world.organism_count(), 1);
        world.step();
        assert_eq!(world.organism_count(), 0);
    }

    #[test]
    fn same_seed_produces_same_birth_death_timeline() {
        let agents: Vec<Agent> = (0..20)
            .map(|i| Agent::new(i as u32, 0, [50.0, 50.0]))
            .collect();
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.1f32, NeuralNet::WEIGHT_COUNT));
        let config = SimConfig {
            seed: 777,
            num_organisms: 1,
            agents_per_organism: 20,
            ..SimConfig::default()
        };
        let mut a = World::new(agents.clone(), vec![nn.clone()], config.clone());
        let mut b = World::new(agents, vec![nn], config);

        let ra = a.run_experiment(30, 1);
        let rb = b.run_experiment(30, 1);

        let births_a: Vec<usize> = ra.samples.iter().map(|s| s.birth_count).collect();
        let births_b: Vec<usize> = rb.samples.iter().map(|s| s.birth_count).collect();
        let deaths_a: Vec<usize> = ra.samples.iter().map(|s| s.death_count).collect();
        let deaths_b: Vec<usize> = rb.samples.iter().map(|s| s.death_count).collect();
        assert_eq!(births_a, births_b);
        assert_eq!(deaths_a, deaths_b);
    }

    #[test]
    fn metrics_include_evolution_fields() {
        let mut world = make_world(10, 100.0);
        let summary = world.run_experiment(5, 1);
        let sample = summary.samples.last().expect("sample should exist");
        assert!(sample.population_size >= sample.alive_count);
        assert!(sample.mean_generation >= 0.0);
        assert!(sample.mean_genome_drift >= 0.0);
    }

    #[test]
    fn dead_entities_are_pruned_after_step() {
        let mut world = make_world(4, 100.0);
        world.config.enable_metabolism = true;
        world.config.death_energy_threshold = 1.0;
        world.resource_field_mut().set(50.0, 50.0, 0.0);
        world.step();
        assert_eq!(world.organism_count(), 0);
        assert!(world.agents.is_empty());
    }

    #[test]
    fn boundary_terminal_threshold_is_consistent_across_checks() {
        let mut world = make_world(4, 100.0);
        world.config.enable_metabolism = false;
        world.config.boundary_collapse_threshold = 0.05;
        world.config.death_boundary_threshold = 0.10;
        world.organisms[0].boundary_integrity = 0.08;
        world.step();
        assert_eq!(world.organism_count(), 0);
    }

    #[test]
    fn disable_homeostasis_allows_state_decay() {
        let mut world = make_world(10, 100.0);
        world.config.enable_homeostasis = false;
        world.config.homeostasis_decay_rate = 0.05;
        // Disable metabolism and boundary to ensure organism survives all steps
        world.config.enable_metabolism = false;
        world.config.enable_boundary_maintenance = false;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.config.death_energy_threshold = 0.0;
        world.config.enable_reproduction = false;
        let before_0 = world.agents[0].internal_state[0]; // starts at 0.5
        for _ in 0..50 {
            world.step();
        }
        assert!(
            world.organisms[0].alive,
            "organism must survive for valid test"
        );
        assert!(
            world.agents[0].internal_state[0] < before_0,
            "internal_state[0] should decay when homeostasis is disabled"
        );
    }

    #[test]
    fn homeostasis_decay_reduces_internal_state() {
        let mut world = make_world(1, 100.0);
        // Use zero NN weights so NN delta is ~0
        world.organisms[0].nn =
            NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
        world.config.enable_homeostasis = false;
        world.config.homeostasis_decay_rate = 0.1;
        world.config.enable_metabolism = false;
        world.config.enable_boundary_maintenance = false;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.config.death_energy_threshold = 0.0;
        world.config.enable_reproduction = false;
        let before = world.agents[0].internal_state[0]; // 0.5
        world.step();
        assert!(
            world.agents[0].internal_state[0] < before,
            "internal_state[0] should decrease after one step with decay"
        );
    }

    #[test]
    fn homeostasis_enabled_counteracts_decay() {
        // NN with large positive weights should produce positive delta[2] to counteract decay
        let mut world = make_world(1, 100.0);
        world.organisms[0].nn =
            NeuralNet::from_weights(std::iter::repeat_n(1.0f32, NeuralNet::WEIGHT_COUNT));
        world.config.enable_homeostasis = true;
        world.config.homeostasis_decay_rate = 0.001; // small decay
        world.config.enable_metabolism = false;
        world.config.enable_boundary_maintenance = false;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.config.death_energy_threshold = 0.0;
        world.config.enable_reproduction = false;

        // Comparison: same config but homeostasis disabled
        let mut world_no = make_world(1, 100.0);
        world_no.organisms[0].nn =
            NeuralNet::from_weights(std::iter::repeat_n(1.0f32, NeuralNet::WEIGHT_COUNT));
        world_no.config.enable_homeostasis = false;
        world_no.config.homeostasis_decay_rate = 0.001;
        world_no.config.enable_metabolism = false;
        world_no.config.enable_boundary_maintenance = false;
        world_no.config.death_boundary_threshold = 0.0;
        world_no.config.boundary_collapse_threshold = 0.0;
        world_no.config.death_energy_threshold = 0.0;
        world_no.config.enable_reproduction = false;

        for _ in 0..50 {
            world.step();
            world_no.step();
        }
        assert!(
            world.agents[0].internal_state[0] > world_no.agents[0].internal_state[0],
            "homeostasis-enabled should maintain higher internal_state than disabled"
        );
    }

    #[test]
    fn homeostasis_modulates_boundary_repair() {
        // High internal_state[0] → better boundary repair
        let mut world_high = make_world(10, 100.0);
        world_high.config.enable_homeostasis = false;
        world_high.config.homeostasis_decay_rate = 0.0; // no decay, state stays at 0.5
        world_high.config.enable_metabolism = false;
        world_high.config.enable_reproduction = false;
        for a in &mut world_high.agents {
            a.internal_state[0] = 0.9;
        }

        let mut world_low = make_world(10, 100.0);
        world_low.config.enable_homeostasis = false;
        world_low.config.homeostasis_decay_rate = 0.0;
        world_low.config.enable_metabolism = false;
        world_low.config.enable_reproduction = false;
        for a in &mut world_low.agents {
            a.internal_state[0] = 0.1;
        }

        // Give both organisms some energy for repair
        world_high.organisms[0].metabolic_state.energy = 0.8;
        world_low.organisms[0].metabolic_state.energy = 0.8;

        for _ in 0..50 {
            world_high.step();
            world_low.step();
        }
        assert!(
            world_high.organisms[0].boundary_integrity > world_low.organisms[0].boundary_integrity,
            "organism with high internal_state[0] should have better boundary"
        );
    }

    #[test]
    fn disable_response_freezes_velocity() {
        let mut world = make_world(10, 100.0);
        world.config.enable_response = false;
        world.agents[0].velocity = [0.0, 0.0];
        world.step();
        assert_eq!(
            world.agents[0].velocity,
            [0.0, 0.0],
            "velocity should remain zero when response is disabled"
        );
    }

    #[test]
    fn disable_reproduction_prevents_births() {
        let mut world = make_world(10, 100.0);
        world.config.enable_reproduction = false;
        // Disable death mechanisms to ensure the organism survives
        world.config.enable_metabolism = false;
        world.config.enable_boundary_maintenance = false;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.config.death_energy_threshold = 0.0;
        world.organisms[0].metabolic_state.energy = 1.0;
        world.organisms[0].boundary_integrity = 1.0;
        let before = world.organism_count();
        for _ in 0..10 {
            world.step();
        }
        assert!(
            world.organisms[0].alive,
            "organism must survive for valid test"
        );
        assert_eq!(
            world.population_stats().total_births,
            0,
            "birth_count should be 0 when reproduction is disabled"
        );
        assert_eq!(world.organism_count(), before);
    }

    #[test]
    fn disable_evolution_copies_genome_exactly() {
        let mut world = make_world(10, 100.0);
        world.config.enable_evolution = false;
        // Disable death mechanisms so parent and child survive for inspection
        world.config.death_energy_threshold = 0.0;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.organisms[0].metabolic_state.energy = 1.0;
        world.organisms[0].boundary_integrity = 1.0;
        let parent_data = world.organisms[0].genome.data().to_vec();
        world.step();
        assert!(
            world.population_stats().total_births >= 1,
            "reproduction should still happen with evolution disabled"
        );
        // Find the child: it will be the last organism (pushed during maybe_reproduce)
        let child = world
            .organisms
            .iter()
            .find(|o| o.generation == 1)
            .expect("child organism with generation=1 should exist");
        let child_data = child.genome.data().to_vec();
        assert_eq!(
            parent_data, child_data,
            "child genome should be exact copy when evolution is disabled"
        );
    }

    #[test]
    fn enable_growth_default_is_true() {
        let config = SimConfig::default();
        assert!(config.enable_growth, "enable_growth should default to true");
    }

    #[test]
    fn organism_matures_over_time() {
        let mut world = make_world(10, 100.0);
        world.config.enable_growth = true;
        world.config.growth_maturation_steps = 100;
        world.config.enable_metabolism = false;
        world.config.enable_boundary_maintenance = false;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.config.death_energy_threshold = 0.0;
        world.config.enable_reproduction = false;
        // Bootstrap organisms start at maturity 1.0
        assert!((world.organisms[0].maturity - 1.0).abs() < f32::EPSILON);

        // Simulate a child by setting maturity to 0.0
        world.organisms[0].maturity = 0.0;
        for _ in 0..100 {
            world.step();
        }
        assert!(
            (world.organisms[0].maturity - 1.0).abs() < 0.02,
            "organism should reach maturity ~1.0 after growth_maturation_steps"
        );
    }

    #[test]
    fn immature_organism_has_reduced_metabolic_efficiency() {
        // Maturity always modulates metabolic efficiency regardless of enable_growth
        let mut world_immature = make_world(10, 100.0);
        world_immature.config.growth_immature_metabolic_efficiency = 0.3;
        world_immature.config.enable_boundary_maintenance = false;
        world_immature.config.death_boundary_threshold = 0.0;
        world_immature.config.boundary_collapse_threshold = 0.0;
        world_immature.config.death_energy_threshold = 0.0;
        world_immature.config.enable_reproduction = false;
        world_immature.organisms[0].maturity = 0.0;
        world_immature.organisms[0].metabolic_state.energy = 0.5;

        let mut world_mature = make_world(10, 100.0);
        world_mature.config.growth_immature_metabolic_efficiency = 0.3;
        world_mature.config.enable_boundary_maintenance = false;
        world_mature.config.death_boundary_threshold = 0.0;
        world_mature.config.boundary_collapse_threshold = 0.0;
        world_mature.config.death_energy_threshold = 0.0;
        world_mature.config.enable_reproduction = false;
        world_mature.organisms[0].maturity = 1.0;
        world_mature.organisms[0].metabolic_state.energy = 0.5;

        for _ in 0..10 {
            world_immature.step();
            world_mature.step();
        }
        assert!(
            world_mature.organisms[0].metabolic_state.energy
                > world_immature.organisms[0].metabolic_state.energy,
            "mature organism should have higher energy than immature"
        );
    }

    #[test]
    fn growth_factor_preserves_energy_loss() {
        // When metabolism causes net energy loss, growth factor must NOT mask it.
        // With the old bug (.max(0.0) on energy delta), losses were silently discarded.
        let mut world = make_world(10, 100.0);
        world.config.growth_immature_metabolic_efficiency = 0.3;
        world.config.enable_boundary_maintenance = false;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.config.death_energy_threshold = 0.0;
        world.config.enable_reproduction = false;
        world.config.resource_regeneration_rate = 0.0;
        world.current_resource_rate = 0.0;
        world.organisms[0].maturity = 0.0; // fully immature

        // Deplete ALL resource sources: world grid, internal pool, and graph pool.
        // This forces metabolism's energy_loss_rate to dominate → net energy decrease.
        let w = world.resource_field.width();
        let h = world.resource_field.height();
        let cs = world.resource_field.cell_size();
        for y in 0..h {
            for x in 0..w {
                world.resource_field.set(x as f64 * cs, y as f64 * cs, 0.0);
            }
        }
        world.organisms[0].metabolic_state.resource = 0.0;
        world.organisms[0].metabolic_state.graph_pool.clear();

        let initial_energy = world.organisms[0].metabolic_state.energy;
        for _ in 0..50 {
            world.step();
        }
        assert!(
            world.organisms[0].metabolic_state.energy < initial_energy,
            "energy should decrease when all resources are depleted, even for immature organisms \
             (got {} >= initial {})",
            world.organisms[0].metabolic_state.energy,
            initial_energy
        );
    }

    #[test]
    fn immature_organism_cannot_reproduce() {
        let mut world = make_world(10, 100.0);
        world.config.enable_metabolism = false;
        world.config.enable_boundary_maintenance = false;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.config.death_energy_threshold = 0.0;
        world.organisms[0].maturity = 0.5; // not fully mature
        world.organisms[0].metabolic_state.energy = 1.0;
        world.organisms[0].boundary_integrity = 1.0;
        let before = world.organism_count();
        world.step();
        assert_eq!(
            world.organism_count(),
            before,
            "immature organism should not reproduce"
        );
    }

    #[test]
    fn growth_disabled_prevents_maturation() {
        let mut world = make_world(10, 100.0);
        world.config.enable_growth = false;
        world.config.growth_maturation_steps = 100;
        world.config.enable_metabolism = false;
        world.config.enable_boundary_maintenance = false;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.config.death_energy_threshold = 0.0;
        world.config.enable_reproduction = false;
        world.organisms[0].maturity = 0.0;
        for _ in 0..200 {
            world.step();
        }
        assert!(
            world.organisms[0].maturity < f32::EPSILON,
            "maturity should stay at 0.0 when growth is disabled"
        );
    }

    #[test]
    fn growth_reduces_boundary_repair_for_immature() {
        // Immature organisms should have lower boundary than mature after same steps
        let mut world_immature = make_world(10, 100.0);
        world_immature.config.enable_growth = true;
        world_immature.config.enable_metabolism = false;
        world_immature.config.death_energy_threshold = 0.0;
        world_immature.config.enable_reproduction = false;
        world_immature.organisms[0].maturity = 0.0;
        world_immature.organisms[0].boundary_integrity = 0.8;
        world_immature.organisms[0].metabolic_state.energy = 0.5;

        let mut world_mature = make_world(10, 100.0);
        world_mature.config.enable_growth = true;
        world_mature.config.enable_metabolism = false;
        world_mature.config.death_energy_threshold = 0.0;
        world_mature.config.enable_reproduction = false;
        world_mature.organisms[0].maturity = 1.0;
        world_mature.organisms[0].boundary_integrity = 0.8;
        world_mature.organisms[0].metabolic_state.energy = 0.5;

        for _ in 0..50 {
            world_immature.step();
            world_mature.step();
        }
        assert!(
            world_mature.organisms[0].boundary_integrity
                > world_immature.organisms[0].boundary_integrity,
            "mature organism should have higher boundary integrity: mature={}, immature={}",
            world_mature.organisms[0].boundary_integrity,
            world_immature.organisms[0].boundary_integrity
        );
    }

    #[test]
    fn growth_reduces_sensing_for_immature() {
        // Immature organisms should detect fewer neighbors due to reduced sensing radius
        let mut world = make_world(10, 100.0);
        world.config.enable_growth = true;
        world.organisms[0].maturity = 0.0;
        // After step, neighbor counts should be reduced for immature organisms
        // This is hard to test directly, but we can verify the dev program decodes correctly
        let dp = &world.organisms[0].developmental_program;
        let (_, sensing, _) = dp.stage_factors(0.0);
        assert!(
            sensing < 1.0,
            "juvenile sensing factor should be < 1.0: {sensing}"
        );
    }

    #[test]
    fn growth_ablation_degrades_boundary_independently_of_reproduction() {
        // With reproduction disabled, growth-on should still produce higher boundary than growth-off
        let mut world_growth_on = make_world(10, 100.0);
        world_growth_on.config.enable_growth = true;
        world_growth_on.config.enable_reproduction = false;
        world_growth_on.config.enable_metabolism = false;
        world_growth_on.config.death_energy_threshold = 0.0;
        world_growth_on.organisms[0].maturity = 0.0;
        world_growth_on.organisms[0].metabolic_state.energy = 0.5;
        world_growth_on.organisms[0].boundary_integrity = 0.8;

        let mut world_growth_off = make_world(10, 100.0);
        world_growth_off.config.enable_growth = false;
        world_growth_off.config.enable_reproduction = false;
        world_growth_off.config.enable_metabolism = false;
        world_growth_off.config.death_energy_threshold = 0.0;
        world_growth_off.organisms[0].maturity = 0.0;
        world_growth_off.organisms[0].metabolic_state.energy = 0.5;
        world_growth_off.organisms[0].boundary_integrity = 0.8;

        for _ in 0..100 {
            world_growth_on.step();
            world_growth_off.step();
        }

        // Growth-on: organism matures, eventually gets full boundary repair
        // Growth-off: organism never matures, boundary repair factor stays reduced
        // (growth_off uses the old linear formula which with maturity=0 gives reduced efficiency)
        // The key test: growth-on should show DIFFERENT boundary than growth-off,
        // proving independent viability effect
        assert!(
            (world_growth_on.organisms[0].boundary_integrity
                - world_growth_off.organisms[0].boundary_integrity)
                .abs()
                > 0.01,
            "growth on/off should produce different boundary integrity: on={}, off={}",
            world_growth_on.organisms[0].boundary_integrity,
            world_growth_off.organisms[0].boundary_integrity
        );
    }

    #[test]
    fn genome_segment3_affects_maturation_rate() {
        let mut world_fast = make_world(10, 100.0);
        world_fast.config.enable_growth = true;
        world_fast.config.growth_maturation_steps = 200;
        world_fast.config.enable_metabolism = false;
        world_fast.config.enable_boundary_maintenance = false;
        world_fast.config.death_boundary_threshold = 0.0;
        world_fast.config.boundary_collapse_threshold = 0.0;
        world_fast.config.death_energy_threshold = 0.0;
        world_fast.config.enable_reproduction = false;
        // Set genome segment 3 g[0] = 1.0 → maturation_rate_modifier = 2^1 = 2.0
        world_fast.organisms[0]
            .genome
            .set_segment_data(3, &[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]);
        world_fast.organisms[0].developmental_program =
            DevelopmentalProgram::decode(world_fast.organisms[0].genome.segment_data(3));
        world_fast.organisms[0].maturity = 0.0;

        let mut world_slow = make_world(10, 100.0);
        world_slow.config.enable_growth = true;
        world_slow.config.growth_maturation_steps = 200;
        world_slow.config.enable_metabolism = false;
        world_slow.config.enable_boundary_maintenance = false;
        world_slow.config.death_boundary_threshold = 0.0;
        world_slow.config.boundary_collapse_threshold = 0.0;
        world_slow.config.death_energy_threshold = 0.0;
        world_slow.config.enable_reproduction = false;
        // Set genome segment 3 g[0] = -1.0 → maturation_rate_modifier = 2^-1 = 0.5
        world_slow.organisms[0]
            .genome
            .set_segment_data(3, &[-1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]);
        world_slow.organisms[0].developmental_program =
            DevelopmentalProgram::decode(world_slow.organisms[0].genome.segment_data(3));
        world_slow.organisms[0].maturity = 0.0;

        for _ in 0..100 {
            world_fast.step();
            world_slow.step();
        }
        assert!(
            world_fast.organisms[0].maturity > world_slow.organisms[0].maturity,
            "fast maturation genome should mature faster: fast={}, slow={}",
            world_fast.organisms[0].maturity,
            world_slow.organisms[0].maturity
        );
    }

    #[test]
    fn developmental_program_decoded_on_child_creation() {
        let mut world = make_world(10, 100.0);
        world.config.enable_metabolism = false;
        world.config.enable_boundary_maintenance = false;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.config.death_energy_threshold = 0.0;
        world.config.enable_evolution = false;
        world.organisms[0].metabolic_state.energy = 1.0;
        world.organisms[0].boundary_integrity = 1.0;
        world.organisms[0].maturity = 1.0;
        for _ in 0..10 {
            world.step();
        }
        if let Some(child) = world.organisms.iter().find(|o| o.generation == 1) {
            // Child should have a decoded developmental program
            assert!(
                child.developmental_program.maturation_rate_modifier > 0.0,
                "child should have decoded developmental program"
            );
            assert!(
                child.parent_stable_id.is_some(),
                "child should have parent_stable_id"
            );
        }
    }

    #[test]
    fn lineage_events_recorded_on_reproduction() {
        let mut world = make_world(10, 100.0);
        world.config.enable_metabolism = false;
        world.config.enable_boundary_maintenance = false;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.config.death_energy_threshold = 0.0;
        world.organisms[0].metabolic_state.energy = 1.0;
        world.organisms[0].boundary_integrity = 1.0;
        world.organisms[0].maturity = 1.0;
        let summary = world.run_experiment(20, 20);
        if summary.total_reproduction_events > 0 {
            assert!(
                !summary.lineage_events.is_empty(),
                "lineage events should be recorded when reproduction occurs"
            );
            let event = &summary.lineage_events[0];
            assert!(event.generation > 0);
        }
    }

    #[test]
    fn maturity_mean_and_spatial_cohesion_in_metrics() {
        let mut world = make_world(10, 100.0);
        world.config.enable_metabolism = false;
        world.config.enable_boundary_maintenance = false;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.config.death_energy_threshold = 0.0;
        world.config.enable_reproduction = false;
        let summary = world.run_experiment(10, 10);
        let last = summary.samples.last().unwrap();
        // Bootstrap organisms start at maturity 1.0
        assert!(
            (last.maturity_mean - 1.0).abs() < f32::EPSILON,
            "bootstrap organisms should have maturity_mean=1.0: {}",
            last.maturity_mean
        );
        assert!(
            last.spatial_cohesion_mean >= 0.0,
            "spatial_cohesion_mean should be non-negative"
        );
    }

    fn make_graph_world(num_agents: usize, world_size: f64) -> World {
        let agents: Vec<Agent> = (0..num_agents)
            .map(|i| Agent::new(i as u32, 0, [50.0, 50.0]))
            .collect();
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.1f32, NeuralNet::WEIGHT_COUNT));
        let config = SimConfig {
            world_size,
            num_organisms: 1,
            agents_per_organism: num_agents,
            metabolism_mode: MetabolismMode::Graph,
            ..SimConfig::default()
        };
        World::new(agents, vec![nn], config)
    }

    #[test]
    fn graph_mode_organisms_have_individual_engines() {
        let agents: Vec<Agent> = (0..20)
            .map(|i| Agent::new(i as u32, i as u16 / 10, [50.0, 50.0]))
            .collect();
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.1f32, NeuralNet::WEIGHT_COUNT));
        let config = SimConfig {
            world_size: 100.0,
            num_organisms: 2,
            agents_per_organism: 10,
            metabolism_mode: MetabolismMode::Graph,
            ..SimConfig::default()
        };
        let world = World::new(agents, vec![nn.clone(), nn], config);
        assert!(world.organisms[0].metabolism_engine.is_some());
        assert!(world.organisms[1].metabolism_engine.is_some());
        // Different organisms should have different metabolic segments (seeded differently)
        let seg0 = world.organisms[0].genome.segment_data(1);
        let seg1 = world.organisms[1].genome.segment_data(1);
        assert_ne!(
            seg0, seg1,
            "different organisms should have different metabolic segments"
        );
    }

    #[test]
    fn toy_mode_organisms_use_shared_engine() {
        let world = make_world(10, 100.0);
        assert!(world.organisms[0].metabolism_engine.is_none());
    }

    #[test]
    fn child_inherits_then_redecodes_metabolism() {
        let mut world = make_graph_world(10, 100.0);
        world.config.death_energy_threshold = 0.0;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.organisms[0].metabolic_state.energy = 1.0;
        world.organisms[0].boundary_integrity = 1.0;
        world.step();
        assert!(
            world.population_stats().total_births >= 1,
            "reproduction must occur for this test to be valid"
        );
        let child = world
            .organisms
            .iter()
            .find(|o| o.generation == 1)
            .expect("child should exist");
        assert!(
            child.metabolism_engine.is_some(),
            "child in Graph mode should have its own metabolism engine"
        );
    }

    #[test]
    fn graph_mode_mutation_changes_metabolic_topology() {
        let agents: Vec<Agent> = (0..10)
            .map(|i| Agent::new(i as u32, 0, [50.0, 50.0]))
            .collect();
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.1f32, NeuralNet::WEIGHT_COUNT));
        let config = SimConfig {
            world_size: 100.0,
            num_organisms: 1,
            agents_per_organism: 10,
            metabolism_mode: MetabolismMode::Graph,
            mutation_point_rate: 0.5, // aggressive mutation
            mutation_point_scale: 1.0,
            death_energy_threshold: 0.0,
            death_boundary_threshold: 0.0,
            boundary_collapse_threshold: 0.0,
            ..SimConfig::default()
        };
        let mut world = World::new(agents, vec![nn], config);
        world.organisms[0].metabolic_state.energy = 1.0;
        world.organisms[0].boundary_integrity = 1.0;
        let parent_seg = world.organisms[0].genome.segment_data(1).to_vec();
        world.step();
        assert!(
            world.population_stats().total_births >= 1,
            "reproduction must occur for this test to be valid"
        );
        let child = world
            .organisms
            .iter()
            .find(|o| o.generation == 1)
            .expect("child should exist");
        let child_seg = child.genome.segment_data(1);
        assert_ne!(
            parent_seg, child_seg,
            "child metabolic segment should differ from parent with high mutation rate"
        );
    }

    // ── Extended metrics tests (Phase 1) ──

    #[test]
    fn step_metrics_new_fields_are_populated() {
        let mut world = make_world(10, 100.0);
        let summary = world.run_experiment(10, 5);
        let sample = summary.samples.last().expect("should have samples");
        // SD fields should be non-negative
        assert!(sample.energy_std >= 0.0);
        assert!(sample.waste_std >= 0.0);
        assert!(sample.boundary_std >= 0.0);
        // mean_age should be non-negative
        assert!(sample.mean_age >= 0.0);
        // internal_state_mean values should be in [0, 1]
        for &v in &sample.internal_state_mean {
            assert!(
                (0.0..=1.0).contains(&v),
                "internal_state_mean out of range: {v}"
            );
        }
        // internal_state_std should be non-negative
        for &v in &sample.internal_state_std {
            assert!(v >= 0.0, "internal_state_std negative: {v}");
        }
        // genome_diversity should be non-negative
        assert!(
            sample.genome_diversity >= 0.0,
            "genome_diversity should be non-negative"
        );
    }

    #[test]
    fn lifespans_recorded_on_organism_death() {
        let mut world = make_world(4, 100.0);
        world.config.enable_metabolism = true;
        world.config.death_energy_threshold = 1.0; // force death
        world.resource_field_mut().set(50.0, 50.0, 0.0);
        let summary = world.run_experiment(5, 5);
        // Organism should die, producing at least one lifespan entry
        assert!(
            !summary.lifespans.is_empty(),
            "lifespans should be recorded when organisms die"
        );
    }

    #[test]
    fn run_summary_total_reproduction_events() {
        let mut world = make_world(10, 100.0);
        world.organisms[0].metabolic_state.energy = 1.0;
        world.organisms[0].boundary_integrity = 1.0;
        let summary = world.run_experiment(5, 5);
        // With high energy, reproduction should happen
        assert!(
            summary.total_reproduction_events >= 1,
            "total_reproduction_events should count births"
        );
    }

    #[test]
    fn genome_diversity_is_bounded() {
        let mut world = make_world(10, 100.0);
        world.organisms[0].metabolic_state.energy = 1.0;
        world.organisms[0].boundary_integrity = 1.0;
        // Run enough steps for reproduction to occur
        let summary = world.run_experiment(20, 10);
        for sample in &summary.samples {
            assert!(
                sample.genome_diversity >= 0.0,
                "genome_diversity must be non-negative"
            );
            assert!(
                sample.genome_diversity.is_finite(),
                "genome_diversity must be finite"
            );
        }
    }

    #[test]
    fn genome_diversity_zero_for_single_organism() {
        let mut world = make_world(10, 100.0);
        world.config.enable_reproduction = false;
        world.config.enable_metabolism = false;
        world.config.enable_boundary_maintenance = false;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.config.death_energy_threshold = 0.0;
        let summary = world.run_experiment(5, 5);
        let sample = summary.samples.last().unwrap();
        assert!(
            sample.genome_diversity < f32::EPSILON,
            "genome_diversity should be 0 with only one organism"
        );
    }

    // ── Environment shift tests (Phase 4) ──

    #[test]
    fn environment_shift_zero_produces_no_change() {
        let mut world = make_world(10, 100.0);
        world.config.environment_shift_step = 0; // disabled
        world.config.environment_shift_resource_rate = 0.0;
        let original_rate = world.current_resource_rate;
        for _ in 0..50 {
            world.step();
        }
        assert!(
            (world.current_resource_rate - original_rate).abs() < f32::EPSILON,
            "resource rate should not change when shift_step=0"
        );
    }

    #[test]
    fn environment_shift_changes_resource_rate_at_step() {
        let mut world = make_world(10, 100.0);
        world.config.environment_shift_step = 5;
        world.config.environment_shift_resource_rate = 0.005;
        world.config.resource_regeneration_rate = 0.01;
        world.current_resource_rate = 0.01;
        for _ in 0..4 {
            world.step();
        }
        assert!(
            (world.current_resource_rate - 0.01).abs() < f32::EPSILON,
            "rate should be unchanged before shift step"
        );
        world.step(); // step 5
        assert!(
            (world.current_resource_rate - 0.005).abs() < f32::EPSILON,
            "rate should change at shift step"
        );
    }

    // ── Graded ablation tests ──

    #[test]
    fn metabolism_efficiency_multiplier_defaults_to_one() {
        let cfg = SimConfig::default();
        assert!(
            (cfg.metabolism_efficiency_multiplier - 1.0).abs() < f32::EPSILON,
            "metabolism_efficiency_multiplier should default to 1.0"
        );
    }

    #[test]
    fn metabolism_efficiency_half_halves_metabolic_gain() {
        // Two identical worlds: one with multiplier=1.0, one with 0.5
        let mut world_full = make_world(10, 100.0);
        world_full.config.enable_boundary_maintenance = false;
        world_full.config.death_boundary_threshold = 0.0;
        world_full.config.boundary_collapse_threshold = 0.0;
        world_full.config.metabolism_efficiency_multiplier = 1.0;

        let mut world_half = make_world(10, 100.0);
        world_half.config.enable_boundary_maintenance = false;
        world_half.config.death_boundary_threshold = 0.0;
        world_half.config.boundary_collapse_threshold = 0.0;
        world_half.config.metabolism_efficiency_multiplier = 0.5;

        for _ in 0..100 {
            world_full.step();
            world_half.step();
        }
        let e_full = world_full.metabolic_state(0).energy;
        let e_half = world_half.metabolic_state(0).energy;
        assert!(
            e_half < e_full,
            "half-efficiency ({e_half}) should produce less energy than full ({e_full})"
        );
    }

    #[test]
    fn metabolism_efficiency_zero_produces_zero_metabolic_gain() {
        let mut world = make_world(10, 100.0);
        world.config.enable_boundary_maintenance = false;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.config.metabolism_efficiency_multiplier = 0.0;
        let initial_energy = world.metabolic_state(0).energy;

        for _ in 0..50 {
            world.step();
        }
        let final_energy = world.metabolic_state(0).energy;
        assert!(
            final_energy <= initial_energy,
            "zero-efficiency should produce no net energy gain \
             (initial={initial_energy}, final={final_energy})"
        );
    }

    #[test]
    fn metabolism_efficiency_one_matches_baseline() {
        // Multiplier=1.0 should be identical to a world without the field set
        let mut world_a = make_world(10, 100.0);
        world_a.config.enable_boundary_maintenance = false;
        world_a.config.death_boundary_threshold = 0.0;
        world_a.config.boundary_collapse_threshold = 0.0;
        world_a.config.metabolism_efficiency_multiplier = 1.0;

        let mut world_b = make_world(10, 100.0);
        world_b.config.enable_boundary_maintenance = false;
        world_b.config.death_boundary_threshold = 0.0;
        world_b.config.boundary_collapse_threshold = 0.0;
        // world_b uses default (1.0) from SimConfig::default()

        for _ in 0..100 {
            world_a.step();
            world_b.step();
        }
        let e_a = world_a.metabolic_state(0).energy;
        let e_b = world_b.metabolic_state(0).energy;
        assert!(
            (e_a - e_b).abs() < f32::EPSILON,
            "multiplier=1.0 ({e_a}) should match default ({e_b})"
        );
    }

    // ── Cyclic environment tests ──

    #[test]
    fn environment_cycle_period_zero_means_no_cycling() {
        let cfg = SimConfig::default();
        assert_eq!(
            cfg.environment_cycle_period, 0,
            "environment_cycle_period should default to 0 (no cycling)"
        );
        let mut world = make_world(10, 100.0);
        world.config.environment_cycle_period = 0;
        let original_rate = world.current_resource_rate;
        for _ in 0..200 {
            world.step();
        }
        assert!(
            (world.current_resource_rate - original_rate).abs() < f32::EPSILON,
            "resource rate should not change when cycle_period=0"
        );
    }

    #[test]
    fn environment_cycle_alternates_resource_rate() {
        let mut world = make_world(10, 100.0);
        world.config.environment_cycle_period = 100;
        world.config.resource_regeneration_rate = 0.01;
        world.config.environment_cycle_low_rate = 0.005;
        world.current_resource_rate = 0.01;

        // Steps 1-100 → phase 0 (high rate): step_index 1..100, (step/100)%2 = 0
        for _ in 0..99 {
            world.step();
        }
        assert!(
            (world.current_resource_rate - 0.01).abs() < f32::EPSILON,
            "phase 0 should use normal rate, got {}",
            world.current_resource_rate
        );

        // Step 100 → phase 1 (low rate): (100/100)%2 = 1
        world.step();
        assert!(
            (world.current_resource_rate - 0.005).abs() < f32::EPSILON,
            "phase 1 should use low rate, got {}",
            world.current_resource_rate
        );
    }

    #[test]
    fn environment_cycle_returns_to_high_rate() {
        let mut world = make_world(10, 100.0);
        world.config.environment_cycle_period = 100;
        world.config.resource_regeneration_rate = 0.01;
        world.config.environment_cycle_low_rate = 0.005;
        world.config.enable_metabolism = false;
        world.config.enable_boundary_maintenance = false;
        world.config.death_boundary_threshold = 0.0;
        world.config.boundary_collapse_threshold = 0.0;
        world.current_resource_rate = 0.01;

        // Run 200 steps to reach phase 2 (which is (200/100)%2=0 → high)
        for _ in 0..200 {
            world.step();
        }
        assert!(
            (world.current_resource_rate - 0.01).abs() < f32::EPSILON,
            "phase 2 should return to normal rate, got {}",
            world.current_resource_rate
        );
    }

    // ── Sham ablation tests ──

    #[test]
    fn enable_sham_process_defaults_to_false() {
        let cfg = SimConfig::default();
        assert!(
            !cfg.enable_sham_process,
            "enable_sham_process should default to false (opt-in)"
        );
    }

    #[test]
    fn sham_process_has_no_functional_effect() {
        // Compare sham-on vs sham-off: population outcomes should be identical
        // since sham computes distances but discards results
        let mut world_on = make_world(10, 100.0);
        world_on.config.enable_sham_process = true;
        world_on.config.enable_boundary_maintenance = false;
        world_on.config.death_boundary_threshold = 0.0;
        world_on.config.boundary_collapse_threshold = 0.0;

        let mut world_off = make_world(10, 100.0);
        world_off.config.enable_sham_process = false;
        world_off.config.enable_boundary_maintenance = false;
        world_off.config.death_boundary_threshold = 0.0;
        world_off.config.boundary_collapse_threshold = 0.0;

        for _ in 0..200 {
            world_on.step();
            world_off.step();
        }
        let energy_on = world_on.metabolic_state(0).energy;
        let energy_off = world_off.metabolic_state(0).energy;
        assert!(
            (energy_on - energy_off).abs() < f32::EPSILON,
            "sham process should have no effect on energy (on={energy_on}, off={energy_off})"
        );

        let alive_on = world_on.organism_count();
        let alive_off = world_off.organism_count();
        assert_eq!(
            alive_on, alive_off,
            "sham process should have no effect on population"
        );
    }

    // ── Legacy config backward compatibility ──

    #[test]
    fn legacy_config_gets_new_field_defaults() {
        let legacy_json = r#"{
            "seed": 42,
            "world_size": 100.0,
            "num_organisms": 1,
            "agents_per_organism": 1
        }"#;
        let cfg: SimConfig = serde_json::from_str(legacy_json).expect("legacy config should parse");
        assert!(
            (cfg.metabolism_efficiency_multiplier - 1.0).abs() < f32::EPSILON,
            "metabolism_efficiency_multiplier should default to 1.0"
        );
        assert_eq!(cfg.environment_cycle_period, 0);
        assert!(
            (cfg.environment_cycle_low_rate - 0.005).abs() < f32::EPSILON,
            "environment_cycle_low_rate should default to 0.005"
        );
        assert!(!cfg.enable_sham_process);
    }

    #[test]
    fn environment_shift_and_cycle_are_mutually_exclusive() {
        let mut world = make_world(10, 100.0);
        world.config.environment_shift_step = 500;
        world.config.environment_cycle_period = 200;
        let result = world.set_config(world.config.clone());
        assert!(matches!(
            result,
            Err(WorldInitError::ConflictingEnvironmentFeatures)
        ));
    }
}
