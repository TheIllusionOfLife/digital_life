use digital_life_core::agent::Agent;
use digital_life_core::config::SimConfig;
use digital_life_core::nn::NeuralNet;
use digital_life_core::world::World;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

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
    let config: SimConfig = serde_json::from_str(config_json)
        .map_err(|e| PyValueError::new_err(format!("invalid config json: {e}")))?;
    let (agents, nns) = bootstrap_entities(
        config.num_organisms,
        config.agents_per_organism,
        config.world_size,
    )
    .map_err(|e| PyValueError::new_err(format!("invalid world configuration: {e}")))?;
    World::try_new(agents, nns, config)
        .map(|_| true)
        .map_err(|e| PyValueError::new_err(format!("invalid world configuration: {e}")))
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
    let config: SimConfig = serde_json::from_str(config_json)
        .map_err(|e| PyValueError::new_err(format!("invalid config json: {e}")))?;
    let (agents, nns) = bootstrap_entities(
        config.num_organisms,
        config.agents_per_organism,
        config.world_size,
    )
    .map_err(|e| PyValueError::new_err(format!("invalid world configuration: {e}")))?;
    let mut world = World::try_new(agents, nns, config)
        .map_err(|e| PyValueError::new_err(format!("invalid world configuration: {e}")))?;
    let summary = world.run_experiment(steps, sample_every);
    serde_json::to_string(&summary)
        .map_err(|e| PyValueError::new_err(format!("failed to serialize experiment summary: {e}")))
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
    }
}
