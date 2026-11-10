//! `DeepDiff(..., ignore_order=True)`'s list-matching algorithm, called
//! from [`crate::diff::array_diff`] whenever
//! [`crate::diff::DiffOptions::ignore_order`] is set. See
//! `docs/design/ignore-order.md` for the full algorithm.
//!
//! - **Hash** — reduce each list to a canonical equivalence key per item.
//! - **Pair** — gate on overlap, then greedily match by structural distance.
//! - **Distance** — rank candidate pairs; never an equality check.

mod distance;
mod fxhash;
mod hash;
mod memo;
mod pairing;

pub(crate) use distance::THRESHOLD_TO_DIFF_DEEPER;
pub(crate) use memo::IgnoreOrderMemo;
pub(crate) use pairing::CUTOFF_DISTANCE_FOR_PAIRS;

#[cfg(test)]
#[path = "tests.rs"]
mod tests;

use crate::value::Value;

use crate::diff::{DiffOptions, check_value_depth, diff_at, scoped};
use crate::error::Error;
use crate::path::PathSegment;
use crate::report::Report;

use fxhash::{HashMap, HashSet};
use std::rc::Rc;

use hash::{HashedList, ItemKey};
use pairing::compute_pairs;

pub(crate) use distance::{
    deep_distance, is_below_threshold_to_diff_deeper, item_length, match_dict_keys,
    type_change_leaf_length,
};
pub(crate) use hash::set_difference;
#[cfg(test)]
pub(crate) use hash::set_member_digest;

/// `cutoff_intersection_for_pairs`'s default (`DeepDiff`'s own name;
/// `CUTOFF_INTERSECTION_FOR_PAIRS_DEFAULT`, diff.py): the get-pairs gate threshold.
pub(crate) const CUTOFF_INTERSECTION_FOR_PAIRS: f64 = 0.7;

/// `DeepDiff`'s `_diff_iterable_with_deephash` (diff.py) for one list level.
pub(crate) fn ignore_order_array_diff(
    path: &mut Vec<PathSegment>,
    a: &[Value],
    b: &[Value],
    depth: usize,
    opts: &DiffOptions,
    memo: &IgnoreOrderMemo,
) -> Result<Report, Error> {
    // Every item will be structurally hashed (`item_key`, native recursion)
    // and, if left unpaired, cloned whole into the Report — both unbounded
    // native recursion unless validated first. See `docs/design/ignore-order.md`'s
    // "Depth safety" section. Checked at each side's own eventual path (its
    // own original index) so a MaxDepthExceeded error points at exactly the
    // item that tripped it.
    for (idx, item) in a.iter().enumerate().chain(b.iter().enumerate()) {
        scoped(path, PathSegment::Index(idx), |path| {
            check_value_depth(path, item, depth + 1, opts.max_depth)
        })?;
    }

    let t1 = HashedList::build(a, memo);
    let t2 = HashedList::build(b, memo);

    let hashes_added = unmatched(&t2, &t1);
    let hashes_removed = unmatched(&t1, &t2);

    #[allow(
        clippy::cast_precision_loss,
        reason = "distinct-hash counts are bounded by list length, far under f64's exact-integer range"
    )]
    let get_pairs = {
        let ratio = (hashes_added.len() + hashes_removed.len()) as f64
            / (t1.distinct_order.len() + t2.distinct_order.len() + 1) as f64;
        ratio <= opts.cutoff_intersection_for_pairs && memo.take_pass(opts)
    };

    let pairs = if get_pairs {
        match compute_pairs(&hashes_added, &hashes_removed, &t1, &t2, depth, opts, memo) {
            Ok(pairs) => pairs,
            Err(error) => return Err(*error.under(path)),
        }
    } else {
        HashMap::default()
    };

    let mut report = Report::new();
    let mut consumed_removed: HashSet<Rc<ItemKey>> = HashSet::default();
    // Under `report_repetition` every index of a key is reported, and a repeated new item
    // carries no `new_path`, as `DeepDiff` reports it.
    let rep = opts.report_repetition;

    for added_key in &hashes_added {
        if memo.over_max_diffs(opts) {
            break;
        }
        let (new_idx, new_value) = t2.get(added_key);

        if let Some(removed_key) = pairs.get(added_key) {
            consumed_removed.insert(Rc::clone(removed_key));
            let (old_idx, old_value) = t1.get(removed_key);
            let (old_indexes, new_idx) = if rep {
                let single = t2.indexes(added_key).len() == 1;
                (t1.indexes(removed_key), single.then_some(new_idx))
            } else {
                (std::slice::from_ref(&old_idx), Some(new_idx))
            };
            for &old_idx in old_indexes {
                let prefix_depth = path.len();
                let sub_report = scoped(path, PathSegment::Index(old_idx), |path| {
                    let mut sub = diff_at(path, old_value, new_value, depth, opts, memo)?;
                    // Merges this pair's own add/remove collision before
                    // retagging; independent of the whole-tree merge pass.
                    if !rep {
                        sub.merge_mutual_add_removes();
                    }
                    if let Some(new_idx) = new_idx
                        && old_idx != new_idx
                    {
                        sub.retag_new_path(prefix_depth, new_idx);
                    }
                    Ok::<Report, Error>(sub)
                })?;
                report.merge(sub_report);
            }
        } else {
            let new_indexes = if rep {
                t2.indexes(added_key)
            } else {
                std::slice::from_ref(&new_idx)
            };
            for &new_idx in new_indexes {
                scoped(path, PathSegment::Index(new_idx), |path| {
                    report.insert_iterable_item_added(path.clone(), new_value.clone());
                });
            }
        }
    }

    for removed_key in &hashes_removed {
        if consumed_removed.contains(removed_key) {
            continue;
        }
        if memo.over_max_diffs(opts) {
            break;
        }
        let (old_idx, old_value) = t1.get(removed_key);
        let old_indexes = if rep {
            t1.indexes(removed_key)
        } else {
            std::slice::from_ref(&old_idx)
        };
        for &old_idx in old_indexes {
            scoped(path, PathSegment::Index(old_idx), |path| {
                report.insert_iterable_item_removed(path.clone(), old_value.clone());
            });
        }
    }

    if rep {
        report_repetition_changes(path, &t1, &t2, &mut report);
    }

    Ok(report)
}

/// `list`'s distinct keys, in order, that `other` does not hold.
fn unmatched(list: &HashedList<'_>, other: &HashedList<'_>) -> Vec<Rc<ItemKey>> {
    list.distinct_order
        .iter()
        .filter(|key| !other.contains(key))
        .cloned()
        .collect()
}

/// `report_repetition`'s `repetition_change` for each item the two lists hold a different
/// number of times.
fn report_repetition_changes(
    path: &mut Vec<PathSegment>,
    t1: &HashedList<'_>,
    t2: &HashedList<'_>,
    report: &mut Report,
) {
    for key in t1.distinct_order.iter().filter(|key| t2.contains(key)) {
        let (old_indexes, new_indexes) = (t1.indexes(key), t2.indexes(key));
        if old_indexes.len() != new_indexes.len() {
            let value = t1.get(key).1.clone();
            scoped(path, PathSegment::Index(old_indexes[0]), |path| {
                report.insert_repetition_change(path.clone(), old_indexes, new_indexes, value);
            });
        }
    }
}
