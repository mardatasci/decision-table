"""Validation checks for decision tables: completeness, redundancy, contradiction, consistency."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .model import DONT_CARE, DecisionTable, TableType


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationMessage:
    severity: Severity
    check: str
    message: str
    rule_indices: list[int] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    messages: list[ValidationMessage] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(m.severity == Severity.ERROR for m in self.messages)

    @property
    def errors(self) -> list[ValidationMessage]:
        return [m for m in self.messages if m.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationMessage]:
        return [m for m in self.messages if m.severity == Severity.WARNING]

    def add(self, msg: ValidationMessage) -> None:
        self.messages.append(msg)


def check_consistency(table: DecisionTable) -> ValidationResult:
    """Check structural consistency: valid values, complete references, and constraint validity."""
    result = ValidationResult()

    if not table.conditions:
        result.add(ValidationMessage(
            Severity.WARNING, "consistency", "Table has no conditions defined."
        ))

    if not table.actions:
        result.add(ValidationMessage(
            Severity.WARNING, "consistency", "Table has no actions defined."
        ))

    if not table.rules:
        result.add(ValidationMessage(
            Severity.WARNING, "consistency", "Table has no rules defined."
        ))
        return result

    cond_names = {c.name for c in table.conditions}
    action_names = {a.name for a in table.actions}
    cond_values = {c.name: set(c.possible_values) | {DONT_CARE} for c in table.conditions}
    action_values = {a.name: set(a.possible_values) for a in table.actions}

    for i, rule in enumerate(table.rules):
        # Check condition entries reference valid conditions with valid values
        for cond_name, value in rule.condition_entries.items():
            if cond_name not in cond_names:
                result.add(ValidationMessage(
                    Severity.ERROR, "consistency",
                    f"Rule {i}: references unknown condition '{cond_name}'.",
                    rule_indices=[i],
                ))
            elif value not in cond_values[cond_name]:
                result.add(ValidationMessage(
                    Severity.ERROR, "consistency",
                    f"Rule {i}: condition '{cond_name}' has invalid value '{value}'.",
                    rule_indices=[i],
                ))

        # Check missing conditions
        missing_conds = cond_names - set(rule.condition_entries.keys())
        if missing_conds:
            result.add(ValidationMessage(
                Severity.WARNING, "consistency",
                f"Rule {i}: missing conditions {sorted(missing_conds)} (treated as don't-care).",
                rule_indices=[i],
            ))

        # Check action entries
        for action_name, value in rule.action_entries.items():
            if action_name not in action_names:
                result.add(ValidationMessage(
                    Severity.ERROR, "consistency",
                    f"Rule {i}: references unknown action '{action_name}'.",
                    rule_indices=[i],
                ))
            elif value not in action_values[action_name]:
                result.add(ValidationMessage(
                    Severity.ERROR, "consistency",
                    f"Rule {i}: action '{action_name}' has invalid value '{value}'.",
                    rule_indices=[i],
                ))

        # Check missing actions
        missing_actions = action_names - set(rule.action_entries.keys())
        if missing_actions:
            result.add(ValidationMessage(
                Severity.WARNING, "consistency",
                f"Rule {i}: missing actions {sorted(missing_actions)} (treated as empty).",
                rule_indices=[i],
            ))

    # Validate constraints reference valid conditions and values
    for ci, constraint in enumerate(table.constraints):
        for cond_name, value in constraint.conditions.items():
            if cond_name not in cond_names:
                result.add(ValidationMessage(
                    Severity.ERROR, "consistency",
                    f"Constraint {ci}: references unknown condition '{cond_name}'.",
                    details={"constraint_index": ci},
                ))
            elif value not in cond_values[cond_name] and value != DONT_CARE:
                result.add(ValidationMessage(
                    Severity.ERROR, "consistency",
                    f"Constraint {ci}: condition '{cond_name}' has invalid value '{value}'.",
                    details={"constraint_index": ci},
                ))

    if not result.errors:
        result.add(ValidationMessage(
            Severity.INFO, "consistency", "Table is structurally consistent."
        ))

    return result


def check_completeness(table: DecisionTable) -> ValidationResult:
    """Check if all valid input combinations are covered by at least one rule.

    Uses ``valid_input_combinations()`` so that constraint-excluded combos are
    ignored.  Else rules (``rule.is_else``) are treated as covering every
    combination.
    """
    result = ValidationResult()

    if not table.conditions or not table.rules:
        result.add(ValidationMessage(
            Severity.WARNING, "completeness",
            "Cannot check completeness: table has no conditions or no rules."
        ))
        return result

    # If there is an else rule, it covers everything by definition
    has_else = any(rule.is_else for rule in table.rules)
    if has_else:
        valid_combos = table.valid_input_combinations()
        result.add(ValidationMessage(
            Severity.INFO, "completeness",
            f"Table is complete: else rule covers all {len(valid_combos)} valid input combinations."
        ))
        return result

    valid_combos = table.valid_input_combinations()
    uncovered = []

    for combo in valid_combos:
        if not any(rule.covers(combo) for rule in table.rules):
            uncovered.append(combo)

    if uncovered:
        for combo in uncovered:
            desc = ", ".join(f"{k}={v}" for k, v in sorted(combo.items()))
            result.add(ValidationMessage(
                Severity.WARNING, "completeness",
                f"Uncovered input combination: {desc}.",
                details={"combination": combo},
            ))
        result.add(ValidationMessage(
            Severity.WARNING, "completeness",
            f"{len(uncovered)} of {len(valid_combos)} valid input combinations are not covered.",
        ))
    else:
        result.add(ValidationMessage(
            Severity.INFO, "completeness",
            f"Table is complete: all {len(valid_combos)} valid input combinations are covered."
        ))

    return result


def check_redundancy(table: DecisionTable) -> ValidationResult:
    """Find rules that cover the same valid inputs with the same outputs.

    Only valid (non-constrained) input combinations are considered.
    """
    result = ValidationResult()

    if len(table.rules) < 2:
        result.add(ValidationMessage(
            Severity.INFO, "redundancy", "Not enough rules to check for redundancy."
        ))
        return result

    valid_combos = table.valid_input_combinations()
    found = set()

    for i in range(len(table.rules)):
        for j in range(i + 1, len(table.rules)):
            if (i, j) in found:
                continue

            ri, rj = table.rules[i], table.rules[j]

            # Check if they have the same action profile
            if ri.action_profile() != rj.action_profile():
                continue

            # Check coverage against valid combinations only
            ri_combos = {tuple(sorted(c.items())) for c in valid_combos if ri.covers(c)}
            rj_combos = {tuple(sorted(c.items())) for c in valid_combos if rj.covers(c)}

            if ri_combos and rj_combos:
                if ri_combos == rj_combos:
                    found.add((i, j))
                    result.add(ValidationMessage(
                        Severity.WARNING, "redundancy",
                        f"Rules {i} and {j} are fully redundant (same inputs and outputs).",
                        rule_indices=[i, j],
                    ))
                elif ri_combos <= rj_combos:
                    found.add((i, j))
                    result.add(ValidationMessage(
                        Severity.WARNING, "redundancy",
                        f"Rule {i} is redundant (fully covered by rule {j} with same actions).",
                        rule_indices=[i, j],
                    ))
                elif rj_combos <= ri_combos:
                    found.add((i, j))
                    result.add(ValidationMessage(
                        Severity.WARNING, "redundancy",
                        f"Rule {j} is redundant (fully covered by rule {i} with same actions).",
                        rule_indices=[i, j],
                    ))

    if not found:
        result.add(ValidationMessage(
            Severity.INFO, "redundancy", "No redundant rules found."
        ))

    return result


def check_contradiction(table: DecisionTable) -> ValidationResult:
    """Find rules that cover the same valid inputs with different outputs.

    Constraint-excluded combinations are skipped.

    For **single-hit** tables, overlapping rules with different actions are not
    contradictions when they have different priorities -- the higher-priority
    rule wins.  They are only flagged as errors when two rules share the same
    priority *and* overlap on valid inputs.

    For **multi-hit** tables, overlapping rules with different actions are
    expected (multiple rules are meant to fire together), so no contradiction
    is reported.
    """
    result = ValidationResult()

    if len(table.rules) < 2:
        result.add(ValidationMessage(
            Severity.INFO, "contradiction", "Not enough rules to check for contradiction."
        ))
        return result

    # Multi-hit tables allow overlapping rules with different actions by design
    if table.table_type == TableType.MULTI_HIT:
        result.add(ValidationMessage(
            Severity.INFO, "contradiction",
            "Multi-hit table: overlapping rules with different actions are allowed."
        ))
        return result

    valid_combos = table.valid_input_combinations()
    found = set()

    for i in range(len(table.rules)):
        for j in range(i + 1, len(table.rules)):
            if (i, j) in found:
                continue

            ri, rj = table.rules[i], table.rules[j]

            # Same actions -> not a contradiction (may be redundant)
            if ri.action_profile() == rj.action_profile():
                continue

            # In single-hit tables, different priorities resolve the conflict
            if ri.priority != rj.priority:
                continue

            # Check if they share any covered valid input combinations
            overlap = []
            for combo in valid_combos:
                if ri.covers(combo) and rj.covers(combo):
                    overlap.append(combo)

            if overlap:
                found.add((i, j))
                desc = ", ".join(
                    f"{k}={v}" for k, v in sorted(overlap[0].items())
                )
                result.add(ValidationMessage(
                    Severity.ERROR, "contradiction",
                    f"Rules {i} and {j} contradict: same input ({desc}) but different actions.",
                    rule_indices=[i, j],
                    details={"overlapping_combinations": len(overlap)},
                ))

    if not found:
        result.add(ValidationMessage(
            Severity.INFO, "contradiction", "No contradictions found."
        ))

    return result


def check_constraints(table: DecisionTable) -> ValidationResult:
    """Report which input combinations are excluded by constraints.

    This provides visibility into the effect of constraints on the input space.
    """
    result = ValidationResult()

    if not table.constraints:
        result.add(ValidationMessage(
            Severity.INFO, "constraints",
            "No constraints defined."
        ))
        return result

    all_combos = table.all_input_combinations()
    excluded = []

    for combo in all_combos:
        if table.violates_constraints(combo):
            excluded.append(combo)

    if excluded:
        for combo in excluded:
            desc = ", ".join(f"{k}={v}" for k, v in sorted(combo.items()))
            # Find which constraint(s) exclude it
            violating = []
            for ci, constraint in enumerate(table.constraints):
                if constraint.is_violated(combo):
                    violating.append(ci)
            result.add(ValidationMessage(
                Severity.INFO, "constraints",
                f"Excluded by constraint(s) {violating}: {desc}.",
                details={"combination": combo, "constraint_indices": violating},
            ))
        result.add(ValidationMessage(
            Severity.INFO, "constraints",
            f"{len(excluded)} of {len(all_combos)} input combinations are excluded by constraints.",
            details={"excluded_count": len(excluded), "total_count": len(all_combos)},
        ))
    else:
        result.add(ValidationMessage(
            Severity.INFO, "constraints",
            "Constraints are defined but do not exclude any input combinations.",
        ))

    return result


def validate_all(table: DecisionTable) -> ValidationResult:
    """Run all validation checks."""
    combined = ValidationResult()
    for check in [
        check_consistency,
        check_constraints,
        check_completeness,
        check_redundancy,
        check_contradiction,
    ]:
        r = check(table)
        combined.messages.extend(r.messages)
    return combined
