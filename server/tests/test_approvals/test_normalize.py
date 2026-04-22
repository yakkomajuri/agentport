from agent_port.approvals.normalize import hash_normalized_args, normalize_tool_args


def test_stable_key_order():
    a = normalize_tool_args({"b": 2, "a": 1})
    b = normalize_tool_args({"a": 1, "b": 2})
    assert a == b
    assert a == '{"a":1,"b":2}'


def test_preserves_list_order():
    result = normalize_tool_args({"items": [3, 1, 2]})
    assert result == '{"items":[3,1,2]}'


def test_preserves_explicit_null():
    result = normalize_tool_args({"key": None})
    assert result == '{"key":null}'


def test_nested_key_ordering():
    result = normalize_tool_args({"z": {"b": 2, "a": 1}, "a": 0})
    assert result == '{"a":0,"z":{"a":1,"b":2}}'


def test_hash_deterministic():
    normalized = normalize_tool_args({"x": 1})
    h1 = hash_normalized_args(normalized)
    h2 = hash_normalized_args(normalized)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_different_args_different_hash():
    h1 = hash_normalized_args(normalize_tool_args({"x": 1}))
    h2 = hash_normalized_args(normalize_tool_args({"x": 2}))
    assert h1 != h2


def test_empty_args():
    result = normalize_tool_args({})
    assert result == "{}"
    h = hash_normalized_args(result)
    assert len(h) == 64
