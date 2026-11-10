//! Python-visible exception types this crate raises, plus the shared
//! mapping from an [`deepdiff_core::Error`] to one of them.

use pyo3::create_exception;
use pyo3::exceptions::PyValueError;

create_exception!(
    deepdiff_rust,
    MaxDepthError,
    PyValueError,
    "Raised when diffing two values would need to recurse past the configured `max_depth`. A \
     `ValueError` subclass, so callers that only catch `ValueError` still catch this."
);

/// Maps an [`deepdiff_core::Error`] to the [`pyo3::PyErr`] a Python caller sees.
pub(crate) fn map_diff_error(error: &deepdiff_core::Error) -> pyo3::PyErr {
    match error {
        deepdiff_core::Error::MaxDepthExceeded { .. } => MaxDepthError::new_err(error.to_string()),
        deepdiff_core::Error::DateTimeOutOfRange { .. } => PyValueError::new_err(error.to_string()),
    }
}
