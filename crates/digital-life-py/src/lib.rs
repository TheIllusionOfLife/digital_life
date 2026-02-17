use digital_life_core::agent::Agent;
use digital_life_core::config::SimConfig;
use digital_life_core::nn::NeuralNet;
use digital_life_core::world::World;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha12Rng;
use serde_json::json;

/// Minimal PyO3 module exposing digital-life-core to Python.
#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[pyfunction]
fn default_config_json() -> PyResult<String> {
    serde_json::to_string(&SimConfig::default())
        .map_err(|e| PyValueError::new_err(format!("failed to serialize default config: {e}")))
}

#[pyfunction]
fn validate_config_json(config_json: &str) -> PyResult<bool> {
    world_from_config_json(config_json)
        .map(|_| true)
        .map_err(PyValueError::new_err)
}

#[pyfunction]
fn step_once(
    num_organisms: usize,
    agents_per_organism: usize,
    world_size: f64,
) -> PyResult<(usize, u64)> {
    if world_size > World::MAX_WORLD_SIZE {
        return Err(PyValueError::new_err(format!(
            "world_size ({world_size}) exceeds supported maximum ({})",
            World::MAX_WORLD_SIZE
        )));
    }

    let config = SimConfig {
        num_organisms,
        agents_per_organism,
        world_size,
        ..SimConfig::default()
    };
    let (agents, nns) = bootstrap_entities(
        num_organisms,
        agents_per_organism,
        world_size,
        config.seed,
        config.sensing_radius,
    )
    .map_err(PyValueError::new_err)?;
    let mut world = World::new(agents, nns, config)
        .map_err(|e| PyValueError::new_err(format!("invalid world configuration: {e}")))?;
    let timings = world.step();
    Ok((world.agents.len(), timings.total_us))
}

#[pyfunction]
fn run_experiment_json(config_json: &str, steps: usize, sample_every: usize) -> PyResult<String> {
    run_experiment_json_impl(config_json, steps, sample_every).map_err(PyValueError::new_err)
}

#[pyfunction]
fn run_evolution_experiment_json(
    config_json: &str,
    steps: usize,
    sample_every: usize,
) -> PyResult<String> {
    run_evolution_experiment_json_impl(config_json, steps, sample_every)
        .map_err(PyValueError::new_err)
}

fn run_experiment_json_impl(
    config_json: &str,
    steps: usize,
    sample_every: usize,
) -> Result<String, String> {
    if steps > World::MAX_EXPERIMENT_STEPS {
        return Err(format!(
            "steps ({steps}) exceeds supported maximum ({})",
            World::MAX_EXPERIMENT_STEPS
        ));
    }
    let mut world = world_from_config_json(config_json)?;
    let summary = world
        .try_run_experiment(steps, sample_every)
        .map_err(|e| format!("invalid experiment parameters: {e}"))?;
    serde_json::to_string(&summary)
        .map_err(|e| format!("failed to serialize experiment summary: {e}"))
}

#[pyfunction]
fn run_niche_experiment_json(
    config_json: &str,
    steps: usize,
    sample_every: usize,
    snapshot_steps_json: &str,
) -> PyResult<String> {
    run_niche_experiment_json_impl(config_json, steps, sample_every, snapshot_steps_json)
        .map_err(PyValueError::new_err)
}

fn run_niche_experiment_json_impl(
    config_json: &str,
    steps: usize,
    sample_every: usize,
    snapshot_steps_json: &str,
) -> Result<String, String> {
    // Pre-check for maximum items to avoid allocating a massive vector
    // A valid JSON array of N items has at least N-1 commas.
    // If commas >= MAX, we definitely have >= MAX+1 items (or invalid JSON).
    if snapshot_steps_json.bytes().filter(|&b| b == b',').count() >= World::MAX_EXPERIMENT_SNAPSHOTS
    {
        return Err(format!(
            "snapshot_steps json complexity exceeds supported maximum ({})",
            World::MAX_EXPERIMENT_SNAPSHOTS
        ));
    }

    let snapshot_steps: Vec<usize> = serde_json::from_str(snapshot_steps_json)
        .map_err(|e| format!("invalid snapshot_steps json: {e}"))?;
    // Post-check for exact count
    if snapshot_steps.len() > World::MAX_EXPERIMENT_SNAPSHOTS {
        return Err(format!(
            "snapshot_steps count ({}) exceeds supported maximum ({})",
            snapshot_steps.len(),
            World::MAX_EXPERIMENT_SNAPSHOTS
        ));
    }
    let mut world = world_from_config_json(config_json)?;
    let summary = world
        .try_run_experiment_with_snapshots(steps, sample_every, &snapshot_steps)
        .map_err(|e| format!("invalid experiment parameters: {e}"))?;
    serde_json::to_string(&summary)
        .map_err(|e| format!("failed to serialize experiment summary: {e}"))
}

fn run_evolution_experiment_json_impl(
    config_json: &str,
    steps: usize,
    sample_every: usize,
) -> Result<String, String> {
    let mut world = world_from_config_json(config_json)?;
    let summary = world
        .try_run_experiment(steps, sample_every)
        .map_err(|e| format!("invalid experiment parameters: {e}"))?;
    let stats = world.population_stats();
    let config = world.config();
    let payload = json!({
        "kind": "evolution_v1",
        "summary": summary,
        "final_population": stats,
        "effective_parameters": {
            "reproduction_min_energy": config.reproduction_min_energy,
            "reproduction_min_boundary": config.reproduction_min_boundary,
            "reproduction_energy_cost": config.reproduction_energy_cost,
            "reproduction_child_min_agents": config.reproduction_child_min_agents,
            "reproduction_spawn_radius": config.reproduction_spawn_radius,
            "crowding_neighbor_threshold": config.crowding_neighbor_threshold,
            "crowding_boundary_decay": config.crowding_boundary_decay,
            "max_organism_age_steps": config.max_organism_age_steps,
            "compaction_interval_steps": config.compaction_interval_steps,
            "mutation_point_rate": config.mutation_point_rate,
            "mutation_point_scale": config.mutation_point_scale,
            "mutation_reset_rate": config.mutation_reset_rate,
            "mutation_scale_rate": config.mutation_scale_rate,
            "mutation_scale_min": config.mutation_scale_min,
            "mutation_scale_max": config.mutation_scale_max,
            "mutation_value_limit": config.mutation_value_limit,
        }
    });
    serde_json::to_string(&payload)
        .map_err(|e| format!("failed to serialize evolution experiment summary: {e}"))
}

fn world_from_config_json(config_json: &str) -> Result<World, String> {
    let config: SimConfig =
        serde_json::from_str(config_json).map_err(|e| format!("invalid config json: {e}"))?;
    let (agents, nns) = bootstrap_entities(
        config.num_organisms,
        config.agents_per_organism,
        config.world_size,
        config.seed,
        config.sensing_radius,
    )
    .map_err(|e| format!("invalid world configuration: {e}"))?;
    World::new(agents, nns, config).map_err(|e| format!("invalid world configuration: {e}"))
}

fn bootstrap_entities(
    num_organisms: usize,
    agents_per_organism: usize,
    world_size: f64,
    seed: u64,
    sensing_radius: f64,
) -> Result<(Vec<Agent>, Vec<NeuralNet>), String> {
    let total_agents = checked_total_agents(num_organisms, agents_per_organism)?;
    let mut rng = ChaCha12Rng::seed_from_u64(seed);
    let cluster_radius = sensing_radius.min(world_size / 4.0);

    let mut agents = Vec::with_capacity(total_agents);
    for org in 0..num_organisms {
        let cx: f64 = rng.random_range(0.0..world_size);
        let cy: f64 = rng.random_range(0.0..world_size);
        for a in 0..agents_per_organism {
            let global_id = org * agents_per_organism + a;
            let (dx, dy) = if cluster_radius > f64::EPSILON {
                (
                    rng.random_range(-cluster_radius..cluster_radius),
                    rng.random_range(-cluster_radius..cluster_radius),
                )
            } else {
                (0.0, 0.0)
            };
            let px = (cx + dx).rem_euclid(world_size);
            let py = (cy + dy).rem_euclid(world_size);
            agents.push(Agent::new(global_id as u32, org as u16, [px, py]));
        }
    }

    let nns = (0..num_organisms)
        .map(|_| {
            NeuralNet::from_weights(
                (0..NeuralNet::WEIGHT_COUNT).map(|_| rng.random_range(-1.0f32..1.0)),
            )
        })
        .collect();
    Ok((agents, nns))
}

fn checked_total_agents(num_organisms: usize, agents_per_organism: usize) -> Result<usize, String> {
    if num_organisms > u16::MAX as usize {
        return Err(format!(
            "num_organisms ({num_organisms}) exceeds maximum organism count ({})",
            u16::MAX
        ));
    }
    let total_agents = num_organisms
        .checked_mul(agents_per_organism)
        .ok_or_else(|| "num_organisms * agents_per_organism overflows usize".to_string())?;
    if total_agents > SimConfig::MAX_TOTAL_AGENTS {
        return Err(format!(
            "total agents ({total_agents}) exceeds supported maximum ({})",
            SimConfig::MAX_TOTAL_AGENTS
        ));
    }
    Ok(total_agents)
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    m.add_function(wrap_pyfunction!(default_config_json, m)?)?;
    m.add_function(wrap_pyfunction!(validate_config_json, m)?)?;
    m.add_function(wrap_pyfunction!(step_once, m)?)?;
    m.add_function(wrap_pyfunction!(run_experiment_json, m)?)?;
    m.add_function(wrap_pyfunction!(run_evolution_experiment_json, m)?)?;
    m.add_function(wrap_pyfunction!(run_niche_experiment_json, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn checked_total_agents_rejects_overflow() {
        let result = checked_total_agents(usize::MAX, 2);
        assert!(result.is_err());
    }

    #[test]
    fn checked_total_agents_rejects_excess_organism_count() {
        let result = checked_total_agents(u16::MAX as usize + 1, 1);
        assert!(result.is_err());
    }

    #[test]
    fn checked_total_agents_rejects_too_many() {
        let result = checked_total_agents(1, SimConfig::MAX_TOTAL_AGENTS + 1);
        assert!(result.is_err());
    }

    #[test]
    fn checked_total_agents_accepts_limit() {
        let result = checked_total_agents(1, SimConfig::MAX_TOTAL_AGENTS);
        assert_eq!(
            result.expect("limit should be accepted"),
            SimConfig::MAX_TOTAL_AGENTS
        );
    }

    #[test]
    fn sim_config_json_includes_new_metabolism_fields() {
        let config_json =
            serde_json::to_string(&SimConfig::default()).expect("default config should serialize");
        let value: serde_json::Value =
            serde_json::from_str(&config_json).expect("config output must be valid JSON");
        assert!(value["world_size"].as_f64().is_some());
        assert!(value["metabolic_viability_floor"].as_f64().is_some());
        assert!(value["metabolism_mode"].as_str().is_some());
        assert!(value["reproduction_min_energy"].as_f64().is_some());
        assert!(value["max_organism_age_steps"].as_u64().is_some());
        assert!(value["mutation_point_rate"].as_f64().is_some());
    }

    #[test]
    fn run_experiment_json_impl_returns_summary_json() {
        let config_json = serde_json::to_string(&SimConfig {
            num_organisms: 1,
            agents_per_organism: 1,
            ..SimConfig::default()
        })
        .expect("config should serialize");
        let output = run_experiment_json_impl(&config_json, 10, 5).expect("experiment should run");
        let payload: serde_json::Value =
            serde_json::from_str(&output).expect("output should be valid json");
        assert_eq!(payload["steps"].as_u64(), Some(10));
        assert!(payload["samples"].as_array().is_some());
    }

    #[test]
    fn run_experiment_json_impl_rejects_zero_sampling_interval() {
        let config_json =
            serde_json::to_string(&SimConfig::default()).expect("config should serialize");
        let result = run_experiment_json_impl(&config_json, 10, 0);
        assert!(result.is_err());
    }

    #[test]
    fn run_experiment_json_impl_includes_evolution_metrics() {
        let config_json = serde_json::to_string(&SimConfig {
            num_organisms: 1,
            agents_per_organism: 8,
            ..SimConfig::default()
        })
        .expect("config should serialize");
        let output = run_experiment_json_impl(&config_json, 5, 1).expect("experiment should run");
        let payload: serde_json::Value =
            serde_json::from_str(&output).expect("output should be valid json");
        let sample = &payload["samples"][0];
        assert!(sample["birth_count"].is_number());
        assert!(sample["mean_generation"].is_number());
    }

    #[test]
    fn run_evolution_experiment_json_impl_returns_v1_payload() {
        let config_json = serde_json::to_string(&SimConfig {
            num_organisms: 1,
            agents_per_organism: 8,
            ..SimConfig::default()
        })
        .expect("config should serialize");
        let output =
            run_evolution_experiment_json_impl(&config_json, 5, 1).expect("experiment should run");
        let payload: serde_json::Value =
            serde_json::from_str(&output).expect("output should be valid json");
        assert_eq!(payload["kind"].as_str(), Some("evolution_v1"));
        assert!(payload["summary"]["samples"].is_array());
        assert!(payload["final_population"]["alive_count"].is_number());
        assert!(payload["effective_parameters"]["reproduction_min_energy"].is_number());
        assert!(payload["effective_parameters"]["mutation_point_rate"].is_number());
    }

    #[test]
    fn world_from_config_json_rejects_invalid_payload() {
        let result = world_from_config_json("{\"world_size\": \"bad\"}");
        assert!(result.is_err());
    }

    #[test]
    fn bootstrap_is_deterministic_for_same_seed() {
        let (agents_a, nns_a) = bootstrap_entities(2, 3, 50.0, 42, 5.0).unwrap();
        let (agents_b, nns_b) = bootstrap_entities(2, 3, 50.0, 42, 5.0).unwrap();
        for (a, b) in agents_a.iter().zip(&agents_b) {
            assert_eq!(a.position, b.position);
            assert_eq!(a.organism_id, b.organism_id);
        }
        for (a, b) in nns_a.iter().zip(&nns_b) {
            assert_eq!(a.to_weight_vec(), b.to_weight_vec());
        }
    }

    #[test]
    fn bootstrap_positions_within_world_bounds() {
        let world_size = 80.0;
        let (agents, _) = bootstrap_entities(5, 10, world_size, 7, 5.0).unwrap();
        for agent in &agents {
            assert!(
                (0.0..world_size).contains(&agent.position[0]),
                "x={} out of [0, {world_size})",
                agent.position[0]
            );
            assert!(
                (0.0..world_size).contains(&agent.position[1]),
                "y={} out of [0, {world_size})",
                agent.position[1]
            );
        }
    }

    #[test]
    fn bootstrap_nn_weights_within_range() {
        let (_, nns) = bootstrap_entities(3, 2, 50.0, 99, 5.0).unwrap();
        for nn in &nns {
            for &w in &nn.to_weight_vec() {
                assert!((-1.0..1.0).contains(&w), "weight {w} outside [-1, 1)");
            }
        }
    }

    #[test]
    fn bootstrap_different_seeds_produce_different_positions() {
        let (agents_a, _) = bootstrap_entities(2, 5, 50.0, 0, 5.0).unwrap();
        let (agents_b, _) = bootstrap_entities(2, 5, 50.0, 1, 5.0).unwrap();
        let differs = agents_a
            .iter()
            .zip(&agents_b)
            .any(|(a, b)| a.position != b.position);
        assert!(
            differs,
            "different seeds should produce different positions"
        );
    }

    #[test]
    fn run_niche_experiment_json_impl_returns_snapshots() {
        let config_json = serde_json::to_string(&SimConfig {
            num_organisms: 2,
            agents_per_organism: 8,
            ..SimConfig::default()
        })
        .expect("config should serialize");
        let output = run_niche_experiment_json_impl(&config_json, 10, 5, "[5, 10]")
            .expect("niche experiment should run");
        let payload: serde_json::Value =
            serde_json::from_str(&output).expect("output should be valid json");
        assert!(payload["organism_snapshots"].is_array());
        let snapshots = payload["organism_snapshots"].as_array().unwrap();
        assert_eq!(snapshots.len(), 2);
        assert_eq!(snapshots[0]["step"].as_u64(), Some(5));
        assert!(snapshots[0]["organisms"].is_array());
    }

    #[test]
    fn run_experiment_json_impl_handles_zero_sensing_radius() {
        // This test reproduces the panic when sensing_radius is 0.0
        let config = SimConfig {
            sensing_radius: 0.0,
            ..SimConfig::default()
        };
        let config_json = serde_json::to_string(&config).unwrap();

        // This should not panic
        let result = run_experiment_json_impl(&config_json, 1, 1);
        assert!(result.is_ok());
    }

    #[test]
    fn run_niche_experiment_json_impl_rejects_excessive_snapshots() {
        let config_json =
            serde_json::to_string(&SimConfig::default()).expect("config should serialize");
        // Create a JSON array with MAX_EXPERIMENT_SNAPSHOTS + 1 elements
        let count = World::MAX_EXPERIMENT_SNAPSHOTS + 1;
        let mut steps = Vec::with_capacity(count);
        for i in 0..count {
            steps.push(i);
        }
        let snapshot_steps_json = serde_json::to_string(&steps).expect("steps should serialize");

        let result = run_niche_experiment_json_impl(&config_json, 10, 5, &snapshot_steps_json);
        assert!(result.is_err());
    }
}
