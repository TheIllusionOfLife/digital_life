use pyo3::prelude::*;

/// Minimal PyO3 module exposing digital-life-core to Python.
#[pyfunction]
fn version() -> &'static str {
    "0.1.0"
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(version, m)?)?;
    Ok(())
}
