## 2026-02-16 - [Panic on Zero Radius]
**Vulnerability:** Application panic (DoS) when `sensing_radius` is 0.0, causing `rand::Rng::random_range` to panic on empty range `0.0..0.0`.
**Learning:** `rand` crate panics on empty ranges for floating point numbers. Input validation or defensive checks are necessary before generating random numbers in a range derived from configuration.
**Prevention:** Always check if the range is valid (start < end) before calling `random_range`.
