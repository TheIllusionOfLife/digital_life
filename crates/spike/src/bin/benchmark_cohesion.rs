use digital_life_core::agent::Agent;
use digital_life_core::config::{MetabolismMode, SimConfig};
use digital_life_core::nn::NeuralNet;
use digital_life_core::world::World;
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha12Rng;
use std::time::Instant;

fn create_agents(config: &SimConfig) -> Vec<Agent> {
    let total_agents = config.num_organisms * config.agents_per_organism;
    let mut rng = ChaCha12Rng::seed_from_u64(config.seed);
    let mut agents = Vec::with_capacity(total_agents);
    for org in 0..config.num_organisms {
        for i in 0..config.agents_per_organism {
            let id = (org * config.agents_per_organism + i) as u32;
            let organism_id = u16::try_from(org).expect("Organism ID overflow (max 65535)");
            let pos = [
                rng.random::<f64>() * config.world_size,
                rng.random::<f64>() * config.world_size,
            ];
            agents.push(Agent::new(id, organism_id, pos));
        }
    }
    agents
}

fn create_nns(config: &SimConfig) -> Vec<NeuralNet> {
    let mut rng = ChaCha12Rng::seed_from_u64(config.seed);
    (0..config.num_organisms)
        .map(|_| {
            let weights = (0..NeuralNet::WEIGHT_COUNT).map(|_| rng.random::<f32>() * 2.0 - 1.0);
            NeuralNet::from_weights(weights)
        })
        .collect()
}

fn main() {
    let num_organisms = 500;
    let agents_per_organism = 100;
    let total_agents = num_organisms * agents_per_organism;
    println!("Benchmarking with {} organisms, {} agents each (total {})", num_organisms, agents_per_organism, total_agents);

    let config = SimConfig {
        world_size: 1000.0,
        num_organisms,
        agents_per_organism,
        metabolism_mode: MetabolismMode::Toy,
        seed: 42,
        ..SimConfig::default()
    };

    let agents = create_agents(&config);
    let nns = create_nns(&config);
    let mut world1 = World::new(agents.clone(), nns.clone(), config.clone());
    let mut world2 = World::new(agents, nns, config);

    let steps = 10;

    // Run WITHOUT metrics
    let start = Instant::now();
    for _ in 0..steps {
        world1.step();
    }
    let duration_no_metrics = start.elapsed();
    println!("Time for {} steps WITHOUT metrics: {:?}", steps, duration_no_metrics);
    println!("Avg time per step (no metrics): {:?}", duration_no_metrics / steps as u32);

    // Run WITH metrics (every step)
    let start = Instant::now();
    world2.run_experiment(steps, 1);
    let duration_metrics = start.elapsed();

    println!("Time for {} steps WITH metrics: {:?}", steps, duration_metrics);
    println!("Avg time per step (with metrics): {:?}", duration_metrics / steps as u32);

    let diff = duration_metrics.saturating_sub(duration_no_metrics);
    println!("Total metrics overhead: {:?}", diff);
    println!("Avg metrics overhead per step: {:?}", diff / steps as u32);
}
