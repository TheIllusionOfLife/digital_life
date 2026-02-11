use digital_life_core::agent::Agent;
use digital_life_core::config::SimConfig;
use digital_life_core::nn::NeuralNet;
use digital_life_core::world::World;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
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

    let (agents, nns) = bootstrap_entities(num_organisms, agents_per_organism, world_size)
        .map_err(PyValueError::new_err)?;
    let config = SimConfig {
        num_organisms,
        agents_per_organism,
        world_size,
        ..SimConfig::default()
    };
    let mut world = World::try_new(agents, nns, config)
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
    )
    .map_err(|e| format!("invalid world configuration: {e}"))?;
    World::try_new(agents, nns, config).map_err(|e| format!("invalid world configuration: {e}"))
}

fn bootstrap_entities(
    num_organisms: usize,
    agents_per_organism: usize,
    world_size: f64,
) -> Result<(Vec<Agent>, Vec<NeuralNet>), String> {
    let total_agents = checked_total_agents(num_organisms, agents_per_organism)?;
    let wrapped_origin = 0.0f64.rem_euclid(world_size.max(1.0));
    let agents = (0..total_agents)
        .map(|i| {
            let organism_id = (i / agents_per_organism.max(1)) as u16;
            Agent::new(i as u32, organism_id, [wrapped_origin, wrapped_origin])
        })
        .collect();
    let nns = (0..num_organisms)
        .map(|_| NeuralNet::from_weights(std::iter::repeat_n(0.0f32, NeuralNet::WEIGHT_COUNT)))
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
    if total_agents > World::MAX_TOTAL_AGENTS {
        return Err(format!(
            "total agents ({total_agents}) exceeds supported maximum ({})",
            World::MAX_TOTAL_AGENTS
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
        let result = checked_total_agents(1, World::MAX_TOTAL_AGENTS + 1);
        assert!(result.is_err());
    }

    #[test]
    fn checked_total_agents_accepts_limit() {
        let result = checked_total_agents(1, World::MAX_TOTAL_AGENTS);
        assert_eq!(
            result.expect("limit should be accepted"),
            World::MAX_TOTAL_AGENTS
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
}
