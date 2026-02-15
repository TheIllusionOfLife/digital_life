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

/// Decoded developmental program from genome segment 3 (8 floats).
///
/// Encodes a 3-stage (juvenile → adolescent → adult) developmental trajectory
/// that affects boundary repair, sensing radius, and metabolic efficiency.
#[derive(Clone, Debug)]
pub struct DevelopmentalProgram {
    /// g[0]: 2^(g.clamp(-2,2)) → [0.25, 4.0] — maturation speed modifier.
    pub maturation_rate_modifier: f32,
    /// g[1]: sigmoid → [0.2, 1.0] — juvenile boundary repair factor.
    pub juvenile_boundary_repair: f32,
    /// g[2]: sigmoid → [0.3, 1.0] — juvenile sensing radius factor.
    pub juvenile_sensing: f32,
    /// g[3]: sigmoid → [0.3, 0.7] — threshold for adolescent transition.
    pub adolescent_threshold: f32,
    /// g[4]: sigmoid → [0.5, 1.0] — adolescent boundary repair factor.
    pub adolescent_boundary_repair: f32,
    /// g[5]: sigmoid → [0.5, 1.0] — adolescent sensing radius factor.
    pub adolescent_sensing: f32,
    /// g[6]: sigmoid → [0.1, 0.5] — juvenile metabolic efficiency factor.
    pub juvenile_metabolic_efficiency: f32,
}

impl DevelopmentalProgram {
    /// Sigmoid squash: 1 / (1 + e^(-x)).
    fn sigmoid(x: f32) -> f32 {
        1.0 / (1.0 + (-x).exp())
    }

    /// Linearly maps sigmoid output [0,1] to [lo, hi].
    fn map_range(sig: f32, lo: f32, hi: f32) -> f32 {
        lo + sig * (hi - lo)
    }

    /// Decode genome segment 3 (8 floats) into developmental parameters.
    pub fn decode(segment: &[f32]) -> Self {
        assert!(segment.len() >= 7, "developmental segment needs ≥7 floats");
        let s = Self::sigmoid;
        let m = Self::map_range;
        Self {
            maturation_rate_modifier: 2.0f32.powf(segment[0].clamp(-2.0, 2.0)),
            juvenile_boundary_repair: m(s(segment[1]), 0.2, 1.0),
            juvenile_sensing: m(s(segment[2]), 0.3, 1.0),
            adolescent_threshold: m(s(segment[3]), 0.3, 0.7),
            adolescent_boundary_repair: m(s(segment[4]), 0.5, 1.0),
            adolescent_sensing: m(s(segment[5]), 0.5, 1.0),
            juvenile_metabolic_efficiency: m(s(segment[6]), 0.1, 0.5),
        }
    }

    /// Returns (boundary_repair_factor, sensing_factor, metabolic_factor) for the
    /// current maturity level. Adults (maturity ≥ 1.0) always return (1.0, 1.0, 1.0).
    pub fn stage_factors(&self, maturity: f32) -> (f32, f32, f32) {
        if maturity >= 1.0 {
            return (1.0, 1.0, 1.0);
        }
        if maturity < self.adolescent_threshold {
            // Juvenile stage
            (
                self.juvenile_boundary_repair,
                self.juvenile_sensing,
                self.juvenile_metabolic_efficiency,
            )
        } else {
            // Adolescent stage — interpolate toward adult (1.0) as maturity → 1.0
            let t = (maturity - self.adolescent_threshold)
                / (1.0 - self.adolescent_threshold).max(f32::EPSILON);
            let t = t.clamp(0.0, 1.0);
            let mid = (self.juvenile_metabolic_efficiency + 1.0) * 0.5;
            (
                self.adolescent_boundary_repair + t * (1.0 - self.adolescent_boundary_repair),
                self.adolescent_sensing + t * (1.0 - self.adolescent_sensing),
                mid + t * (1.0 - mid),
            )
        }
    }
}

impl Default for DevelopmentalProgram {
    /// Default matches decode of an all-zero genome segment:
    /// sigmoid(0.0) = 0.5, maturation_rate_modifier = 2^0 = 1.0.
    fn default() -> Self {
        Self::decode(&[0.0; 8])
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
    /// Decoded developmental program from genome segment 3.
    pub developmental_program: DevelopmentalProgram,
    /// Stable ID of the parent organism (None for bootstrap organisms).
    pub parent_stable_id: Option<u64>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn decode_zero_genome_matches_default() {
        let from_decode = DevelopmentalProgram::decode(&[0.0; 8]);
        let from_default = DevelopmentalProgram::default();
        assert!(
            (from_decode.maturation_rate_modifier - from_default.maturation_rate_modifier).abs()
                < f32::EPSILON
        );
        assert!(
            (from_decode.juvenile_boundary_repair - from_default.juvenile_boundary_repair).abs()
                < f32::EPSILON
        );
        assert!(
            (from_decode.juvenile_sensing - from_default.juvenile_sensing).abs() < f32::EPSILON
        );
        assert!(
            (from_decode.adolescent_threshold - from_default.adolescent_threshold).abs()
                < f32::EPSILON
        );
    }

    #[test]
    fn stage_factors_adult_returns_all_ones() {
        let dp = DevelopmentalProgram::default();
        let (b, s, m) = dp.stage_factors(1.0);
        assert!((b - 1.0).abs() < f32::EPSILON);
        assert!((s - 1.0).abs() < f32::EPSILON);
        assert!((m - 1.0).abs() < f32::EPSILON);
    }

    #[test]
    fn stage_factors_juvenile_returns_reduced() {
        let dp = DevelopmentalProgram::default();
        // Default adolescent_threshold ≈ 0.5, so maturity=0.1 is juvenile
        let (b, s, m) = dp.stage_factors(0.1);
        assert!(b < 1.0, "juvenile boundary should be reduced: {b}");
        assert!(s < 1.0, "juvenile sensing should be reduced: {s}");
        assert!(m < 1.0, "juvenile metabolic should be reduced: {m}");
    }

    #[test]
    fn stage_factors_adolescent_intermediate() {
        let dp = DevelopmentalProgram::default();
        let (b_juv, s_juv, m_juv) = dp.stage_factors(0.1);
        let (b_ado, s_ado, m_ado) = dp.stage_factors(0.7);
        assert!(b_ado > b_juv, "adolescent boundary > juvenile");
        assert!(s_ado > s_juv, "adolescent sensing > juvenile");
        assert!(m_ado > m_juv, "adolescent metabolic > juvenile");
        assert!(b_ado < 1.0, "adolescent boundary < adult");
        assert!(s_ado < 1.0, "adolescent sensing < adult");
    }

    #[test]
    fn maturation_rate_modifier_positive_speeds_up() {
        let dp = DevelopmentalProgram::decode(&[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]);
        assert!(
            dp.maturation_rate_modifier > 1.0,
            "positive g[0] should speed up: {}",
            dp.maturation_rate_modifier
        );
    }

    #[test]
    fn maturation_rate_modifier_negative_slows_down() {
        let dp = DevelopmentalProgram::decode(&[-1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]);
        assert!(
            dp.maturation_rate_modifier < 1.0,
            "negative g[0] should slow down: {}",
            dp.maturation_rate_modifier
        );
    }
}
