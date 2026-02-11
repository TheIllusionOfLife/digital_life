use crate::genome::Genome;
use crate::nn::NeuralNet;

#[derive(Clone, Debug)]
pub struct Organism {
    pub id: u16,
    pub agent_start: usize,
    pub agent_count: usize,
    pub nn: NeuralNet,
    pub genome: Genome,
}

impl Organism {
    pub fn new(id: u16, agent_start: usize, agent_count: usize, nn: NeuralNet, genome: Genome) -> Self {
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
}
