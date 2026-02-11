#[derive(Clone, Debug)]
pub struct MetabolicState {
    pub energy: f32,
    pub resource: f32,
    pub waste: f32,
}

impl Default for MetabolicState {
    fn default() -> Self {
        Self {
            energy: 0.5,
            resource: 5.0,
            waste: 0.0,
        }
    }
}

#[derive(Clone, Debug)]
pub struct ToyMetabolism {
    pub uptake_rate: f32,
    pub conversion_efficiency: f32,
    pub waste_ratio: f32,
    pub energy_loss_rate: f32,
    pub max_energy: f32,
    pub waste_decay_rate: f32,
    pub max_waste: f32,
}

impl Default for ToyMetabolism {
    fn default() -> Self {
        Self {
            uptake_rate: 0.4,
            conversion_efficiency: 0.8,
            waste_ratio: 0.2,
            energy_loss_rate: 0.02,
            max_energy: 1.0,
            waste_decay_rate: 0.05,
            max_waste: 1.0,
        }
    }
}

impl ToyMetabolism {
    pub fn step(&self, state: &mut MetabolicState, dt: f32) {
        let uptake = (self.uptake_rate * dt).min(state.resource).max(0.0);
        state.resource -= uptake;
        state.energy += uptake * self.conversion_efficiency;
        state.waste += uptake * self.waste_ratio;
        state.waste = (state.waste - self.waste_decay_rate * dt).clamp(0.0, self.max_waste);

        // Minimal thermodynamic loss to avoid unbounded free energy growth.
        let retained = (1.0 - self.energy_loss_rate * dt).clamp(0.0, 1.0);
        state.energy = (state.energy * retained).clamp(0.0, self.max_energy);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn energy_is_bounded() {
        let mut state = MetabolicState::default();
        let metabolism = ToyMetabolism {
            uptake_rate: 10.0,
            conversion_efficiency: 1.0,
            energy_loss_rate: 0.0,
            ..ToyMetabolism::default()
        };
        for _ in 0..100 {
            state.resource += 10.0;
            metabolism.step(&mut state, 1.0);
        }
        assert!(
            (0.0..=metabolism.max_energy).contains(&state.energy),
            "energy out of bounds: {}",
            state.energy
        );
    }

    #[test]
    fn waste_is_bounded() {
        let mut state = MetabolicState::default();
        let metabolism = ToyMetabolism {
            uptake_rate: 10.0,
            waste_ratio: 1.0,
            waste_decay_rate: 0.0,
            ..ToyMetabolism::default()
        };
        for _ in 0..100 {
            state.resource += 10.0;
            metabolism.step(&mut state, 1.0);
        }
        assert!(
            (0.0..=metabolism.max_waste).contains(&state.waste),
            "waste out of bounds: {}",
            state.waste
        );
    }
}
