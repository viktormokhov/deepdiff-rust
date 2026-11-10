//! PyO3 bindings for `deepdiff_core`, imported in Python as `deepdiff_rust`.

mod convert;
mod deepdiff;
mod errors;
mod fast_path;
mod guard;
mod verbose;

use pyo3::prelude::*;

#[pymodule]
fn _native(py: Python<'_>, module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<deepdiff::DeepDiff>()?;
    module.add_function(wrap_pyfunction!(fast_path::diff_json, module)?)?;
    module.add("MaxDepthError", py.get_type::<errors::MaxDepthError>())?;
    module.add("MAX_DEPTH_CEILING", guard::MAX_DEPTH_CEILING)?;
    module.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
