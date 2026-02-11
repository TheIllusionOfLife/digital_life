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
    /// Minimum energy required before an organism can reproduce.
    pub reproduction_min_energy: f32,
    /// Minimum boundary integrity required before an organism can reproduce.
    pub reproduction_min_boundary: f32,
    /// Energy deducted from parent during reproduction and seeded into child.
    pub reproduction_energy_cost: f32,
    /// Minimum number of agents assigned to a newly reproduced child organism.
    pub reproduction_child_min_agents: usize,
    /// Maximum radius used when spawning child agents around the parent center.
    pub reproduction_spawn_radius: f64,
    /// Neighbor-density threshold where crowding damage starts.
    pub crowding_neighbor_threshold: f32,
    /// Per-step boundary decay scale induced by crowding.
    pub crowding_boundary_decay: f32,
    /// Maximum age in simulation steps before forced organism death.
    pub max_organism_age_steps: usize,
    /// Step interval used for pruning dead entities.
    pub compaction_interval_steps: usize,
    /// Per-gene point mutation probability.
    pub mutation_point_rate: f32,
    /// Magnitude bound for additive point mutation deltas.
    pub mutation_point_scale: f32,
    /// Per-gene reset-to-zero mutation probability.
    pub mutation_reset_rate: f32,
    /// Per-gene multiplicative scale mutation probability.
    pub mutation_scale_rate: f32,
    /// Minimum multiplicative factor used by scale mutation.
    pub mutation_scale_min: f32,
    /// Maximum multiplicative factor used by scale mutation.
    pub mutation_scale_max: f32,
    /// Absolute clamp used for mutated genome values.
    pub mutation_value_limit: f32,
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
            reproduction_min_energy: 0.85,
            reproduction_min_boundary: 0.70,
            reproduction_energy_cost: 0.30,
            reproduction_child_min_agents: 4,
            reproduction_spawn_radius: 1.0,
            crowding_neighbor_threshold: 8.0,
            crowding_boundary_decay: 0.0015,
            max_organism_age_steps: 20_000,
            compaction_interval_steps: 64,
            mutation_point_rate: 0.02,
            mutation_point_scale: 0.15,
            mutation_reset_rate: 0.002,
            mutation_scale_rate: 0.002,
            mutation_scale_min: 0.8,
            mutation_scale_max: 1.2,
            mutation_value_limit: 2.0,
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
        assert!(cfg.reproduction_min_energy > 0.0);
        assert!(cfg.max_organism_age_steps > 0);
        assert!(cfg.compaction_interval_steps > 0);
        assert!(cfg.mutation_value_limit > 0.0);
    }
}
