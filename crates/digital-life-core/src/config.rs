use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MetabolismMode {
    #[default]
    Toy,
    Graph,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SimConfig {
    /// Deterministic seed for reproducible simulation runs.
    pub seed: u64,
    /// Width/height of the square toroidal world in world units.
    pub world_size: f64,
    /// Number of organisms in the world. Must match `nns.len()`.
    pub num_organisms: usize,
    /// Expected number of agents per organism.
    pub agents_per_organism: usize,
    /// Radius for local neighbor sensing.
    pub sensing_radius: f64,
    /// Maximum speed clamp for agent velocity.
    pub max_speed: f64,
    /// Simulation timestep (seconds in model time).
    pub dt: f64,
    /// Normalization factor for neighbor-count NN input channel.
    pub neighbor_norm: f64,
    /// Criterion-ablation toggle for metabolism updates.
    pub enable_metabolism: bool,
    /// Criterion-ablation toggle for boundary maintenance updates.
    pub enable_boundary_maintenance: bool,
    /// Minimum energy required for stable boundary maintenance.
    pub metabolic_viability_floor: f32,
    /// Baseline per-step boundary integrity decay rate.
    pub boundary_decay_base_rate: f32,
    /// Additional boundary decay scale from low energy and waste pressure.
    pub boundary_decay_energy_scale: f32,
    /// Selects metabolism engine behavior.
    pub metabolism_mode: MetabolismMode,
}

impl Default for SimConfig {
    fn default() -> Self {
        Self {
            seed: 42,
            world_size: 100.0,
            num_organisms: 50,
            agents_per_organism: 50,
            sensing_radius: 5.0,
            max_speed: 2.0,
            dt: 0.1,
            neighbor_norm: 50.0,
            enable_metabolism: true,
            enable_boundary_maintenance: true,
            metabolic_viability_floor: 0.2,
            boundary_decay_base_rate: 0.003,
            boundary_decay_energy_scale: 0.02,
            metabolism_mode: MetabolismMode::Toy,
        }
    }
}
