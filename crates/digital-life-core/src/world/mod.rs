pub mod lifecycle;
pub mod metrics;
#[cfg(test)]
mod tests;

pub use metrics::*;

use crate::agent::Agent;
use crate::config::{MetabolismMode, SimConfig, SimConfigError};
use crate::genome::{Genome, MutationRates};
use crate::metabolism::{MetabolicState, MetabolismEngine};
use crate::nn::NeuralNet;
use crate::organism::{DevelopmentalProgram, OrganismRuntime};
use crate::resource::ResourceField;
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha12Rng;
use std::f64::consts::PI;
use std::{error::Error, fmt};

/// Decode a genome's metabolic segment into a per-organism `MetabolismEngine`.
///
/// Returns `Some(engine)` in Graph mode, `None` in Toy/Counter mode (uses shared engine).
pub(crate) fn decode_organism_metabolism(
    genome: &Genome,
    mode: MetabolismMode,
) -> Option<MetabolismEngine> {
    match mode {
        MetabolismMode::Graph => {
            let gm = crate::metabolism::decode_graph_metabolism(genome.segment_data(1));
            Some(MetabolismEngine::Graph(gm))
        }
        MetabolismMode::Toy | MetabolismMode::Counter => None,
    }
}

pub struct World {
    pub agents: Vec<Agent>,
    pub(crate) organisms: Vec<OrganismRuntime>,
    pub(crate) config: SimConfig,
    pub(crate) metabolism: MetabolismEngine,
    pub(crate) resource_field: ResourceField,
    pub(crate) org_toroidal_sums: Vec<[f64; 4]>,
    pub(crate) org_counts: Vec<usize>,
    pub(crate) rng: ChaCha12Rng,
    pub(crate) next_agent_id: u32,
    pub(crate) step_index: usize,
    pub(crate) births_last_step: usize,
    pub(crate) deaths_last_step: usize,
    pub(crate) total_births: usize,
    pub(crate) total_deaths: usize,
    pub(crate) mutation_rates: MutationRates,
    pub(crate) next_organism_stable_id: u64,
    pub(crate) agent_id_exhaustions_last_step: usize,
    pub(crate) total_agent_id_exhaustions: usize,
    pub(crate) lifespans: Vec<usize>,
    pub(crate) lineage_events: Vec<LineageEvent>,
    /// Runtime resource regeneration rate, separate from config to avoid mutating
    /// config at runtime during environment shifts.
    pub(crate) current_resource_rate: f32,
}

#[derive(Debug, Clone, PartialEq)]
pub enum WorldInitError {
    Config(SimConfigError),
    AgentCountOverflow,
    TooManyAgents { max: usize, actual: usize },
    NumOrganismsMismatch { expected: usize, actual: usize },
    AgentCountMismatch { expected: usize, actual: usize },
    InvalidOrganismId,
}

impl fmt::Display for WorldInitError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            WorldInitError::Config(e) => write!(f, "{}", e),
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

impl From<SimConfigError> for WorldInitError {
    fn from(err: SimConfigError) -> Self {
        WorldInitError::Config(err)
    }
}

impl Error for WorldInitError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            WorldInitError::Config(e) => Some(e),
            _ => None,
        }
    }
}

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
        config.validate()?;
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
        if expected_agent_count > SimConfig::MAX_TOTAL_AGENTS {
            return Err(WorldInitError::TooManyAgents {
                max: SimConfig::MAX_TOTAL_AGENTS,
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

    pub fn config(&self) -> &SimConfig {
        &self.config
    }

    pub fn set_config(&mut self, config: SimConfig) -> Result<(), WorldInitError> {
        let mode_changed = self.config.metabolism_mode != config.metabolism_mode;
        config.validate()?;
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
            for org in &mut self.organisms {
                org.metabolism_engine =
                    decode_organism_metabolism(&org.genome, self.config.metabolism_mode);
            }
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

    pub fn live_flags(&self) -> Vec<bool> {
        self.organisms.iter().map(|o| o.alive).collect()
    }

    fn alive_count(&self) -> usize {
        self.organisms.iter().filter(|o| o.alive).count()
    }

    pub(crate) fn compute_organism_centers_with_counts(
        &self,
    ) -> (Vec<Option<[f64; 2]>>, Vec<usize>) {
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
        (centers, counts)
    }

    pub(crate) fn compute_organism_centers(&self) -> Vec<Option<[f64; 2]>> {
        self.compute_organism_centers_with_counts().0
    }

    pub(crate) fn toroidal_mean_coord(sum_sin: f64, sum_cos: f64, world_size: f64) -> f64 {
        if sum_sin == 0.0 && sum_cos == 0.0 {
            return 0.0;
        }
        let angle = sum_sin.atan2(sum_cos);
        (angle.rem_euclid(2.0 * PI) / (2.0 * PI)) * world_size
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
            schema_version: 1,
            steps,
            sample_every,
            final_alive_count: self.alive_count(),
            samples,
            lifespans: std::mem::take(&mut self.lifespans),
            total_reproduction_events: self.total_births - births_before,
            lineage_events: std::mem::take(&mut self.lineage_events),
            organism_snapshots: Vec::new(),
        })
    }

    /// Run an experiment like `try_run_experiment`, but also collect per-organism
    /// snapshots at the specified steps.
    pub fn try_run_experiment_with_snapshots(
        &mut self,
        steps: usize,
        sample_every: usize,
        snapshot_steps: &[usize],
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
        let mut snapshots = Vec::with_capacity(snapshot_steps.len());

        for step in 1..=steps {
            self.step();
            if step % sample_every == 0 || step == steps {
                samples.push(self.collect_step_metrics(step));
            }
            if snapshot_steps.contains(&step) {
                snapshots.push(self.collect_organism_snapshots(step));
            }
        }
        Ok(RunSummary {
            schema_version: 1,
            steps,
            sample_every,
            final_alive_count: self.alive_count(),
            samples,
            lifespans: std::mem::take(&mut self.lifespans),
            total_reproduction_events: self.total_births - births_before,
            lineage_events: std::mem::take(&mut self.lineage_events),
            organism_snapshots: snapshots,
        })
    }
}
