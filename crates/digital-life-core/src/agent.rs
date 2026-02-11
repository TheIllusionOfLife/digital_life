use rstar::{RTreeObject, AABB};

#[derive(Clone, Debug)]
pub struct Agent {
    pub id: u32,
    pub organism_id: u16,
    pub position: [f64; 2],
    pub velocity: [f64; 2],
    pub internal_state: [f32; 4],
}

impl Agent {
    pub fn new(id: u32, organism_id: u16, position: [f64; 2]) -> Self {
        Self {
            id,
            organism_id,
            position,
            velocity: [0.0; 2],
            internal_state: [0.5; 4],
        }
    }
}

impl RTreeObject for Agent {
    type Envelope = AABB<[f64; 2]>;

    fn envelope(&self) -> Self::Envelope {
        AABB::from_point(self.position)
    }
}
