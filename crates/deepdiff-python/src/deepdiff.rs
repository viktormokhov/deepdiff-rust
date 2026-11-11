//! The drop-in `DeepDiff` class: accepts live Python objects, converts them
//! to `deepdiff_core`'s value model exactly once, diffs natively, and exposes
//! the result as `.to_json()`/`.to_dict()`. Supported types and raised
//! errors: the README's "Known limitations" section.

use deepdiff_core::diff::Resolution;
use deepdiff_core::path::{PathSegment, render_path};
use deepdiff_core::{DiffOptions, Value};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyType};
use std::borrow::Cow;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use crate::convert::{
    Held, objects_by_identity, render_report, resolve_token, to_value, token_error,
    value_to_pyobject,
};
use crate::guard::{diff_to_value, is_deep, resolve_options, run_on_worker, serialize_value};
use crate::verbose::at_verbose_level;

/// A drop-in subset of `deepdiff.DeepDiff`, diffing `t1`/`t2` at
/// `verbose_level=2`. `max_depth` defaults to 512; deeper input raises
/// `MaxDepthError`. Supported types and errors:
/// <https://github.com/ksco92/onix#known-limitations>
#[pyclass(module = "deepdiff_rust")]
pub(crate) struct DeepDiff {
    report_value: Value,
    /// Whether `report_value` needs the worker thread to render; computed once
    /// so `to_json` never re-walks it. See `crate::guard::is_deep`.
    report_is_deep: bool,
    /// The resolved `max_depth`, which bounds the report's nesting.
    max_depth: usize,
    /// Whether either input held a lone surrogate code point, found during
    /// conversion; lets `to_json` skip its own WTF-8 tree walk when `false`.
    may_have_wtf8: bool,
    /// See `crate::convert::Held::types`.
    types: HashMap<Arc<str>, Py<PyType>>,
    /// `get_deep_distance`'s result, `None` when not asked for.
    #[pyo3(get)]
    deep_distance: Option<f64>,
}

#[pymethods]
impl DeepDiff {
    #[new]
    #[pyo3(signature = (t1, t2, ignore_order=false, max_depth=None, exclude_types=None, ignore_private_variables=true, skip=None, significant_digits=None, exponent_notation=false, math_epsilon=None, log_scale_threshold=None, ignore_nan_inequality=false, ignore_string_case=false, ignore_numeric_type_changes=false, type_groups=None, group_mask=None, truncate_datetime=None, use_enum_value=false, threshold_to_diff_deeper=0.33, cutoff_distance_for_pairs=0.3, cutoff_intersection_for_pairs=0.7, zip_ordered_iterables=false, get_deep_distance=false, report_repetition=false, max_diffs=None, max_passes=10_000_000))]
    #[allow(clippy::too_many_arguments)] // mirrors the Python keyword signature
    fn new(
        py: Python<'_>,
        t1: &Bound<'_, PyAny>,
        t2: &Bound<'_, PyAny>,
        ignore_order: bool,
        max_depth: Option<usize>,
        exclude_types: Option<Bound<'_, PyAny>>,
        ignore_private_variables: bool,
        skip: Option<Py<PyAny>>,
        significant_digits: Option<usize>,
        exponent_notation: bool,
        math_epsilon: Option<f64>,
        log_scale_threshold: Option<f64>,
        ignore_nan_inequality: bool,
        ignore_string_case: bool,
        ignore_numeric_type_changes: bool,
        type_groups: Option<HashMap<String, u64>>,
        group_mask: Option<Py<PyAny>>,
        truncate_datetime: Option<Py<PyDict>>,
        use_enum_value: bool,
        threshold_to_diff_deeper: f64,
        cutoff_distance_for_pairs: f64,
        cutoff_intersection_for_pairs: f64,
        zip_ordered_iterables: bool,
        get_deep_distance: bool,
        report_repetition: bool,
        max_diffs: Option<usize>,
        max_passes: usize,
    ) -> PyResult<Self> {
        let mut opts = DiffOptions {
            significant_digits,
            exponent_notation,
            math_epsilon,
            log_scale_threshold,
            ignore_nan_inequality,
            ignore_string_case,
            ignore_numeric_type_changes,
            use_enum_value,
            threshold_to_diff_deeper,
            cutoff_distance_for_pairs,
            cutoff_intersection_for_pairs,
            zip_ordered_iterables,
            get_deep_distance,
            report_repetition,
            max_diffs,
            max_passes,
            ..resolve_options(max_depth, ignore_order)?
        };
        let mut held = Held::new(opts.max_depth);
        held.exclude_types = exclude_types.map(Bound::unbind);
        held.truncate_datetime = truncate_datetime;
        let (a, a_may_have_wtf8) = to_value(t1, opts.max_depth, &mut held)?;
        let (b, b_may_have_wtf8) = to_value(t2, opts.max_depth, &mut held)?;
        // A class attribute or cycle token is resolved the first time the
        // diff compares one, then the diff reruns with it available.
        if let Some(group_mask) = &group_mask {
            let mut groups: HashMap<Box<str>, u64> = type_groups
                .unwrap_or_default()
                .into_iter()
                .map(|(name, mask)| (name.into(), mask))
                .collect();
            for (name, class) in &held.types {
                let mask = group_mask.call1(py, (class,))?.extract(py)?;
                groups.insert(name.as_ref().into(), mask);
            }
            opts.type_groups = Some(Arc::new(groups));
        }
        // ponytail: filters drop findings after the diff instead of pruning it, so an
        // excluded part still pairs under ignore_order; prune in the core if that matters.
        let excluded = std::mem::take(&mut held.excluded);
        let skip_error = Mutex::new(None);
        let keep = |path: &[PathSegment]| {
            if ignore_private_variables && path.iter().any(is_private_key) {
                return false;
            }
            let Some(skip) = &skip else { return true };
            let prefixes: Vec<String> = (0..=path.len())
                .map(|k| render_path(&path[..k]).to_string())
                .collect();
            let typed: Vec<bool> = (0..=path.len())
                .map(|k| excluded.contains(&path[..k]))
                .collect();
            Python::attach(|py| {
                match skip
                    .call1(py, (prefixes, typed))
                    .and_then(|r| r.is_truthy(py))
                {
                    Ok(skipped) => !skipped,
                    Err(err) => {
                        skip_error
                            .lock()
                            .expect("never poisoned")
                            .get_or_insert(err);
                        true
                    }
                }
            })
        };
        let mut index = None;
        let mut deep = false;
        let report_value = loop {
            let report_value = {
                let held = &mut held;
                let index = &mut index;
                let (a, b) = (&a, &b);
                let mut resolver = |identity: &str| {
                    if held.cycle_targets.contains(identity) {
                        let index = index.get_or_insert_with(|| objects_by_identity(&[a, b]));
                        if let Some(value) = index.get(identity) {
                            return Some(Resolution::Borrowed(value));
                        }
                    }
                    Python::attach(|py| resolve_token(py, identity, held, !deep))
                        .map(Resolution::Shared)
                };
                diff_to_value(py, a, b, &opts, &mut resolver, deep, Some(&keep))?
            };
            if held.needs_worker && !deep {
                deep = true;
                continue;
            }
            break report_value;
        };
        let (report_value, deep_distance) = report_value;
        if let Some(err) = skip_error.lock().expect("never poisoned").take() {
            return Err(err);
        }
        if let Some(err) = held.interrupt(py) {
            return Err(err);
        }
        let report_value = if held.needs_render {
            let rendered = if is_deep(&report_value) {
                run_on_worker(py, opts.max_depth, || render_report(&report_value))?
            } else {
                render_report(&report_value)
            };
            match rendered {
                Ok(rendered) => rendered,
                Err(tokens) => {
                    let token = &tokens[0];
                    return Err(token_error(
                        py,
                        &token.identity,
                        &token.type_name,
                        &token.path,
                        &held,
                    ));
                }
            }
        } else {
            report_value
        };
        let report_is_deep = is_deep(&report_value);
        // Conservative: the report only ever carries values already in
        // `t1`/`t2`, so this may overcount but never undercounts.
        let may_have_wtf8 = a_may_have_wtf8 || b_may_have_wtf8 || held.saw_wtf8;

        Ok(Self {
            report_value,
            report_is_deep,
            max_depth: opts.max_depth,
            may_have_wtf8,
            types: std::mem::take(&mut held.types),
            deep_distance,
        })
    }

    /// The report as a `DeepDiff`-compatible JSON string at the given
    /// `verbose_level`; a deep report renders on the sized worker thread
    /// rather than inline. Differences from `DeepDiff`'s rendering are
    /// documented in the onix repository's `tests/golden/README.md`, 'JSON
    /// supersets' and 'Set iteration order' sections.
    #[pyo3(signature = (verbose_level=2))]
    fn to_json(&self, py: Python<'_>, verbose_level: u8) -> PyResult<String> {
        serialize_value(
            py,
            &*self.at_level(py, verbose_level)?,
            self.max_depth,
            self.report_is_deep,
            self.may_have_wtf8,
        )
    }

    /// The report as a native Python dict, Python types (tuples, sets,
    /// datetimes) intact. Differences from `DeepDiff`'s `to_dict()`:
    /// `tests/golden/README.md` in the onix repository.
    #[pyo3(signature = (verbose_level=2))]
    fn to_dict(&self, py: Python<'_>, verbose_level: u8) -> PyResult<Py<PyAny>> {
        value_to_pyobject(py, &*self.at_level(py, verbose_level)?, &self.types)
    }

    /// `if diff:` truthiness — falsy exactly when `t1`/`t2` had no
    /// differences (an empty report).
    fn __bool__(&self) -> bool {
        !is_empty_report(&self.report_value)
    }

    /// The subclass and custom classes seen in `t1`/`t2`, by `__name__`.
    #[getter]
    fn _types<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let types = PyDict::new(py);
        for (name, class) in &self.types {
            types.set_item(name.as_ref(), class.bind(py))?;
        }
        Ok(types)
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        Ok(format!("DeepDiff({})", self.to_json(py, 2)?))
    }
}

impl DeepDiff {
    /// The report at `verbose_level`, re-rendered on the sized worker when deep.
    fn at_level(&self, py: Python<'_>, verbose_level: u8) -> PyResult<Cow<'_, Value>> {
        if verbose_level >= 2 {
            return Ok(Cow::Borrowed(&self.report_value));
        }
        let render = || at_verbose_level(&self.report_value, verbose_level);
        Ok(Cow::Owned(if self.report_is_deep {
            run_on_worker(py, self.max_depth, render)?
        } else {
            render()
        }))
    }
}

fn is_empty_report(value: &Value) -> bool {
    matches!(value, Value::Object(map) if map.is_empty())
}

/// A `str` dict key `ignore_private_variables` hides: one starting `__`.
fn is_private_key(segment: &PathSegment) -> bool {
    matches!(segment, PathSegment::Key(key) if key.as_bytes().starts_with(b"__"))
}
