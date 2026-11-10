use pyo3::prelude::*;
use pyo3::types::PyAny;

/// Initial native module smoke-test.
///
/// The public compatibility API will be implemented only after the Python
/// object adapter preserves Python-specific types and semantics.
#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[pyfunction]
fn diff_json(old_json: &str, new_json: &str) -> PyResult<String> {
    let old: deepdiff_core::Value = serde_json::from_str(old_json)
        .map_err(|err| pyo3::exceptions::PyValueError::new_err(err.to_string()))?;
    let new: deepdiff_core::Value = serde_json::from_str(new_json)
        .map_err(|err| pyo3::exceptions::PyValueError::new_err(err.to_string()))?;

    let changes = deepdiff_core::diff(&old, &new);
    serde_json::to_string(&changes)
        .map_err(|err| pyo3::exceptions::PyRuntimeError::new_err(err.to_string()))
}

#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(version, module)?)?;
    module.add_function(wrap_pyfunction!(diff_json, module)?)?;
    Ok(())
}
