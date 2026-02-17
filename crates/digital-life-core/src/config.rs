use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MetabolismMode {
    #[default]
    Toy,
    Graph,
    /// Minimal single-step metabolism for proxy control experiments.
    Counter,
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
    /// Criterion-ablation toggle for homeostasis (internal state regulation).
    pub enable_homeostasis: bool,
    /// Criterion-ablation toggle for response to stimuli (velocity from NN).
    pub enable_response: bool,
    /// Criterion-ablation toggle for reproduction.
    pub enable_reproduction: bool,
    /// Criterion-ablation toggle for evolution (genome mutation during reproduction).
    pub enable_evolution: bool,
    /// Criterion-ablation toggle for growth/development (placeholder until developmental program).
    pub enable_growth: bool,
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
    /// Per-step decay rate for internal state (homeostatic entropy).
    pub homeostasis_decay_rate: f32,
    /// Number of simulation steps for a child organism to reach full maturity.
    pub growth_maturation_steps: usize,
    /// Metabolic efficiency multiplier for fully immature organisms (maturity=0).
    pub growth_immature_metabolic_efficiency: f32,
    /// Per-step resource regeneration rate per cell.
    pub resource_regeneration_rate: f32,
    /// Step at which to apply environment shift (0 = no shift).
    pub environment_shift_step: usize,
    /// Resource regeneration rate to apply after the environment shift step.
    pub environment_shift_resource_rate: f32,
    /// Multiplier applied to metabolic energy gains (graded ablation).
    /// 1.0 = full efficiency, 0.0 = no metabolic gain.
    pub metabolism_efficiency_multiplier: f32,
    /// Period (in steps) for cyclic resource modulation (0 = no cycling).
    pub environment_cycle_period: usize,
    /// Resource regeneration rate during the low phase of cyclic modulation.
    pub environment_cycle_low_rate: f32,
    /// Toggle for sham (no-op) computational process control.
    pub enable_sham_process: bool,
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
            enable_homeostasis: true,
            enable_response: true,
            enable_reproduction: true,
            enable_evolution: true,
            enable_growth: true,
            metabolic_viability_floor: 0.2,
            boundary_decay_base_rate: 0.001,
            boundary_decay_energy_scale: 0.02,
            boundary_waste_pressure_scale: 0.5,
            boundary_repair_waste_penalty_scale: 0.4,
            boundary_repair_rate: 0.05,
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
            homeostasis_decay_rate: 0.01,
            growth_maturation_steps: 200,
            growth_immature_metabolic_efficiency: 0.3,
            resource_regeneration_rate: 0.01,
            environment_shift_step: 0,
            environment_shift_resource_rate: 0.01,
            metabolism_efficiency_multiplier: 1.0,
            environment_cycle_period: 0,
            environment_cycle_low_rate: 0.005,
            enable_sham_process: false,
        }
    }
}

macro_rules! define_sim_config_error {
    (
        $(
            $variant:ident $( { $($field:ident : $type:ty),* } )? => $fmt:literal $(, $arg:expr)*
        );* $(;)?
    ) => {
        #[derive(Debug, Clone, PartialEq)]
        pub enum SimConfigError {
            $(
                $variant $( { $($field : $type),* } )?,
            )*
        }

        impl std::fmt::Display for SimConfigError {
            fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
                match self {
                    $(
                        Self::$variant $( { $($field),* } )? => write!(f, $fmt $(, $arg)*),
                    )*
                }
            }
        }
    };
}

define_sim_config_error! {
    InvalidNumOrganisms => "num_organisms must be greater than 0";
    InvalidAgentsPerOrganism => "agents_per_organism must be greater than 0";
    AgentCountOverflow => "Total agent count overflow";
    TooManyAgents { max: usize, actual: usize } => "Too many agents: {} > max {}", actual, max;
    InvalidWorldSize => "world_size must be positive and finite";
    InvalidDt => "dt must be positive and finite";
    InvalidMaxSpeed => "max_speed must be positive and finite";
    InvalidSensingRadius => "sensing_radius must be non-negative and finite";
    InvalidNeighborNorm => "neighbor_norm must be positive and finite";
    InvalidMetabolicViabilityFloor => "metabolic_viability_floor must be finite and non-negative";
    InvalidBoundaryDecayBaseRate => "boundary_decay_base_rate must be finite and non-negative";
    InvalidBoundaryDecayEnergyScale => "boundary_decay_energy_scale must be finite and non-negative";
    InvalidBoundaryWastePressureScale => "boundary_waste_pressure_scale must be finite and non-negative";
    InvalidBoundaryRepairWastePenaltyScale => "boundary_repair_waste_penalty_scale must be finite and non-negative";
    InvalidBoundaryRepairRate => "boundary_repair_rate must be finite and non-negative";
    InvalidBoundaryCollapseThreshold => "boundary_collapse_threshold must be finite and within [0,1]";
    InvalidDeathEnergyThreshold => "death_energy_threshold must be finite and non-negative";
    InvalidDeathBoundaryThreshold => "death_boundary_threshold must be finite and within [0,1]";
    InvalidReproductionMinEnergy => "reproduction_min_energy must be finite and non-negative";
    InvalidReproductionMinBoundary => "reproduction_min_boundary must be finite and within [0,1]";
    InvalidReproductionEnergyCost => "reproduction_energy_cost must be finite and positive";
    InvalidReproductionEnergyBalance => "reproduction_min_energy must be greater than or equal to reproduction_energy_cost";
    InvalidReproductionChildMinAgents => "reproduction_child_min_agents must be positive";
    InvalidReproductionSpawnRadius => "reproduction_spawn_radius must be finite and non-negative";
    InvalidCrowdingNeighborThreshold => "crowding_neighbor_threshold must be finite and non-negative";
    InvalidCrowdingBoundaryDecay => "crowding_boundary_decay must be finite and non-negative";
    InvalidMaxOrganismAgeSteps => "max_organism_age_steps must be positive";
    InvalidCompactionIntervalSteps => "compaction_interval_steps must be positive";
    InvalidMutationPointRate => "mutation_point_rate must be finite and within [0,1]";
    InvalidMutationPointScale => "mutation_point_scale must be finite and non-negative";
    InvalidMutationResetRate => "mutation_reset_rate must be finite and within [0,1]";
    InvalidMutationScaleRate => "mutation_scale_rate must be finite and within [0,1]";
    InvalidMutationScaleBounds => "mutation_scale_min/mutation_scale_max must be finite, positive, and ordered";
    InvalidMutationValueLimit => "mutation_value_limit must be finite and positive";
    InvalidMutationProbabilityBudget => "mutation_point_rate + mutation_reset_rate + mutation_scale_rate must be <= 1.0";
    InvalidHomeostasisDecayRate => "homeostasis_decay_rate must be finite and non-negative";
    InvalidGrowthMaturationSteps => "growth_maturation_steps must be positive";
    InvalidGrowthImmatureMetabolicEfficiency => "growth_immature_metabolic_efficiency must be finite and within [0,1]";
    InvalidResourceRegenerationRate => "resource_regeneration_rate must be finite and non-negative";
    InvalidEnvironmentShiftResourceRate => "environment_shift_resource_rate must be finite and non-negative";
    InvalidMetabolismEfficiencyMultiplier => "metabolism_efficiency_multiplier must be finite and within [0,1]";
    InvalidEnvironmentCycleLowRate => "environment_cycle_low_rate must be finite and non-negative";
    ConflictingEnvironmentFeatures => "environment_shift_step and environment_cycle_period are mutually exclusive";
    WorldSizeTooLarge { max: f64, actual: f64 } => "world_size ({actual}) exceeds supported maximum ({max})";
}

impl std::error::Error for SimConfigError {}

impl SimConfig {
    pub const MAX_WORLD_SIZE: f64 = 2048.0;

    pub const MAX_TOTAL_AGENTS: usize = 250_000;

    pub fn validate(&self) -> Result<(), SimConfigError> {
        self.validate_agents()?;
        self.validate_world_and_physics()?;
        self.validate_metabolism()?;
        self.validate_boundary()?;
        self.validate_death()?;
        self.validate_reproduction()?;
        self.validate_crowding()?;
        self.validate_simulation_steps()?;
        self.validate_mutation()?;
        self.validate_homeostasis()?;
        self.validate_growth()?;
        self.validate_environment()?;
        Ok(())
    }

    fn validate_agents(&self) -> Result<(), SimConfigError> {
        if self.num_organisms == 0 {
            return Err(SimConfigError::InvalidNumOrganisms);
        }
        if self.agents_per_organism == 0 {
            return Err(SimConfigError::InvalidAgentsPerOrganism);
        }
        let total_agents = self
            .num_organisms
            .checked_mul(self.agents_per_organism)
            .ok_or(SimConfigError::AgentCountOverflow)?;
        if total_agents > Self::MAX_TOTAL_AGENTS {
            return Err(SimConfigError::TooManyAgents {
                max: Self::MAX_TOTAL_AGENTS,
                actual: total_agents,
            });
        }
        Ok(())
    }

    fn validate_world_and_physics(&self) -> Result<(), SimConfigError> {
        if !(self.world_size.is_finite() && self.world_size > 0.0) {
            return Err(SimConfigError::InvalidWorldSize);
        }
        if self.world_size > Self::MAX_WORLD_SIZE {
            return Err(SimConfigError::WorldSizeTooLarge {
                max: Self::MAX_WORLD_SIZE,
                actual: self.world_size,
            });
        }
        if !(self.dt.is_finite() && self.dt > 0.0) {
            return Err(SimConfigError::InvalidDt);
        }
        if !(self.max_speed.is_finite() && self.max_speed > 0.0) {
            return Err(SimConfigError::InvalidMaxSpeed);
        }
        if !(self.sensing_radius.is_finite() && self.sensing_radius >= 0.0) {
            return Err(SimConfigError::InvalidSensingRadius);
        }
        if !(self.neighbor_norm.is_finite() && self.neighbor_norm > 0.0) {
            return Err(SimConfigError::InvalidNeighborNorm);
        }
        Ok(())
    }

    fn validate_metabolism(&self) -> Result<(), SimConfigError> {
        if !(self.metabolic_viability_floor.is_finite() && self.metabolic_viability_floor >= 0.0) {
            return Err(SimConfigError::InvalidMetabolicViabilityFloor);
        }
        if !(self.metabolism_efficiency_multiplier.is_finite()
            && (0.0..=1.0).contains(&self.metabolism_efficiency_multiplier))
        {
            return Err(SimConfigError::InvalidMetabolismEfficiencyMultiplier);
        }
        Ok(())
    }

    fn validate_boundary(&self) -> Result<(), SimConfigError> {
        if !(self.boundary_decay_base_rate.is_finite() && self.boundary_decay_base_rate >= 0.0) {
            return Err(SimConfigError::InvalidBoundaryDecayBaseRate);
        }
        if !(self.boundary_decay_energy_scale.is_finite()
            && self.boundary_decay_energy_scale >= 0.0)
        {
            return Err(SimConfigError::InvalidBoundaryDecayEnergyScale);
        }
        if !(self.boundary_waste_pressure_scale.is_finite()
            && self.boundary_waste_pressure_scale >= 0.0)
        {
            return Err(SimConfigError::InvalidBoundaryWastePressureScale);
        }
        if !(self.boundary_repair_waste_penalty_scale.is_finite()
            && self.boundary_repair_waste_penalty_scale >= 0.0)
        {
            return Err(SimConfigError::InvalidBoundaryRepairWastePenaltyScale);
        }
        if !(self.boundary_repair_rate.is_finite() && self.boundary_repair_rate >= 0.0) {
            return Err(SimConfigError::InvalidBoundaryRepairRate);
        }
        if !(self.boundary_collapse_threshold.is_finite()
            && (0.0..=1.0).contains(&self.boundary_collapse_threshold))
        {
            return Err(SimConfigError::InvalidBoundaryCollapseThreshold);
        }
        Ok(())
    }

    fn validate_death(&self) -> Result<(), SimConfigError> {
        if !(self.death_energy_threshold.is_finite() && self.death_energy_threshold >= 0.0) {
            return Err(SimConfigError::InvalidDeathEnergyThreshold);
        }
        if !(self.death_boundary_threshold.is_finite()
            && (0.0..=1.0).contains(&self.death_boundary_threshold))
        {
            return Err(SimConfigError::InvalidDeathBoundaryThreshold);
        }
        Ok(())
    }

    fn validate_reproduction(&self) -> Result<(), SimConfigError> {
        if !(self.reproduction_min_energy.is_finite() && self.reproduction_min_energy >= 0.0) {
            return Err(SimConfigError::InvalidReproductionMinEnergy);
        }
        if !(self.reproduction_min_boundary.is_finite()
            && (0.0..=1.0).contains(&self.reproduction_min_boundary))
        {
            return Err(SimConfigError::InvalidReproductionMinBoundary);
        }
        if !(self.reproduction_energy_cost.is_finite() && self.reproduction_energy_cost > 0.0) {
            return Err(SimConfigError::InvalidReproductionEnergyCost);
        }
        if self.reproduction_min_energy < self.reproduction_energy_cost {
            return Err(SimConfigError::InvalidReproductionEnergyBalance);
        }
        if self.reproduction_child_min_agents == 0 {
            return Err(SimConfigError::InvalidReproductionChildMinAgents);
        }
        if !(self.reproduction_spawn_radius.is_finite() && self.reproduction_spawn_radius >= 0.0) {
            return Err(SimConfigError::InvalidReproductionSpawnRadius);
        }
        Ok(())
    }

    fn validate_crowding(&self) -> Result<(), SimConfigError> {
        if !(self.crowding_neighbor_threshold.is_finite()
            && self.crowding_neighbor_threshold >= 0.0)
        {
            return Err(SimConfigError::InvalidCrowdingNeighborThreshold);
        }
        if !(self.crowding_boundary_decay.is_finite() && self.crowding_boundary_decay >= 0.0) {
            return Err(SimConfigError::InvalidCrowdingBoundaryDecay);
        }
        Ok(())
    }

    fn validate_simulation_steps(&self) -> Result<(), SimConfigError> {
        if self.max_organism_age_steps == 0 {
            return Err(SimConfigError::InvalidMaxOrganismAgeSteps);
        }
        if self.compaction_interval_steps == 0 {
            return Err(SimConfigError::InvalidCompactionIntervalSteps);
        }
        Ok(())
    }

    fn validate_mutation(&self) -> Result<(), SimConfigError> {
        if !(self.mutation_point_rate.is_finite()
            && (0.0..=1.0).contains(&self.mutation_point_rate))
        {
            return Err(SimConfigError::InvalidMutationPointRate);
        }
        if !(self.mutation_point_scale.is_finite() && self.mutation_point_scale >= 0.0) {
            return Err(SimConfigError::InvalidMutationPointScale);
        }
        if !(self.mutation_reset_rate.is_finite()
            && (0.0..=1.0).contains(&self.mutation_reset_rate))
        {
            return Err(SimConfigError::InvalidMutationResetRate);
        }
        if !(self.mutation_scale_rate.is_finite()
            && (0.0..=1.0).contains(&self.mutation_scale_rate))
        {
            return Err(SimConfigError::InvalidMutationScaleRate);
        }
        if !(self.mutation_scale_min.is_finite()
            && self.mutation_scale_max.is_finite()
            && self.mutation_scale_min > 0.0
            && self.mutation_scale_max > 0.0
            && self.mutation_scale_min <= self.mutation_scale_max)
        {
            return Err(SimConfigError::InvalidMutationScaleBounds);
        }
        if !(self.mutation_value_limit.is_finite() && self.mutation_value_limit > 0.0) {
            return Err(SimConfigError::InvalidMutationValueLimit);
        }
        let mutation_budget =
            self.mutation_point_rate + self.mutation_reset_rate + self.mutation_scale_rate;
        if mutation_budget > 1.0 + f32::EPSILON {
            return Err(SimConfigError::InvalidMutationProbabilityBudget);
        }
        Ok(())
    }

    fn validate_homeostasis(&self) -> Result<(), SimConfigError> {
        if !(self.homeostasis_decay_rate.is_finite() && self.homeostasis_decay_rate >= 0.0) {
            return Err(SimConfigError::InvalidHomeostasisDecayRate);
        }
        Ok(())
    }

    fn validate_growth(&self) -> Result<(), SimConfigError> {
        if self.growth_maturation_steps == 0 {
            return Err(SimConfigError::InvalidGrowthMaturationSteps);
        }
        if !(self.growth_immature_metabolic_efficiency.is_finite()
            && (0.0..=1.0).contains(&self.growth_immature_metabolic_efficiency))
        {
            return Err(SimConfigError::InvalidGrowthImmatureMetabolicEfficiency);
        }
        Ok(())
    }

    fn validate_environment(&self) -> Result<(), SimConfigError> {
        if !(self.resource_regeneration_rate.is_finite() && self.resource_regeneration_rate >= 0.0)
        {
            return Err(SimConfigError::InvalidResourceRegenerationRate);
        }
        if !(self.environment_shift_resource_rate.is_finite()
            && self.environment_shift_resource_rate >= 0.0)
        {
            return Err(SimConfigError::InvalidEnvironmentShiftResourceRate);
        }
        if !(self.environment_cycle_low_rate.is_finite() && self.environment_cycle_low_rate >= 0.0)
        {
            return Err(SimConfigError::InvalidEnvironmentCycleLowRate);
        }
        if self.environment_shift_step > 0 && self.environment_cycle_period > 0 {
            return Err(SimConfigError::ConflictingEnvironmentFeatures);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validate_accepts_default() {
        let config = SimConfig::default();
        assert!(config.validate().is_ok());
    }

    #[test]
    fn validate_rejects_invalid_world_size() {
        let config = SimConfig {
            world_size: -1.0,
            ..SimConfig::default()
        };
        assert_eq!(config.validate(), Err(SimConfigError::InvalidWorldSize));

        let config = SimConfig {
            world_size: SimConfig::MAX_WORLD_SIZE + 1.0,
            ..SimConfig::default()
        };
        assert!(matches!(
            config.validate(),
            Err(SimConfigError::WorldSizeTooLarge { .. })
        ));
    }

    #[test]
    fn validate_rejects_invalid_mutation_budget() {
        let config = SimConfig {
            mutation_point_rate: 0.5,
            mutation_reset_rate: 0.5,
            mutation_scale_rate: 0.1,
            ..SimConfig::default()
        };
        assert_eq!(
            config.validate(),
            Err(SimConfigError::InvalidMutationProbabilityBudget)
        );
    }

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
        // New ablation toggles must default to true for backward compatibility
        assert!(cfg.enable_homeostasis);
        assert!(cfg.enable_response);
        assert!(cfg.enable_reproduction);
        assert!(cfg.enable_evolution);
        assert!(cfg.enable_growth);
    }

    #[test]
    fn validate_rejects_invalid_counts() {
        let config = SimConfig {
            num_organisms: 0,
            ..SimConfig::default()
        };
        assert_eq!(config.validate(), Err(SimConfigError::InvalidNumOrganisms));

        let config = SimConfig {
            num_organisms: 1,
            agents_per_organism: 0,
            ..SimConfig::default()
        };
        assert_eq!(
            config.validate(),
            Err(SimConfigError::InvalidAgentsPerOrganism)
        );

        let config = SimConfig {
            num_organisms: SimConfig::MAX_TOTAL_AGENTS + 1,
            agents_per_organism: 1,
            ..SimConfig::default()
        };
        match config.validate() {
            Err(SimConfigError::TooManyAgents { .. }) => (),
            _ => panic!("Expected TooManyAgents error"),
        }
    }

    #[test]
    fn error_display_messages_are_preserved() {
        let cases = vec![
            (
                SimConfigError::InvalidNumOrganisms,
                "num_organisms must be greater than 0",
            ),
            (
                SimConfigError::InvalidAgentsPerOrganism,
                "agents_per_organism must be greater than 0",
            ),
            (
                SimConfigError::AgentCountOverflow,
                "Total agent count overflow",
            ),
            (
                SimConfigError::TooManyAgents {
                    max: 100,
                    actual: 200,
                },
                "Too many agents: 200 > max 100",
            ),
            (
                SimConfigError::InvalidWorldSize,
                "world_size must be positive and finite",
            ),
            (SimConfigError::InvalidDt, "dt must be positive and finite"),
            (
                SimConfigError::InvalidMaxSpeed,
                "max_speed must be positive and finite",
            ),
            (
                SimConfigError::InvalidSensingRadius,
                "sensing_radius must be non-negative and finite",
            ),
            (
                SimConfigError::InvalidNeighborNorm,
                "neighbor_norm must be positive and finite",
            ),
            (
                SimConfigError::InvalidMetabolicViabilityFloor,
                "metabolic_viability_floor must be finite and non-negative",
            ),
            (
                SimConfigError::InvalidBoundaryDecayBaseRate,
                "boundary_decay_base_rate must be finite and non-negative",
            ),
            (
                SimConfigError::InvalidBoundaryDecayEnergyScale,
                "boundary_decay_energy_scale must be finite and non-negative",
            ),
            (
                SimConfigError::InvalidBoundaryWastePressureScale,
                "boundary_waste_pressure_scale must be finite and non-negative",
            ),
            (
                SimConfigError::InvalidBoundaryRepairWastePenaltyScale,
                "boundary_repair_waste_penalty_scale must be finite and non-negative",
            ),
            (
                SimConfigError::InvalidBoundaryRepairRate,
                "boundary_repair_rate must be finite and non-negative",
            ),
            (
                SimConfigError::InvalidBoundaryCollapseThreshold,
                "boundary_collapse_threshold must be finite and within [0,1]",
            ),
            (
                SimConfigError::InvalidDeathEnergyThreshold,
                "death_energy_threshold must be finite and non-negative",
            ),
            (
                SimConfigError::InvalidDeathBoundaryThreshold,
                "death_boundary_threshold must be finite and within [0,1]",
            ),
            (
                SimConfigError::InvalidReproductionMinEnergy,
                "reproduction_min_energy must be finite and non-negative",
            ),
            (
                SimConfigError::InvalidReproductionMinBoundary,
                "reproduction_min_boundary must be finite and within [0,1]",
            ),
            (
                SimConfigError::InvalidReproductionEnergyCost,
                "reproduction_energy_cost must be finite and positive",
            ),
            (
                SimConfigError::InvalidReproductionEnergyBalance,
                "reproduction_min_energy must be greater than or equal to reproduction_energy_cost",
            ),
            (
                SimConfigError::InvalidReproductionChildMinAgents,
                "reproduction_child_min_agents must be positive",
            ),
            (
                SimConfigError::InvalidReproductionSpawnRadius,
                "reproduction_spawn_radius must be finite and non-negative",
            ),
            (
                SimConfigError::InvalidCrowdingNeighborThreshold,
                "crowding_neighbor_threshold must be finite and non-negative",
            ),
            (
                SimConfigError::InvalidCrowdingBoundaryDecay,
                "crowding_boundary_decay must be finite and non-negative",
            ),
            (
                SimConfigError::InvalidMaxOrganismAgeSteps,
                "max_organism_age_steps must be positive",
            ),
            (
                SimConfigError::InvalidCompactionIntervalSteps,
                "compaction_interval_steps must be positive",
            ),
            (
                SimConfigError::InvalidMutationPointRate,
                "mutation_point_rate must be finite and within [0,1]",
            ),
            (
                SimConfigError::InvalidMutationPointScale,
                "mutation_point_scale must be finite and non-negative",
            ),
            (
                SimConfigError::InvalidMutationResetRate,
                "mutation_reset_rate must be finite and within [0,1]",
            ),
            (
                SimConfigError::InvalidMutationScaleRate,
                "mutation_scale_rate must be finite and within [0,1]",
            ),
            (
                SimConfigError::InvalidMutationScaleBounds,
                "mutation_scale_min/mutation_scale_max must be finite, positive, and ordered",
            ),
            (
                SimConfigError::InvalidMutationValueLimit,
                "mutation_value_limit must be finite and positive",
            ),
            (
                SimConfigError::InvalidMutationProbabilityBudget,
                "mutation_point_rate + mutation_reset_rate + mutation_scale_rate must be <= 1.0",
            ),
            (
                SimConfigError::InvalidHomeostasisDecayRate,
                "homeostasis_decay_rate must be finite and non-negative",
            ),
            (
                SimConfigError::InvalidGrowthMaturationSteps,
                "growth_maturation_steps must be positive",
            ),
            (
                SimConfigError::InvalidGrowthImmatureMetabolicEfficiency,
                "growth_immature_metabolic_efficiency must be finite and within [0,1]",
            ),
            (
                SimConfigError::InvalidResourceRegenerationRate,
                "resource_regeneration_rate must be finite and non-negative",
            ),
            (
                SimConfigError::InvalidEnvironmentShiftResourceRate,
                "environment_shift_resource_rate must be finite and non-negative",
            ),
            (
                SimConfigError::InvalidMetabolismEfficiencyMultiplier,
                "metabolism_efficiency_multiplier must be finite and within [0,1]",
            ),
            (
                SimConfigError::InvalidEnvironmentCycleLowRate,
                "environment_cycle_low_rate must be finite and non-negative",
            ),
            (
                SimConfigError::ConflictingEnvironmentFeatures,
                "environment_shift_step and environment_cycle_period are mutually exclusive",
            ),
            (
                SimConfigError::WorldSizeTooLarge {
                    max: 2048.0,
                    actual: 4096.0,
                },
                "world_size (4096) exceeds supported maximum (2048)",
            ),
        ];

        for (err, expected) in cases {
            assert_eq!(err.to_string(), expected);
        }
    }
}
