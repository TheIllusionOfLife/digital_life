use rand::SeedableRng;
use rand_chacha::ChaCha12Rng;

/// Create a deterministic RNG from a seed.
pub fn create_rng(seed: u64) -> ChaCha12Rng {
    ChaCha12Rng::seed_from_u64(seed)
}

/// Derive a sub-RNG for a specific organism, ensuring independent streams.
pub fn derive_organism_rng(base_seed: u64, organism_id: usize) -> ChaCha12Rng {
    ChaCha12Rng::seed_from_u64(base_seed.wrapping_add(organism_id as u64 * 7919))
}
