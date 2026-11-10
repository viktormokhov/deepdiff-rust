//! The Python-facing DeepDiff class, adapted from the pinned Onix revision.
//! The only local change is the public module name: `deepdiff`.

use onix_core::Value;
use onix_core::diff::Resolution;
use pyo3::prelude::*;

use crate::convert::{
    Held, objects_by_identity, render_report, resolve_token, to_value, token_error,
    value_to_pyobject,
};
use crate::guard::{diff_to_value, is_deep, resolve_options, run_on_worker, serialize_value};

#[pyclass(module = "deepdiff")]
pub(crate) struct DeepDiff {
    report_value: Value,
    report_is_deep: bool,
    max_depth: usize,
    may_have_wtf8: bool,
}

#[pymethods]
impl DeepDiff {
    #[new]
    #[pyo3(signature = (t1, t2, ignore_order=false, max_depth=None))]
    fn new(
        py: Python<'_>,
        t1: &Bound<'_, PyAny>,
        t2: &Bound<'_, PyAny>,
        ignore_order: bool,
        max_depth: Option<usize>,
    ) -> PyResult<Self> {
        let opts = resolve_options(max_depth, ignore_order)?;
        let mut held = Held::new(opts.max_depth);
        let (a, a_may_have_wtf8) = to_value(t1, opts.max_depth, &mut held)?;
        let (b, b_may_have_wtf8) = to_value(t2, opts.max_depth, &mut held)?;
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
                diff_to_value(py, a, b, opts, &mut resolver, deep)?
            };
            if held.needs_worker && !deep {
                deep = true;
                continue;
            }
            break report_value;
        };
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
        let may_have_wtf8 = a_may_have_wtf8 || b_may_have_wtf8 || held.saw_wtf8;

        Ok(Self {
            report_value,
            report_is_deep,
            max_depth: opts.max_depth,
            may_have_wtf8,
        })
    }

    fn to_json(&self, py: Python<'_>) -> PyResult<String> {
        serialize_value(
            py,
            &self.report_value,
            self.max_depth,
            self.report_is_deep,
            self.may_have_wtf8,
        )
    }

    fn to_dict(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        value_to_pyobject(py, &self.report_value)
    }

    fn __bool__(&self) -> bool {
        !matches!(&self.report_value, Value::Object(map) if map.is_empty())
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        Ok(format!("DeepDiff({})", self.to_json(py)?))
    }
}
