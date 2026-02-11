use crate::agent::Agent;
use crate::config::{MetabolismMode, SimConfig};
use crate::metabolism::{MetabolicState, MetabolismEngine};
use crate::nn::NeuralNet;
use crate::resource::ResourceField;
use crate::spatial;
use serde::{Deserialize, Serialize};
use std::f64::consts::PI;
use std::time::Instant;
use std::{error::Error, fmt};

#[derive(Clone, Debug)]
pub struct StepTimings {
    pub spatial_build_us: u64,
    pub nn_query_us: u64,
    pub state_update_us: u64,
    pub total_us: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StepMetrics {
    pub step: usize,
    pub energy_mean: f32,
    pub waste_mean: f32,
    pub boundary_mean: f32,
    pub alive_count: usize,
    pub resource_total: f32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RunSummary {
    pub steps: usize,
    pub sample_every: usize,
    pub final_alive_count: usize,
    pub samples: Vec<StepMetrics>,
}

pub struct World {
    pub agents: Vec<Agent>,
    pub nns: Vec<NeuralNet>, // one per organism
    // Keep config private to preserve constructor invariants.
    config: SimConfig,
    metabolic_states: Vec<MetabolicState>,
    metabolism: MetabolismEngine,
    resource_field: ResourceField,
    boundary_integrity: Vec<f32>,
    organism_alive: Vec<bool>,
    // Per-organism accumulators: [sin(x), cos(x), sin(y), cos(y)].
    org_toroidal_sums: Vec<[f64; 4]>,
    org_counts: Vec<usize>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum WorldInitError {
    InvalidWorldSize,
    InvalidDt,
    InvalidMaxSpeed,
    InvalidSensingRadius,
    InvalidNeighborNorm,
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

impl World {
    pub const MAX_WORLD_SIZE: f64 = 2048.0;
    pub const MAX_TOTAL_AGENTS: usize = 250_000;

    pub fn new(agents: Vec<Agent>, nns: Vec<NeuralNet>, config: SimConfig) -> Self {
        Self::try_new(agents, nns, config).unwrap_or_else(|e| panic!("{e}"))
    }

    pub fn try_new(
        agents: Vec<Agent>,
        nns: Vec<NeuralNet>,
        config: SimConfig,
    ) -> Result<Self, WorldInitError> {
        Self::validate_config_for_state(&agents, &nns, &config)?;
        let world_size = config.world_size;
        let num_organisms = nns.len();
        let metabolism = match config.metabolism_mode {
            MetabolismMode::Toy => MetabolismEngine::default(),
            MetabolismMode::Graph => {
                MetabolismEngine::Graph(crate::metabolism::GraphMetabolism::default())
            }
        };

        let metabolic_states = vec![MetabolicState::default(); num_organisms];
        Ok(Self {
            agents,
            nns,
            config,
            metabolic_states,
            metabolism,
            resource_field: ResourceField::new(world_size, 1.0, 1.0),
            boundary_integrity: vec![1.0; num_organisms],
            organism_alive: vec![true; num_organisms],
            org_toroidal_sums: vec![[0.0, 0.0, 0.0, 0.0]; num_organisms],
            org_counts: vec![0; num_organisms],
        })
    }

    fn toroidal_mean_coord(sum_sin: f64, sum_cos: f64, world_size: f64) -> f64 {
        if sum_sin == 0.0 && sum_cos == 0.0 {
            return 0.0;
        }
        let angle = sum_sin.atan2(sum_cos);
        (angle.rem_euclid(2.0 * PI) / (2.0 * PI)) * world_size
    }

    fn validate_config_for_state(
        agents: &[Agent],
        nns: &[NeuralNet],
        config: &SimConfig,
    ) -> Result<(), WorldInitError> {
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
        Ok(())
    }

    pub fn config(&self) -> &SimConfig {
        &self.config
    }

    pub fn set_config(&mut self, config: SimConfig) -> Result<(), WorldInitError> {
        let mode_changed = self.config.metabolism_mode != config.metabolism_mode;
        Self::validate_config_for_state(&self.agents, &self.nns, &config)?;
        if (self.config.world_size - config.world_size).abs() > f64::EPSILON {
            self.resource_field = ResourceField::new(config.world_size, 1.0, 1.0);
        }
        self.config = config;
        if mode_changed {
            self.metabolism = match self.config.metabolism_mode {
                MetabolismMode::Toy => MetabolismEngine::default(),
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

    pub fn metabolic_state(&self, organism_id: usize) -> &MetabolicState {
        self.try_metabolic_state(organism_id)
            .expect("organism_id out of range for metabolic_state")
    }

    pub fn try_metabolic_state(&self, organism_id: usize) -> Option<&MetabolicState> {
        self.metabolic_states.get(organism_id)
    }

    fn alive_count(&self) -> usize {
        self.organism_alive.iter().filter(|alive| **alive).count()
    }

    fn collect_step_metrics(&self, step: usize) -> StepMetrics {
        let orgs = self.metabolic_states.len().max(1) as f32;
        let energy_mean = self.metabolic_states.iter().map(|s| s.energy).sum::<f32>() / orgs;
        let waste_mean = self.metabolic_states.iter().map(|s| s.waste).sum::<f32>() / orgs;
        let boundary_mean = self.boundary_integrity.iter().sum::<f32>() / orgs;
        let resource_total = self.resource_field.data().iter().copied().sum::<f32>();
        StepMetrics {
            step,
            energy_mean,
            waste_mean,
            boundary_mean,
            alive_count: self.alive_count(),
            resource_total,
        }
    }

    pub fn run_experiment(&mut self, steps: usize, sample_every: usize) -> RunSummary {
        let interval = sample_every.max(1);
        let mut samples = Vec::new();
        for step in 1..=steps {
            self.step();
            if step % interval == 0 || step == steps {
                samples.push(self.collect_step_metrics(step));
            }
        }
        RunSummary {
            steps,
            sample_every: interval,
            final_alive_count: self.alive_count(),
            samples,
        }
    }

    pub fn step(&mut self) -> StepTimings {
        let total_start = Instant::now();

        // 1. Build spatial index
        let t0 = Instant::now();
        let tree = spatial::build_index(&self.agents);
        let spatial_build_us = t0.elapsed().as_micros() as u64;

        // 2. NN forward pass for each agent
        let t1 = Instant::now();
        let mut deltas: Vec<[f32; 4]> = Vec::with_capacity(self.agents.len());
        for agent in &self.agents {
            if !self.organism_alive[agent.organism_id as usize] {
                deltas.push([0.0; 4]);
                continue;
            }
            let neighbor_count = spatial::count_neighbors(
                &tree,
                agent.position,
                self.config.sensing_radius,
                agent.id,
                self.config.world_size,
            );

            // Build NN input: position(2) + velocity(2) + internal_state(3) + neighbor_count(1)
            // internal_state[2] is a constant bias channel (read but not written by NN)
            // internal_state[3] is reserved for future criteria
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

            let nn = &self.nns[agent.organism_id as usize];
            deltas.push(nn.forward(&input));
        }
        let nn_query_us = t1.elapsed().as_micros() as u64;

        // 3. Apply updates
        let t2 = Instant::now();
        for (agent, delta) in self.agents.iter_mut().zip(deltas.iter()) {
            if !self.organism_alive[agent.organism_id as usize] {
                agent.velocity = [0.0, 0.0];
                continue;
            }
            // Velocity update
            agent.velocity[0] += delta[0] as f64 * self.config.dt;
            agent.velocity[1] += delta[1] as f64 * self.config.dt;

            // Clamp speed
            let speed_sq =
                agent.velocity[0] * agent.velocity[0] + agent.velocity[1] * agent.velocity[1];
            if speed_sq > self.config.max_speed * self.config.max_speed {
                let scale = self.config.max_speed / speed_sq.sqrt();
                agent.velocity[0] *= scale;
                agent.velocity[1] *= scale;
            }

            // Position update with toroidal wrapping
            agent.position[0] = (agent.position[0] + agent.velocity[0] * self.config.dt)
                .rem_euclid(self.config.world_size);
            agent.position[1] = (agent.position[1] + agent.velocity[1] * self.config.dt)
                .rem_euclid(self.config.world_size);

            // Internal state update (clamped to [0, 1])
            agent.internal_state[0] =
                (agent.internal_state[0] + delta[2] * self.config.dt as f32).clamp(0.0, 1.0);
            agent.internal_state[1] =
                (agent.internal_state[1] + delta[3] * self.config.dt as f32).clamp(0.0, 1.0);
        }

        if self.config.enable_boundary_maintenance {
            let dt = self.config.dt as f32;
            for org_id in 0..self.metabolic_states.len() {
                if !self.organism_alive[org_id] {
                    self.boundary_integrity[org_id] = 0.0;
                    continue;
                }
                let state = &self.metabolic_states[org_id];
                let energy_deficit =
                    (self.config.metabolic_viability_floor - state.energy).max(0.0);
                let decay = self.config.boundary_decay_base_rate
                    + self.config.boundary_decay_energy_scale
                        * (energy_deficit + state.waste * 0.5);
                let repair = (state.energy - state.waste * 0.2).max(0.0) * 0.01;
                self.boundary_integrity[org_id] =
                    (self.boundary_integrity[org_id] - decay * dt + repair * dt).clamp(0.0, 1.0);
                if self.boundary_integrity[org_id] <= 0.05 {
                    self.organism_alive[org_id] = false;
                    self.boundary_integrity[org_id] = 0.0;
                }
            }
            for agent in &mut self.agents {
                let boundary = self.boundary_integrity[agent.organism_id as usize];
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
                let theta_x = agent.position[0] * tau_over_world;
                let theta_y = agent.position[1] * tau_over_world;
                self.org_toroidal_sums[idx][0] += theta_x.sin();
                self.org_toroidal_sums[idx][1] += theta_x.cos();
                self.org_toroidal_sums[idx][2] += theta_y.sin();
                self.org_toroidal_sums[idx][3] += theta_y.cos();
                self.org_counts[idx] += 1;
            }

            for (org_id, state) in self.metabolic_states.iter_mut().enumerate() {
                if !self.organism_alive[org_id] {
                    continue;
                }
                let center = if self.org_counts[org_id] > 0 {
                    [
                        Self::toroidal_mean_coord(
                            self.org_toroidal_sums[org_id][0],
                            self.org_toroidal_sums[org_id][1],
                            world_size,
                        ),
                        Self::toroidal_mean_coord(
                            self.org_toroidal_sums[org_id][2],
                            self.org_toroidal_sums[org_id][3],
                            world_size,
                        ),
                    ]
                } else {
                    [0.0, 0.0]
                };
                let external = self.resource_field.get(center[0], center[1]);
                let flux = self.metabolism.step(state, external, self.config.dt as f32);
                if flux.consumed_external > 0.0 {
                    let _ = self
                        .resource_field
                        .take(center[0], center[1], flux.consumed_external);
                }
                if state.energy <= 0.0 && self.boundary_integrity[org_id] <= 0.1 {
                    self.organism_alive[org_id] = false;
                    self.boundary_integrity[org_id] = 0.0;
                }
            }
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
    use crate::config::{MetabolismMode, SimConfig};
    use crate::metabolism::MetabolismEngine;
    use crate::nn::NeuralNet;

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
        world.agents[0].velocity = [100.0, 100.0]; // will overshoot in one step
        world.step();
        let pos = world.agents[0].position;
        assert!(
            pos[0] >= 0.0 && pos[0] < 100.0,
            "x={} out of bounds",
            pos[0]
        );
        assert!(
            pos[1] >= 0.0 && pos[1] < 100.0,
            "y={} out of bounds",
            pos[1]
        );
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
        let agents = vec![Agent::new(0, 5, [0.0, 0.0])]; // organism_id=5, but only 1 NN
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
    #[should_panic(expected = "num_organisms")]
    fn new_panics_on_num_organisms_mismatch() {
        let agents = vec![Agent::new(0, 0, [0.0, 0.0])];
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
        let mut cfg = make_config(100.0, 0.1);
        cfg.num_organisms = 2;
        World::new(agents, vec![nn], cfg);
    }

    #[test]
    fn try_new_returns_structured_error() {
        let agents = vec![Agent::new(0, 0, [0.0, 0.0])];
        let nn = NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
        let mut cfg = make_config(100.0, 0.1);
        cfg.num_organisms = 2;
        match World::try_new(agents, vec![nn], cfg) {
            Err(WorldInitError::NumOrganismsMismatch {
                expected: 2,
                actual: 1,
            }) => {}
            Err(other) => panic!("unexpected error: {other}"),
            Ok(_) => panic!("expected try_new to fail for mismatched organism count"),
        }
    }

    #[test]
    fn internal_state_stays_clamped() {
        let mut world = make_world(1, 100.0);
        // Run many steps — state should remain in [0, 1]
        for _ in 0..100 {
            world.step();
        }
        for &s in &world.agents[0].internal_state {
            assert!(
                (0.0..=1.0).contains(&s),
                "internal_state {s} out of [0,1] range"
            );
        }
    }

    #[test]
    fn step_respects_config_dt_for_position_update() {
        let mut world = make_world(1, 100.0);
        world.agents[0].position = [50.0, 50.0];
        world.agents[0].velocity = [1.0, 0.0];
        world.nns[0] =
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
        for _ in 0..1000 {
            world.step();
        }
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
        match World::try_new(agents, vec![nn], cfg) {
            Err(WorldInitError::AgentCountMismatch {
                expected: 2,
                actual: 1,
            }) => {}
            Err(other) => panic!("unexpected error: {other}"),
            Ok(_) => panic!("expected try_new to fail for agent count mismatch"),
        }
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
    fn metabolism_consumes_world_resource_field() {
        let mut world = make_world(1, 100.0);
        world.agents[0].position = [10.0, 10.0];
        let before = world.resource_field().get(10.0, 10.0);
        world.step();
        let after = world.resource_field().get(10.0, 10.0);
        assert!(
            after <= before,
            "resource field should be consumed by metabolism"
        );
    }

    #[test]
    fn toroidal_center_uses_wrapped_mean_for_resource_sampling() {
        let mut world = make_world(2, 100.0);
        // Cluster crosses boundary around x=0/100; mean should remain near edge, not center.
        world.agents[0].position = [0.1, 50.0];
        world.agents[1].position = [99.9, 50.0];
        world.resource_field.set(0.0, 50.0, 2.0);
        world.resource_field.set(50.0, 50.0, 0.0);
        world.step();
        let edge_resource = world.resource_field().get(0.0, 50.0);
        let center_resource = world.resource_field().get(50.0, 50.0);
        assert!(edge_resource < 2.0, "edge resource should be consumed");
        assert!(
            (center_resource - 0.0).abs() < f32::EPSILON,
            "center resource should remain unchanged"
        );
    }

    #[test]
    fn run_experiment_produces_non_empty_summary() {
        let mut world = make_world(10, 100.0);
        let summary = world.run_experiment(50, 10);
        assert_eq!(summary.steps, 50);
        assert!(!summary.samples.is_empty());
        assert!(summary.final_alive_count <= world.config().num_organisms);
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
        low.metabolic_states[0].energy = 0.0;
        high.metabolic_states[0].energy = 1.0;
        low.metabolic_states[0].waste = 0.8;
        high.metabolic_states[0].waste = 0.0;

        low.step();
        high.step();

        assert!(
            low.boundary_integrity[0] < high.boundary_integrity[0],
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
}
