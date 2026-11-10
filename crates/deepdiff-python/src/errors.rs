//! Python-visible exceptions adapted from the pinned Onix revision.

use pyo3::create_exception;
use pyo3::exceptions::PyValueError;

create_exception!(
    deepdiff,
    MaxDepthError,
    PyValueError,
    "Raised when diffing two values would need to recurse past the configured max_depth."
);

pub(crate) fn map_diff_error(error: &onix_core::Error) -> pyo3::PyErr {
    match error {
        onix_core::Error::MaxDepthExceeded { .. } => MaxDepthError::new_err(error.to_string()),
        onix_core::Error::DateTimeOutOfRange { .. } => PyValueError::new_err(error.to_string()),
    }
}
