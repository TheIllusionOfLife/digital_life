use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MetabolismMode {
    #[default]
    Toy,
    Graph,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
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
    /// Weight applied to waste when computing boundary maintenance pressure.
    pub boundary_waste_pressure_scale: f32,
    /// Additional waste penalty multiplier used in boundary repair effectiveness.
    pub boundary_repair_waste_penalty_scale: f32,
    /// Per-step boundary repair multiplier from available energy.
    pub boundary_repair_rate: f32,
    /// Boundary threshold below which the organism is considered collapsed.
    pub boundary_collapse_threshold: f32,
    /// Energy threshold used in terminal viability checks.
    pub death_energy_threshold: f32,
    /// Boundary threshold used in terminal viability checks.
    pub death_boundary_threshold: f32,
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
            boundary_waste_pressure_scale: 0.5,
            boundary_repair_waste_penalty_scale: 0.4,
            boundary_repair_rate: 0.01,
            boundary_collapse_threshold: 0.05,
            death_energy_threshold: 0.0,
            death_boundary_threshold: 0.1,
            metabolism_mode: MetabolismMode::Toy,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn legacy_config_json_deserializes_with_defaults() {
        let legacy_json = r#"{
            "seed": 42,
            "world_size": 100.0,
            "num_organisms": 1,
            "agents_per_organism": 1,
            "sensing_radius": 5.0,
            "max_speed": 2.0,
            "dt": 0.1,
            "neighbor_norm": 50.0,
            "enable_metabolism": true,
            "enable_boundary_maintenance": true
        }"#;
        let cfg: SimConfig = serde_json::from_str(legacy_json).expect("legacy config should parse");
        assert_eq!(cfg.metabolism_mode, MetabolismMode::Toy);
        assert!(cfg.boundary_decay_base_rate > 0.0);
    }
}
