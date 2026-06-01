import type { RuleEffect, RuleOperator } from '@/api/client'

export const RULE_EFFECTS: { effect: RuleEffect; label: string; color: string }[] = [
  { effect: 'allow', label: 'Allow', color: 'var(--green, #34c759)' },
  { effect: 'require_approval', label: 'Ask', color: 'var(--amber, #f5a623)' },
  { effect: 'deny', label: 'Deny', color: 'var(--red, #ff3b30)' },
]

export const RULE_OPERATORS: { operator: RuleOperator; label: string }[] = [
  { operator: 'equals', label: 'equals' },
  { operator: 'contains', label: 'contains' },
  { operator: 'starts_with', label: 'starts with' },
  { operator: 'ends_with', label: 'ends with' },
]

export function effectLabel(effect: RuleEffect): string {
  return RULE_EFFECTS.find((e) => e.effect === effect)?.label ?? effect
}

export function effectColor(effect: RuleEffect): string {
  return RULE_EFFECTS.find((e) => e.effect === effect)?.color ?? 'var(--text)'
}

export function operatorLabel(operator: RuleOperator): string {
  return RULE_OPERATORS.find((o) => o.operator === operator)?.label ?? operator
}

// Mirrors the backend write-time validation limits (backend is authoritative).
export const RULE_LIMITS = {
  maxRulesPerTool: 20,
  maxConditionsPerRule: 10,
  maxValuesPerCondition: 20,
  maxValueLength: 512,
}
