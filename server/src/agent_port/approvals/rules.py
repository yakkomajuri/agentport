"""Pure evaluation and validation logic for conditional tool-execution rules.

This module is intentionally free of database access so the matching semantics
can be unit-tested in isolation. The evaluator in agent_port.approvals.policy
loads rows and delegates the decision to :func:`evaluate_rules` here.

Semantics (see task spec):
  * values inside one condition are OR-ed
  * an array-valued parameter is OR-ed across its elements
  * conditions inside one rule are AND-ed
  * a rule with no conditions matches everything (a catch-all)
  * a missing parameter never matches
"""

VALID_OPERATORS = ("equals", "contains", "starts_with", "ends_with")
VALID_EFFECTS = ("allow", "require_approval", "deny")

# Write-time validation limits. Backend is authoritative.
MAX_RULES_PER_TOOL = 20
MAX_CONDITIONS_PER_RULE = 10
MAX_VALUES_PER_CONDITION = 20
MAX_VALUE_LENGTH = 512

# Lower number wins among same-priority matches.
_EFFECT_PRECEDENCE = {"deny": 0, "require_approval": 1, "allow": 2}

_MISSING = object()


def resolve_param(args: dict, param_path: str):
    """Resolve a dotted ``param_path`` against ``args``.

    Returns the value, or the sentinel ``_MISSING`` when any segment is absent.
    """
    current = args
    for segment in param_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return _MISSING
        current = current[segment]
    return current


def _operator_matches(operator: str, actual: str, expected: str) -> bool:
    if operator == "equals":
        return actual == expected
    if operator == "contains":
        return expected in actual
    if operator == "starts_with":
        return actual.startswith(expected)
    if operator == "ends_with":
        return actual.endswith(expected)
    return False


def _coerce_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def condition_matches(args: dict, param_path: str, operator: str, values: list[str]) -> bool:
    """Evaluate a single condition against the call ``args``.

    A missing parameter never matches. Array parameters are OR-ed across
    elements; the condition's own values are OR-ed.
    """
    resolved = resolve_param(args, param_path)
    if resolved is _MISSING:
        return False

    candidates = resolved if isinstance(resolved, list) else [resolved]
    for candidate in candidates:
        actual = _coerce_scalar(candidate)
        for expected in values:
            if _operator_matches(operator, actual, expected):
                return True
    return False


def rule_matches(args: dict, conditions: list[dict]) -> bool:
    """A rule matches when every one of its conditions matches (AND).

    ``conditions`` is a list of dicts with keys ``param_path``, ``operator``,
    ``values``. A rule with no conditions matches everything.
    """
    return all(
        condition_matches(args, c["param_path"], c["operator"], c["values"]) for c in conditions
    )


def evaluate_rules(rules: list[dict], args: dict) -> dict | None:
    """Return the winning rule (``{"id", "effect", ...}``) for ``args`` or None.

    ``rules`` must already be filtered to enabled rules for the org/integration/tool.
    Each entry is a dict with ``id``, ``priority``, ``effect`` and ``conditions``.
    """
    matching = [r for r in rules if rule_matches(args, r["conditions"])]
    if not matching:
        return None

    min_priority = min(r["priority"] for r in matching)
    candidates = [r for r in matching if r["priority"] == min_priority]
    return min(candidates, key=lambda r: _EFFECT_PRECEDENCE.get(r["effect"], 99))


class RuleValidationError(ValueError):
    """Raised when a rule write payload violates a validation limit."""


def validate_rule_fields(
    *,
    effect: str,
    conditions: list[dict],
    existing_rule_count: int,
) -> None:
    """Validate a rule create/update payload. Raises RuleValidationError on failure.

    ``existing_rule_count`` is the number of rules that would exist alongside this
    one for the tool (pass the post-write count, i.e. include this rule).
    """
    if existing_rule_count > MAX_RULES_PER_TOOL:
        raise RuleValidationError(f"A tool may have at most {MAX_RULES_PER_TOOL} rules.")
    if effect not in VALID_EFFECTS:
        raise RuleValidationError(f"Invalid effect '{effect}'. Must be one of: {VALID_EFFECTS}.")
    if len(conditions) > MAX_CONDITIONS_PER_RULE:
        raise RuleValidationError(f"A rule may have at most {MAX_CONDITIONS_PER_RULE} conditions.")
    for cond in conditions:
        param_path = cond.get("param_path") or ""
        operator = cond.get("operator")
        values = cond.get("values") or []
        if not param_path.strip():
            raise RuleValidationError("Condition param_path must be non-empty.")
        if operator not in VALID_OPERATORS:
            raise RuleValidationError(
                f"Invalid operator '{operator}'. Must be one of: {VALID_OPERATORS}."
            )
        if not isinstance(values, list) or len(values) == 0:
            raise RuleValidationError("Condition must have at least one value.")
        if len(values) > MAX_VALUES_PER_CONDITION:
            raise RuleValidationError(
                f"A condition may have at most {MAX_VALUES_PER_CONDITION} values."
            )
        for value in values:
            if not isinstance(value, str):
                raise RuleValidationError("Condition values must be strings.")
            if len(value) > MAX_VALUE_LENGTH:
                raise RuleValidationError(
                    f"Condition values must be at most {MAX_VALUE_LENGTH} characters."
                )
