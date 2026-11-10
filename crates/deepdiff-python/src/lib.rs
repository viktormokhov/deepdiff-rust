//! PyO3 bindings. The conversion and JSON fast-path modules are pinned to the
//! Onix submodule revision recorded in docs/architecture/adr-0001-onix-core.md.

#[allow(dead_code)]
#[path = "../../../vendor/onix/crates/onix-py/src/convert.rs"]
mod convert;
mod deepdiff;
mod errors;
#[path = "../../../vendor/onix/crates/onix-py/src/fast_path.rs"]
mod fast_path;
#[path = "../../../vendor/onix/crates/onix-py/src/guard.rs"]
mod guard;

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
