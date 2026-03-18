"""Tests for validation checks."""

from decision_table.model import Action, Condition, Constraint, ConstraintType, DecisionTable, Rule, TableType
from decision_table.validation import (
    Severity, check_completeness, check_consistency, check_constraints,
    check_contradiction, check_redundancy, validate_all,
)


class TestConsistency:
    def test_valid_table(self, simple_boolean_table):
        result = check_consistency(simple_boolean_table)
        assert result.is_valid

    def test_empty_table_warnings(self, empty_table):
        result = check_consistency(empty_table)
        assert any("no conditions" in m.message for m in result.warnings)

    def test_invalid_condition_value(self):
        table = DecisionTable(name="Test")
        table.add_condition(Condition(name="A"))
        table.add_action(Action(name="X"))
        table.add_rule(Rule(condition_entries={"A": "INVALID"}, action_entries={"X": "X"}))
        result = check_consistency(table)
        assert not result.is_valid

    def test_constraint_validation(self):
        table = DecisionTable(name="Test")
        table.add_condition(Condition(name="A"))
        table.add_action(Action(name="X"))
        table.add_rule(Rule(condition_entries={"A": "T"}, action_entries={"X": "X"}))
        table.add_constraint(Constraint(ConstraintType.IMPOSSIBLE, {"UNKNOWN": "T"}))
        result = check_consistency(table)
        assert not result.is_valid


class TestCompleteness:
    def test_complete_table(self, simple_boolean_table):
        result = check_completeness(simple_boolean_table)
        assert any("complete" in m.message.lower() for m in result.messages)

    def test_incomplete_table(self, incomplete_table):
        result = check_completeness(incomplete_table)
        assert any("uncovered" in m.message.lower() for m in result.messages)

    def test_else_rule_makes_complete(self, else_table):
        result = check_completeness(else_table)
        assert any("complete" in m.message.lower() for m in result.messages)

    def test_constrained_completeness(self, constrained_table):
        # Constrained table only needs 3 combos covered, not 4
        result = check_completeness(constrained_table)
        assert not result.errors


class TestRedundancy:
    def test_no_redundancy(self):
        table = DecisionTable(name="Test")
        table.add_condition(Condition(name="A"))
        table.add_action(Action(name="X"))
        table.add_rule(Rule(condition_entries={"A": "T"}, action_entries={"X": "X"}))
        table.add_rule(Rule(condition_entries={"A": "F"}, action_entries={"X": ""}))
        result = check_redundancy(table)
        assert not result.warnings

    def test_redundant_rules(self):
        table = DecisionTable(name="Test")
        table.add_condition(Condition(name="A"))
        table.add_action(Action(name="X"))
        table.add_rule(Rule(condition_entries={"A": "T"}, action_entries={"X": "X"}))
        table.add_rule(Rule(condition_entries={"A": "T"}, action_entries={"X": "X"}))
        result = check_redundancy(table)
        assert len(result.warnings) > 0


class TestContradiction:
    def test_no_contradiction(self, simple_boolean_table):
        result = check_contradiction(simple_boolean_table)
        assert not result.errors

    def test_contradictory_rules(self, contradictory_table):
        result = check_contradiction(contradictory_table)
        assert len(result.errors) > 0

    def test_priority_resolves_contradiction(self, priority_table):
        result = check_contradiction(priority_table)
        # Different priorities = not a contradiction
        assert not result.errors

    def test_multi_hit_no_contradiction(self, multi_hit_table):
        result = check_contradiction(multi_hit_table)
        # Multi-hit allows overlapping rules
        assert not result.errors


class TestConstraints:
    def test_no_constraints(self, simple_boolean_table):
        result = check_constraints(simple_boolean_table)
        assert any("no constraints" in m.message.lower() for m in result.messages)

    def test_constraints_exclude(self, constrained_table):
        result = check_constraints(constrained_table)
        assert any("excluded" in m.message.lower() for m in result.messages)


class TestValidateAll:
    def test_validate_all(self, simple_boolean_table):
        result = validate_all(simple_boolean_table)
        checks = {m.check for m in result.messages}
        assert "consistency" in checks
        assert "completeness" in checks
        assert "redundancy" in checks
        assert "contradiction" in checks
        assert "constraints" in checks
