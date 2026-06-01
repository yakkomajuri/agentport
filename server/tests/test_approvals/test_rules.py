"""Unit tests for the pure rule-matching engine (no DB)."""

import pytest

from agent_port.approvals.rules import (
    RuleValidationError,
    condition_matches,
    evaluate_rules,
    rule_matches,
    validate_rule_fields,
)

# ── operators ──


@pytest.mark.parametrize(
    "operator,value,expected,result",
    [
        ("equals", "hello", "hello", True),
        ("equals", "hello", "Hello", False),
        ("contains", "password reset", "password", True),
        ("contains", "subject line", "secret", False),
        ("starts_with", "hello world", "hello", True),
        ("starts_with", "hello world", "world", False),
        ("ends_with", "a@useskald.com", "@useskald.com", True),
        ("ends_with", "a@gmail.com", "@useskald.com", False),
    ],
)
def test_operators(operator, value, expected, result):
    assert condition_matches({"x": value}, "x", operator, [expected]) is result


# ── condition value OR ──


def test_condition_values_are_or():
    cond = ("subject", "contains", ["password", "secret"])
    assert condition_matches({"subject": "my secret note"}, *cond) is True
    assert condition_matches({"subject": "hello"}, *cond) is False


# ── array param OR ──


def test_array_param_values_are_or():
    cond = ("to", "ends_with", ["@useskald.com"])
    assert condition_matches({"to": ["a@gmail.com", "b@useskald.com"]}, *cond) is True
    assert condition_matches({"to": ["a@gmail.com", "b@yahoo.com"]}, *cond) is False


# ── missing param never matches ──


def test_missing_param_never_matches():
    assert condition_matches({}, "to", "equals", ["x"]) is False
    assert condition_matches({"other": "v"}, "to", "contains", [""]) is False


def test_dotted_param_path():
    args = {"message": {"subject": "secret stuff"}}
    assert condition_matches(args, "message.subject", "contains", ["secret"]) is True
    assert condition_matches(args, "message.missing", "contains", ["secret"]) is False


# ── conditions AND ──


def test_multiple_conditions_are_and():
    conditions = [
        {"param_path": "to", "operator": "ends_with", "values": ["@useskald.com"]},
        {"param_path": "subject", "operator": "contains", "values": ["invoice"]},
    ]
    assert rule_matches({"to": "a@useskald.com", "subject": "invoice 1"}, conditions) is True
    assert rule_matches({"to": "a@useskald.com", "subject": "hello"}, conditions) is False


def test_rule_with_no_conditions_matches_everything():
    assert rule_matches({"anything": 1}, []) is True


# ── evaluate_rules: priority + precedence ──


def _rule(id_, priority, effect, conditions):
    return {"id": id_, "priority": priority, "effect": effect, "conditions": conditions}


def test_ascending_priority_wins():
    rules = [
        _rule("low", 50, "deny", []),
        _rule("high", 100, "allow", []),
    ]
    winner = evaluate_rules(rules, {})
    assert winner["id"] == "low"


def test_same_priority_precedence_deny_beats_allow():
    rules = [
        _rule("a", 100, "allow", []),
        _rule("d", 100, "deny", []),
        _rule("r", 100, "require_approval", []),
    ]
    assert evaluate_rules(rules, {})["id"] == "d"


def test_same_priority_precedence_require_beats_allow():
    rules = [
        _rule("a", 100, "allow", []),
        _rule("r", 100, "require_approval", []),
    ]
    assert evaluate_rules(rules, {})["id"] == "r"


def test_no_matching_rule_returns_none():
    rules = [
        _rule("a", 100, "allow", [{"param_path": "to", "operator": "equals", "values": ["x"]}]),
    ]
    assert evaluate_rules(rules, {"to": "y"}) is None


# ── validation ──


def test_validate_rejects_bad_effect():
    with pytest.raises(RuleValidationError):
        validate_rule_fields(effect="maybe", conditions=[], existing_rule_count=1)


def test_validate_rejects_bad_operator():
    with pytest.raises(RuleValidationError):
        validate_rule_fields(
            effect="allow",
            conditions=[{"param_path": "to", "operator": "regex", "values": ["x"]}],
            existing_rule_count=1,
        )


def test_validate_rejects_empty_param_path():
    with pytest.raises(RuleValidationError):
        validate_rule_fields(
            effect="allow",
            conditions=[{"param_path": "  ", "operator": "equals", "values": ["x"]}],
            existing_rule_count=1,
        )


def test_validate_rejects_too_many_rules():
    with pytest.raises(RuleValidationError):
        validate_rule_fields(effect="allow", conditions=[], existing_rule_count=21)


def test_validate_rejects_too_many_conditions():
    conds = [{"param_path": "a", "operator": "equals", "values": ["x"]} for _ in range(11)]
    with pytest.raises(RuleValidationError):
        validate_rule_fields(effect="allow", conditions=conds, existing_rule_count=1)


def test_validate_rejects_too_many_values():
    with pytest.raises(RuleValidationError):
        validate_rule_fields(
            effect="allow",
            conditions=[
                {"param_path": "a", "operator": "equals", "values": [str(i) for i in range(21)]}
            ],
            existing_rule_count=1,
        )


def test_validate_rejects_long_value():
    with pytest.raises(RuleValidationError):
        validate_rule_fields(
            effect="allow",
            conditions=[{"param_path": "a", "operator": "equals", "values": ["x" * 513]}],
            existing_rule_count=1,
        )


def test_validate_accepts_valid_rule():
    validate_rule_fields(
        effect="allow",
        conditions=[{"param_path": "to", "operator": "ends_with", "values": ["@useskald.com"]}],
        existing_rule_count=1,
    )
