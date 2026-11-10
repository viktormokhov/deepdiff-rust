import json

import deepdiff_rust


def test_native_extension_loads():
    assert deepdiff_rust.version() == "0.1.0"


def test_diff_json_reports_nested_changes():
    result = json.loads(
        deepdiff_rust.diff_json(
            '{"user":{"age":30}}',
            '{"user":{"age":31},"active":true}',
        )
    )
    assert any(item["path"] == "root['user']['age']" for item in result)
    assert any(item["path"] == "root['active']" for item in result)
