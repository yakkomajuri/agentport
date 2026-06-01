import uuid
from datetime import datetime

from sqlalchemy import Index
from sqlmodel import Field, SQLModel


class ToolExecutionRule(SQLModel, table=True):
    """A conditional policy rule that overrides the fallback ToolExecutionSetting.mode.

    Rules are scoped to an (org, integration, tool) triple. The evaluator considers
    only enabled rules, in ascending priority order; ties are broken by effect
    precedence (deny > require_approval > allow). See agent_port.approvals.rules.
    """

    __tablename__ = "tool_execution_rule"
    __table_args__ = (
        Index(
            "ix_tool_exec_rule_lookup",
            "org_id",
            "integration_id",
            "tool_name",
            "enabled",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    org_id: uuid.UUID = Field(foreign_key="org.id", index=True)
    integration_id: str
    tool_name: str
    name: str
    priority: int = Field(default=100)
    effect: str  # "allow" | "require_approval" | "deny"
    enabled: bool = Field(default=True)
    created_by_user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ToolExecutionRuleCondition(SQLModel, table=True):
    """A single condition belonging to a ToolExecutionRule.

    Conditions within one rule are AND-ed. The values in ``values_json`` (a JSON
    array of strings) are OR-ed against the resolved parameter; when the parameter
    itself resolves to an array, the operator is OR-ed across its elements.
    """

    __tablename__ = "tool_execution_rule_condition"
    __table_args__ = (Index("ix_tool_exec_rule_cond_rule", "rule_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    rule_id: uuid.UUID = Field(foreign_key="tool_execution_rule.id", index=True)
    param_path: str
    operator: str  # "equals" | "contains" | "starts_with" | "ends_with"
    values_json: str  # JSON-encoded list[str]
    position: int = Field(default=0)
