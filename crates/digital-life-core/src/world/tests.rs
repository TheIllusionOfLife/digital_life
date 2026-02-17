use super::*;
use crate::agent::Agent;
use crate::config::{MetabolismMode, SimConfig, SimConfigError};
use crate::nn::NeuralNet;
use crate::world::{ExperimentError, WorldInitError};

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
    assert!(matches!(
        result,
        Err(WorldInitError::Config(SimConfigError::AgentCountOverflow))
    ));
}

#[test]
fn try_new_rejects_too_many_agents() {
    let nn = NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT));
    let cfg = SimConfig {
        num_organisms: 1,
        agents_per_organism: SimConfig::MAX_TOTAL_AGENTS + 1,
        ..SimConfig::default()
    };
    let result = World::try_new(Vec::new(), vec![nn], cfg);
    assert!(matches!(
        result,
        Err(WorldInitError::Config(SimConfigError::TooManyAgents { .. }))
    ));
}

#[test]
fn set_config_rejects_invalid_update() {
    let mut world = make_world(1, 100.0);
    let mut cfg = world.config().clone();
    cfg.dt = -0.1;
    let result = world.set_config(cfg);
    assert!(matches!(
        result,
        Err(WorldInitError::Config(SimConfigError::InvalidDt))
    ));
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
fn set_config_switch_to_graph_redecodes_organism_engines() {
    let mut world = make_world(4, 100.0);
    assert!(
        world
            .organisms
            .iter()
            .all(|o| o.metabolism_engine.is_none()),
        "toy mode should not use per-organism metabolism engines"
    );

    let mut cfg = world.config().clone();
    cfg.metabolism_mode = MetabolismMode::Graph;
    world
        .set_config(cfg)
        .expect("switching to graph mode should be valid");

    assert!(
        world
            .organisms
            .iter()
            .all(|o| o.metabolism_engine.is_some()),
        "graph mode should decode per-organism metabolism engines"
    );
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
        Err(WorldInitError::Config(
            SimConfigError::InvalidBoundaryDecayBaseRate
        ))
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
        Err(WorldInitError::Config(
            SimConfigError::InvalidMutationProbabilityBudget
        ))
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
        Err(WorldInitError::Config(
            SimConfigError::InvalidReproductionEnergyBalance
        ))
    ));
}

#[test]
fn try_run_experiment_rejects_too_many_steps() {
    let mut world = make_world(1, 100.0);
    let result = world.try_run_experiment(World::MAX_EXPERIMENT_STEPS + 1, 1);
    assert!(matches!(result, Err(ExperimentError::TooManySteps { .. })));
}

#[test]
fn snapshot_experiment_collects_frames_at_requested_steps() {
    let mut world = make_world(10, 100.0);
    let summary = world
        .try_run_experiment_with_snapshots(10, 5, &[5])
        .expect("experiment should succeed");
    assert_eq!(summary.organism_snapshots.len(), 1);
    assert_eq!(summary.organism_snapshots[0].step, 5);
    assert!(
        !summary.organism_snapshots[0].organisms.is_empty(),
        "snapshot should contain at least one organism"
    );
}

#[test]
fn snapshot_experiment_skips_out_of_range_steps() {
    let mut world = make_world(10, 100.0);
    let summary = world
        .try_run_experiment_with_snapshots(10, 5, &[0, 20])
        .expect("experiment should succeed");
    // step 0 is never reached (loop is 1..=steps), step 20 > 10
    assert!(summary.organism_snapshots.is_empty());
}

#[test]
fn snapshot_organisms_have_valid_fields() {
    let mut world = make_world(10, 100.0);
    let summary = world
        .try_run_experiment_with_snapshots(5, 1, &[3])
        .expect("experiment should succeed");
    assert_eq!(summary.organism_snapshots.len(), 1);
    for org in &summary.organism_snapshots[0].organisms {
        assert!(org.energy >= 0.0);
        assert!(org.boundary_integrity >= 0.0 && org.boundary_integrity <= 1.0);
        assert!(org.maturity >= 0.0);
    }
}

#[test]
fn snapshots_include_agent_counts_when_metabolism_disabled() {
    let mut world = make_world(3, 100.0);
    world.config.enable_metabolism = false;
    world.config.enable_boundary_maintenance = false;
    let summary = world
        .try_run_experiment_with_snapshots(1, 1, &[1])
        .expect("experiment should succeed");
    assert_eq!(summary.organism_snapshots.len(), 1);
    let org = summary.organism_snapshots[0]
        .organisms
        .first()
        .expect("snapshot should contain an alive organism");
    assert_eq!(org.n_agents, 3);
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
    world_high.config.boundary_decay_base_rate = 0.003;
    world_high.config.boundary_repair_rate = 0.01;
    for a in &mut world_high.agents {
        a.internal_state[0] = 0.9;
    }

    let mut world_low = make_world(10, 100.0);
    world_low.config.enable_homeostasis = false;
    world_low.config.homeostasis_decay_rate = 0.0;
    world_low.config.enable_metabolism = false;
    world_low.config.enable_reproduction = false;
    world_low.config.boundary_decay_base_rate = 0.003;
    world_low.config.boundary_repair_rate = 0.01;
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
    let child = world
        .organisms
        .iter()
        .find(|o| o.generation == 1)
        .expect("reproduction should produce a generation-1 child within 10 steps");
    assert!(
        child.developmental_program.maturation_rate_modifier > 0.0,
        "child should have decoded developmental program"
    );
    assert!(
        child.parent_stable_id.is_some(),
        "child should have parent_stable_id"
    );
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
        Err(WorldInitError::Config(
            SimConfigError::ConflictingEnvironmentFeatures
        ))
    ));
}
