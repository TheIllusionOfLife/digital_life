use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use digital_life_core::agent::Agent;
use digital_life_core::config::{MetabolismMode, SimConfig};
use digital_life_core::nn::NeuralNet;
use digital_life_core::world::World;
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha12Rng;
use std::fs::File;
use std::io::BufReader;
use std::path::PathBuf;

const WORLD_SIZE: f64 = 100.0;
const WARMUP_STEPS: usize = 10;
const BENCHMARK_STEPS: usize = 200;
const TARGET_SPS: f64 = 100.0;

#[derive(Parser)]
#[command(name = "digital-life")]
#[command(about = "Digital Life Simulation CLI")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Run a single simulation from a config file
    Run {
        /// Path to config file (JSON)
        #[arg(long)]
        config: PathBuf,

        /// Output directory for results (optional)
        #[arg(long)]
        out: Option<PathBuf>,

        /// Number of simulation steps to run (default: 10000)
        #[arg(long, default_value_t = 10000)]
        steps: usize,
    },
    /// Run the performance benchmark suite
    Benchmark,
    /// Dump the default configuration to stdout
    DumpDefaultConfig,
}

fn create_agents(config: &SimConfig) -> Result<Vec<Agent>> {
    let total_agents = config.num_organisms * config.agents_per_organism;
    let mut rng = ChaCha12Rng::seed_from_u64(config.seed);
    let mut agents = Vec::with_capacity(total_agents);
    for org in 0..config.num_organisms {
        for i in 0..config.agents_per_organism {
            let id = (org * config.agents_per_organism + i) as u32;
            let organism_id: u16 = org.try_into().context("Organism ID overflow (max 65535)")?;
            let pos = [
                rng.random::<f64>() * config.world_size,
                rng.random::<f64>() * config.world_size,
            ];
            agents.push(Agent::new(id, organism_id, pos));
        }
    }
    Ok(agents)
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

fn run_benchmark(
    num_organisms: usize,
    agents_per_organism: usize,
    seed: u64,
    metabolism_mode: MetabolismMode,
) -> Result<()> {
    let config = SimConfig {
        world_size: WORLD_SIZE,
        num_organisms,
        agents_per_organism,
        metabolism_mode,
        seed, // Use provided seed
        ..SimConfig::default()
    };

    config
        .validate()
        .context("Benchmark config validation error")?;

    let agents = create_agents(&config)?;
    let nns = create_nns(&config);
    let mut world = World::new(agents, nns, config.clone());

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

    let total_agents = num_organisms * agents_per_organism;
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
    Ok(())
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Commands::DumpDefaultConfig => {
            let config = SimConfig::default();
            println!("{}", serde_json::to_string_pretty(&config)?);
        }
        Commands::Benchmark => {
            if cfg!(debug_assertions) {
                eprintln!("WARNING: running in debug mode. Results are not representative.");
                eprintln!("         Use: cargo run -p digital-life-cli --release -- benchmark");
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
                    run_benchmark(orgs, apg, 42, mode)?;
                }
            }
        }
        Commands::Run { config, out, steps } => {
            let file = File::open(&config).context("failed to open config file")?;
            let reader = BufReader::new(file);
            let sim_config: SimConfig =
                serde_json::from_reader(reader).context("failed to parse config")?;

            // Validate config
            sim_config.validate().context("Config validation error")?;

            println!("Loaded config from {:?}", config);
            println!("Simulating for {} steps...", steps);

            let agents = create_agents(&sim_config)?;
            let nns = create_nns(&sim_config);
            let mut world = World::new(agents, nns, sim_config.clone());

            let summary = world.run_experiment(steps, 100);

            if let Some(out_dir) = out {
                std::fs::create_dir_all(&out_dir).context("failed to create output directory")?;
                let summary_path = out_dir.join("summary.json");
                let file = File::create(summary_path).context("failed to create summary file")?;
                serde_json::to_writer_pretty(file, &summary).context("failed to write summary")?;
                println!("Run complete. Results saved to {:?}", out_dir);
            } else {
                println!("Run complete. Final alive: {}", summary.final_alive_count);
            }
        }
    }
    Ok(())
}
