use rand::Rng;

/// Variable-length genome encoding all 7 criteria.
/// Only NN weights are active initially; other segments are zero-initialized
/// and will be activated as criteria are implemented.

#[derive(Clone, Debug)]
pub struct Genome {
    data: Vec<f32>,
    /// Segment layout: (start, len) for each criterion's parameters.
    /// Index 0 = NN weights, 1 = metabolic network, 2 = homeostasis params,
    /// 3 = developmental program, 4 = reproduction params, 5 = sensory params,
    /// 6 = evolution/mutation params
    segments: [(usize, usize); 7],
}

impl Genome {
    /// Create a genome with only NN weights active (segment 0).
    pub fn with_nn_weights(nn_weights: Vec<f32>) -> Self {
        let nn_len = nn_weights.len();
        // Segment sizes for criteria 1-6 (segment 0 = NN weights, handled above):
        // 1: Metabolic network params (graph node/edge encoding)
        // 2: Homeostasis params (set-points, gain values)
        // 3: Developmental program (growth schedule)
        // 4: Reproduction params (thresholds)
        // 5: Sensory params (sensitivity weights)
        // 6: Evolution/mutation rate params (self-referential)
        let placeholder_sizes = [16, 8, 8, 4, 4, 4];

        let total_len: usize = nn_len + placeholder_sizes.iter().sum::<usize>();
        let mut data = Vec::with_capacity(total_len);
        data.extend_from_slice(&nn_weights);
        // Zero-fill remaining segments
        data.resize(total_len, 0.0);

        let mut segments = [(0usize, 0usize); 7];
        segments[0] = (0, nn_len);
        let mut offset = nn_len;
        for (i, &size) in placeholder_sizes.iter().enumerate() {
            segments[i + 1] = (offset, size);
            offset += size;
        }

        Self { data, segments }
    }

    pub fn nn_weights(&self) -> &[f32] {
        self.segment_data(0)
    }

    /// Returns the parameter slice for a criterion segment (0..=6).
    pub fn segment_data(&self, criterion: usize) -> &[f32] {
        assert!(
            criterion < self.segments.len(),
            "criterion index out of range"
        );
        let (start, len) = self.segments[criterion];
        &self.data[start..start + len]
    }

    pub fn data(&self) -> &[f32] {
        &self.data
    }

    pub fn segments(&self) -> &[(usize, usize); 7] {
        &self.segments
    }

    pub fn mutate<R: Rng + ?Sized>(&mut self, rng: &mut R, rates: &MutationRates) {
        debug_assert!(
            rates.point_rate + rates.reset_rate + rates.scale_rate <= 1.0,
            "mutation probabilities should sum to <= 1.0"
        );
        for v in &mut self.data {
            let r = rng.random::<f32>();
            if r < rates.point_rate {
                let delta = rng.random_range(-rates.point_scale..=rates.point_scale);
                *v = (*v + delta).clamp(-rates.value_limit, rates.value_limit);
            } else if r < rates.point_rate + rates.reset_rate {
                *v = 0.0;
            } else if r < rates.point_rate + rates.reset_rate + rates.scale_rate {
                let factor = rng.random_range(rates.scale_min..=rates.scale_max);
                *v = (*v * factor).clamp(-rates.value_limit, rates.value_limit);
            }
        }
    }
}

#[derive(Clone, Copy, Debug)]
pub struct MutationRates {
    pub point_rate: f32,
    pub point_scale: f32,
    pub reset_rate: f32,
    pub scale_rate: f32,
    pub scale_min: f32,
    pub scale_max: f32,
    pub value_limit: f32,
}

impl Default for MutationRates {
    fn default() -> Self {
        Self {
            point_rate: 0.02,
            point_scale: 0.15,
            reset_rate: 0.002,
            scale_rate: 0.002,
            scale_min: 0.8,
            scale_max: 1.2,
            value_limit: 2.0,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::SeedableRng;
    use rand_chacha::ChaCha12Rng;

    #[test]
    fn mutation_is_deterministic_for_fixed_seed() {
        let mut a = Genome::with_nn_weights(vec![0.5; 16]);
        let mut b = Genome::with_nn_weights(vec![0.5; 16]);
        let mut rng_a = ChaCha12Rng::seed_from_u64(123);
        let mut rng_b = ChaCha12Rng::seed_from_u64(123);
        let rates = MutationRates::default();
        a.mutate(&mut rng_a, &rates);
        b.mutate(&mut rng_b, &rates);
        assert_eq!(a.data(), b.data());
    }

    #[test]
    fn mutation_respects_value_bounds() {
        let mut g = Genome::with_nn_weights(vec![1.5; 32]);
        let mut rng = ChaCha12Rng::seed_from_u64(42);
        let rates = MutationRates::default();
        for _ in 0..100 {
            g.mutate(&mut rng, &rates);
        }
        assert!(g
            .data()
            .iter()
            .all(|v| v.is_finite() && (-rates.value_limit..=rates.value_limit).contains(v)));
    }

    #[test]
    fn segment_layout_has_correct_sizes() {
        let nn_len = 212;
        let g = Genome::with_nn_weights(vec![0.0; nn_len]);
        let segs = g.segments();
        assert_eq!(segs[0], (0, 212), "segment 0: NN weights");
        assert_eq!(segs[1], (212, 16), "segment 1: metabolic network");
        assert_eq!(segs[2], (228, 8), "segment 2: homeostasis");
        assert_eq!(segs[3], (236, 8), "segment 3: developmental program");
        assert_eq!(segs[4], (244, 4), "segment 4: reproduction");
        assert_eq!(segs[5], (248, 4), "segment 5: sensory");
        assert_eq!(segs[6], (252, 4), "segment 6: evolution/mutation");
        assert_eq!(g.data().len(), 256, "total genome length");
    }

    #[test]
    fn segment_data_returns_correct_slices() {
        let g = Genome::with_nn_weights(vec![1.0; 212]);
        assert_eq!(g.segment_data(1).len(), 16);
        assert!(
            g.segment_data(1).iter().all(|&v| v == 0.0),
            "non-NN segments zero-initialized"
        );
        assert_eq!(g.segment_data(4).len(), 4);
    }

    #[test]
    fn mutation_covers_all_segments() {
        let mut g = Genome::with_nn_weights(vec![0.0; 212]);
        let mut rng = ChaCha12Rng::seed_from_u64(99);
        let rates = MutationRates {
            point_rate: 0.5,
            point_scale: 1.0,
            ..MutationRates::default()
        };
        g.mutate(&mut rng, &rates);
        let non_nn_changed = g.data()[212..].iter().any(|&v| v != 0.0);
        assert!(non_nn_changed, "mutation should affect non-NN segments too");
    }
}
