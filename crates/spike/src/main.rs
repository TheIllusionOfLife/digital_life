use digital_life_core::agent::Agent;
use digital_life_core::config::{MetabolismMode, SimConfig};
use digital_life_core::nn::NeuralNet;
use digital_life_core::world::World;
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha12Rng;

const WORLD_SIZE: f64 = 100.0;
const WARMUP_STEPS: usize = 10;
const BENCHMARK_STEPS: usize = 200;
const TARGET_SPS: f64 = 100.0;

fn run_benchmark(
    num_organisms: usize,
    agents_per_organism: usize,
    seed: u64,
    metabolism_mode: MetabolismMode,
) {
    let total_agents = num_organisms * agents_per_organism;
    let mut rng = ChaCha12Rng::seed_from_u64(seed);

    // Create agents
    let mut agents = Vec::with_capacity(total_agents);
    for org in 0..num_organisms {
        for i in 0..agents_per_organism {
            let id = (org * agents_per_organism + i) as u32;
            let pos = [
                rng.random::<f64>() * WORLD_SIZE,
                rng.random::<f64>() * WORLD_SIZE,
            ];
            agents.push(Agent::new(id, org as u16, pos));
        }
    }

    // Create NNs (one per organism)
    let nns: Vec<NeuralNet> = (0..num_organisms)
        .map(|_| {
            let weights = (0..NeuralNet::WEIGHT_COUNT).map(|_| rng.random::<f32>() * 2.0 - 1.0);
            NeuralNet::from_weights(weights)
        })
        .collect();

    let config = SimConfig {
        world_size: WORLD_SIZE,
        num_organisms,
        agents_per_organism,
        metabolism_mode,
        ..SimConfig::default()
    };
    let mut world = World::new(agents, nns, config);

    // Warmup
    for _ in 0..WARMUP_STEPS {
        world.step();
    }

    // Benchmark
    let mut total_spatial = 0u64;
    let mut total_nn = 0u64;
    let mut total_state = 0u64;
    let mut total_time = 0u64;

    for _ in 0..BENCHMARK_STEPS {
        let timings = world.step();
        total_spatial += timings.spatial_build_us;
        total_nn += timings.nn_query_us;
        total_state += timings.state_update_us;
        total_time += timings.total_us;
    }

    let avg_step_us = total_time as f64 / BENCHMARK_STEPS as f64;
    let steps_per_sec = 1_000_000.0 / avg_step_us;

    println!(
        "--- {total_agents} agents ({num_organisms} organisms x {agents_per_organism} agents) ---"
    );
    println!("  Avg step:      {avg_step_us:.0} us ({steps_per_sec:.1} steps/sec)");
    println!(
        "  Breakdown:     spatial={:.0} us, nn+query={:.0} us, state={:.0} us",
        total_spatial as f64 / BENCHMARK_STEPS as f64,
        total_nn as f64 / BENCHMARK_STEPS as f64,
        total_state as f64 / BENCHMARK_STEPS as f64,
    );

    let verdict = if steps_per_sec >= TARGET_SPS {
        "GO"
    } else {
        "NO-GO"
    };
    println!("  Verdict:       {verdict} (target: >={TARGET_SPS} steps/sec)");
    let summary = world.run_experiment(100, 100);
    println!(
        "  Alive orgs:    {}/{}",
        summary.final_alive_count, num_organisms
    );
    println!();
}

fn main() {
    if cfg!(debug_assertions) {
        eprintln!("WARNING: running in debug mode. Results are not representative.");
        eprintln!("         Use: cargo run -p digital-life-spike --release");
        eprintln!();
    }
    println!("=== Digital Life Feasibility Spike ===");
    println!("Warmup: {WARMUP_STEPS} steps, Benchmark: {BENCHMARK_STEPS} steps");
    println!("Target: >={TARGET_SPS} steps/sec for 2500 agents");
    println!();

    // Multiple configurations
    let configs = [
        (10, 10),  // 100 agents
        (25, 25),  // 625 agents
        (50, 50),  // 2500 agents (target)
        (50, 100), // 5000 agents (stress test)
    ];

    let modes = [MetabolismMode::Toy, MetabolismMode::Graph];
    for mode in modes {
        println!("=== Mode: {:?} ===", mode);
        for (orgs, apg) in configs {
            run_benchmark(orgs, apg, 42, mode);
        }
    }
}
