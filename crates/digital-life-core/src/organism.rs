use crate::genome::Genome;
use crate::metabolism::{MetabolicState, MetabolismEngine};
use crate::nn::NeuralNet;

#[derive(Clone, Debug)]
pub struct Organism {
    // Fields are private by design; use accessors to preserve invariants.
    id: u16,
    agent_start: usize,
    agent_count: usize,
    nn: NeuralNet,
    genome: Genome,
}

impl Organism {
    pub fn new(
        id: u16,
        agent_start: usize,
        agent_count: usize,
        nn: NeuralNet,
        genome: Genome,
    ) -> Self {
        Self {
            id,
            agent_start,
            agent_count,
            nn,
            genome,
        }
    }

    pub fn agent_range(&self) -> std::ops::Range<usize> {
        self.agent_start..self.agent_start + self.agent_count
    }

    pub fn id(&self) -> u16 {
        self.id
    }

    pub fn agent_start(&self) -> usize {
        self.agent_start
    }

    pub fn agent_count(&self) -> usize {
        self.agent_count
    }

    pub fn nn(&self) -> &NeuralNet {
        &self.nn
    }

    pub fn genome(&self) -> &Genome {
        &self.genome
    }
}

#[derive(Clone, Debug)]
pub struct OrganismRuntime {
    pub id: u16,
    pub stable_id: u64,
    pub generation: u32,
    pub age_steps: usize,
    pub alive: bool,
    pub boundary_integrity: f32,
    pub metabolic_state: MetabolicState,
    pub genome: Genome,
    pub ancestor_genome: Genome,
    pub nn: NeuralNet,
    pub agent_ids: Vec<u32>,
    /// Maturation level: 0.0 (seed) → 1.0 (fully mature).
    pub maturity: f32,
    /// Per-organism metabolism engine (Some when Graph mode, None when Toy).
    pub metabolism_engine: Option<MetabolismEngine>,
}
