/// 2D grid resource field stub.
/// Each cell holds a resource concentration value.

#[derive(Clone, Debug)]
pub struct ResourceField {
    pub width: usize,
    pub height: usize,
    pub cell_size: f64,
    pub data: Vec<f32>,
}

impl ResourceField {
    pub fn new(world_size: f64, cell_size: f64, initial_value: f32) -> Self {
        let width = (world_size / cell_size).ceil() as usize;
        let height = width;
        let data = vec![initial_value; width * height];
        Self {
            width,
            height,
            cell_size,
            data,
        }
    }

    pub fn get(&self, x: f64, y: f64) -> f32 {
        let cx = ((x / self.cell_size) as usize).min(self.width - 1);
        let cy = ((y / self.cell_size) as usize).min(self.height - 1);
        self.data[cy * self.width + cx]
    }

    pub fn set(&mut self, x: f64, y: f64, value: f32) {
        let cx = ((x / self.cell_size) as usize).min(self.width - 1);
        let cy = ((y / self.cell_size) as usize).min(self.height - 1);
        self.data[cy * self.width + cx] = value;
    }
}
