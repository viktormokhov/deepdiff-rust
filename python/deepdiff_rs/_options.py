"""deepdiff 9.1.0's value-normalization options, as the native diff takes them."""

import datetime
import decimal
import fractions
import uuid

# deepdiff's `numbers` and `strings`, without the numpy types.
_NUMBERS = (
    int, float, complex, decimal.Decimal, fractions.Fraction,
    datetime.datetime, datetime.date, datetime.timedelta, datetime.time,
)
_STRINGS = (str, bytes, memoryview)
_UUID_STR = (uuid.UUID, str)
_ZEROED = ("hour", "minute", "second", "microsecond")
_TRUNCATE_FROM = {"day": 0, "hour": 1, "minute": 2, "second": 3}


def _type_groups(groups, ignore_string_type_changes, ignore_numeric_type_changes, ignore_uuid_types):
    """`get_ignore_types_in_groups`: each group a tuple of types."""
    if groups and isinstance(groups[0], type):
        groups = [groups]
    result = [
        tuple(type(item) if item is None or not isinstance(item, type) else item for item in group)
        for group in groups or []
    ]
    if ignore_string_type_changes and _STRINGS not in result:
        result.append(_STRINGS)
    if ignore_numeric_type_changes and _NUMBERS not in result:
        result.append(_NUMBERS)
    if ignore_uuid_types and _UUID_STR not in result:
        result.append(_UUID_STR)
    return result


def native_options(
    builtin_types, *, significant_digits, number_format_notation, math_epsilon, use_log_scale,
    log_scale_similarity_threshold, ignore_nan_inequality, ignore_string_case,
    ignore_numeric_type_changes, ignore_string_type_changes, ignore_type_in_groups,
    ignore_type_subclasses, truncate_datetime, ignore_uuid_types=False,
):
    """The native `DeepDiff` keyword arguments for these options."""
    if significant_digits is not None and significant_digits < 0:
        raise ValueError("significant_digits must be None or a non-negative integer")
    if significant_digits is None and ignore_numeric_type_changes:
        significant_digits = 12
    if significant_digits is not None and number_format_notation not in ("f", "e"):
        raise ValueError(
            f"number_format_notation got invalid value of {number_format_notation}. "
            "The valid values are 'f' and 'e'"
        )
    if truncate_datetime not in {None, *_TRUNCATE_FROM}:
        raise ValueError("truncate_datetime must be second, minute, hour or day")
    options = {
        "truncate_datetime": truncate_datetime
        and dict.fromkeys(_ZEROED[_TRUNCATE_FROM[truncate_datetime]:], 0),
        "significant_digits": significant_digits,
        "exponent_notation": number_format_notation == "e",
        "math_epsilon": math_epsilon,
        "log_scale_threshold": log_scale_similarity_threshold if use_log_scale else None,
        "ignore_nan_inequality": ignore_nan_inequality,
        "ignore_string_case": ignore_string_case,
        "ignore_numeric_type_changes": ignore_numeric_type_changes,
    }
    groups = _type_groups(
        ignore_type_in_groups, ignore_string_type_changes, ignore_numeric_type_changes,
        ignore_uuid_types,
    )
    if groups:
        # ponytail: a u64 mask, so at most 64 groups.
        def group_mask(cls):
            return sum(
                1 << i for i, group in enumerate(groups)
                if (cls in group if ignore_type_subclasses else issubclass(cls, group))
            )

        options["type_groups"] = {name: group_mask(cls) for name, cls in builtin_types.items()}
        options["group_mask"] = group_mask
    return options
