/// Variable-length genome encoding all 7 criteria.
/// Only NN weights are active initially; other segments are zero-initialized
/// and will be activated as criteria are implemented.

#[derive(Clone, Debug)]
pub struct Genome {
    pub data: Vec<f32>,
    /// Segment layout: (start, len) for each criterion's parameters.
    /// Index 0 = NN weights, 1 = metabolic network, 2 = homeostasis params,
    /// 3 = developmental program, 4 = reproduction params, 5 = sensory params,
    /// 6 = evolution/mutation params
    pub segments: [(usize, usize); 7],
}

impl Genome {
    /// Create a genome with only NN weights active (segment 0).
    pub fn with_nn_weights(nn_weights: Vec<f32>) -> Self {
        let nn_len = nn_weights.len();
        // Reserve placeholder segments for future criteria
        let placeholder_sizes = [0, 0, 0, 0, 0, 0]; // criteria 2-7

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
        let (start, len) = self.segments[0];
        &self.data[start..start + len]
    }
}
