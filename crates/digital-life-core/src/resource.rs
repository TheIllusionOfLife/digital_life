/// 2D grid resource field stub.
/// Each cell holds a resource concentration value.

#[derive(Clone, Debug)]
pub struct ResourceField {
    width: usize,
    height: usize,
    cell_size: f64,
    data: Vec<f32>,
    total: f64,
    initial_value: f32,
}

impl ResourceField {
    pub fn new(world_size: f64, cell_size: f64, initial_value: f32) -> Self {
        assert!(world_size > 0.0, "world_size must be positive");
        assert!(cell_size > 0.0, "cell_size must be positive");
        // The simulation world is currently square; use a square resource grid for parity.
        let width = (world_size / cell_size).ceil() as usize;
        let height = width;
        let data = vec![initial_value; width * height];
        let total = initial_value as f64 * (width * height) as f64;
        Self {
            width,
            height,
            cell_size,
            data,
            total,
            initial_value,
        }
    }

    /// Regenerate resources toward the initial value at the given rate per step.
    pub fn regenerate(&mut self, rate: f32) {
        for cell in &mut self.data {
            let before = *cell;
            *cell = (*cell + rate).min(self.initial_value);
            self.total += (*cell - before) as f64;
        }
    }

    /// Get resource value at position. Coordinates wrap toroidally.
    pub fn get(&self, x: f64, y: f64) -> f32 {
        let (cx, cy) = self.wrap_coords(x, y);
        self.data[cy * self.width + cx]
    }

    /// Set resource value at position. Coordinates wrap toroidally.
    pub fn set(&mut self, x: f64, y: f64, value: f32) {
        let (cx, cy) = self.wrap_coords(x, y);
        let idx = cy * self.width + cx;
        let old = self.data[idx];
        self.data[idx] = value;
        self.total += (value - old) as f64;
    }

    /// Remove up to `amount` resource from the addressed cell and return actual amount withdrawn.
    pub fn take(&mut self, x: f64, y: f64, amount: f32) -> f32 {
        let (cx, cy) = self.wrap_coords(x, y);
        let idx = cy * self.width + cx;
        let removed = self.data[idx].min(amount.max(0.0));
        self.data[idx] -= removed;
        self.total -= removed as f64;
        removed
    }

    pub fn width(&self) -> usize {
        self.width
    }

    pub fn height(&self) -> usize {
        self.height
    }

    pub fn cell_size(&self) -> f64 {
        self.cell_size
    }

    pub fn data(&self) -> &[f32] {
        &self.data
    }

    pub fn total(&self) -> f64 {
        self.total
    }

    fn wrap_coords(&self, x: f64, y: f64) -> (usize, usize) {
        let cx = ((x / self.cell_size).floor() as isize).rem_euclid(self.width as isize) as usize;
        let cy = ((y / self.cell_size).floor() as isize).rem_euclid(self.height as isize) as usize;
        (cx, cy)
    }

    #[allow(dead_code)]
    fn clamp_coords(&self, x: f64, y: f64) -> (usize, usize) {
        let cx = ((x / self.cell_size).max(0.0) as usize).min(self.width - 1);
        let cy = ((y / self.cell_size).max(0.0) as usize).min(self.height - 1);
        (cx, cy)
    }
}

#[cfg(test)]
mod tests {
    use super::ResourceField;

    #[test]
    fn wraps_coordinates_toroidally() {
        let mut field = ResourceField::new(10.0, 1.0, 0.0);
        field.set(9.0, 9.0, 3.0);
        assert!((field.get(-1.0, -1.0) - 3.0).abs() < f32::EPSILON);
        assert!((field.get(19.0, 19.0) - 3.0).abs() < f32::EPSILON);
    }

    #[test]
    fn take_withdraws_and_clamps_to_available() {
        let mut field = ResourceField::new(10.0, 1.0, 0.0);
        field.set(2.0, 3.0, 1.5);
        assert!((field.take(2.0, 3.0, 0.5) - 0.5).abs() < f32::EPSILON);
        assert!((field.get(2.0, 3.0) - 1.0).abs() < f32::EPSILON);
        assert!((field.take(2.0, 3.0, 5.0) - 1.0).abs() < f32::EPSILON);
        assert!((field.get(2.0, 3.0) - 0.0).abs() < f32::EPSILON);
    }

    #[test]
    fn total_tracks_updates_and_withdrawals() {
        let mut field = ResourceField::new(10.0, 1.0, 1.0);
        let initial = field.total();
        field.set(0.0, 0.0, 2.0);
        assert!((field.total() - (initial + 1.0)).abs() < 1e-6);
        let _ = field.take(0.0, 0.0, 0.5);
        assert!((field.total() - (initial + 0.5)).abs() < 1e-6);
    }

    #[test]
    fn regenerate_restores_depleted_cells() {
        let mut field = ResourceField::new(10.0, 1.0, 1.0);
        field.set(3.0, 3.0, 0.0);
        field.regenerate(0.25);
        assert!((field.get(3.0, 3.0) - 0.25).abs() < f32::EPSILON);
    }

    #[test]
    fn regenerate_caps_at_initial_value() {
        let mut field = ResourceField::new(10.0, 1.0, 1.0);
        field.regenerate(0.5);
        // Already at 1.0 (initial), should stay at 1.0
        assert!((field.get(0.0, 0.0) - 1.0).abs() < f32::EPSILON);
    }

    #[test]
    fn resource_total_tracks_regeneration() {
        let mut field = ResourceField::new(10.0, 1.0, 1.0);
        field.set(0.0, 0.0, 0.0);
        let before = field.total();
        field.regenerate(0.5);
        assert!(field.total() > before);
    }
}
