"""Tests for the core data model."""

import pytest
from decision_table.model import (
    DONT_CARE, Action, Condition, ConditionType, Constraint, ConstraintType,
    DecisionTable, Range, Rule, TableType, make_boolean_condition,
    make_enum_condition, make_numeric_condition, parse_range,
)


class TestRange:
    def test_parse_less_than(self):
        r = parse_range("<18")
        assert r.upper == 18
        assert not r.upper_inclusive
        assert r.contains(17)
        assert not r.contains(18)

    def test_parse_greater_equal(self):
        r = parse_range(">=65")
        assert r.lower == 65
        assert r.lower_inclusive
        assert r.contains(65)
        assert not r.contains(64)

    def test_parse_range(self):
        r = parse_range("18-64")
        assert r.lower == 18
        assert r.upper == 64
        assert r.contains(18)
        assert r.contains(63)
        assert not r.contains(64)

    def test_boundary_values(self):
        r = parse_range("18-64")
        bv = r.boundary_values()
        assert 17 in bv
        assert 18 in bv
        assert 19 in bv
        assert 63 in bv
        assert 64 in bv
        assert 65 in bv


class TestCondition:
    def test_boolean_condition(self):
        c = make_boolean_condition("A")
        assert c.is_boolean
        assert c.condition_type == ConditionType.BOOLEAN

    def test_enum_condition(self):
        c = make_enum_condition("Color", ["Red", "Green", "Blue"])
        assert not c.is_boolean
        assert c.condition_type == ConditionType.ENUM

    def test_numeric_condition(self):
        c = make_numeric_condition("Age", ["<18", "18-64", ">=65"])
        assert c.is_numeric
        assert len(c.ranges) == 3
        assert c.possible_values == ["<18", "18-64", ">=65"]

    def test_numeric_boundary_values(self):
        c = make_numeric_condition("Age", ["<18", "18-64", ">=65"])
        bv = c.boundary_values()
        assert 17 in bv and 18 in bv and 19 in bv
        assert 63 in bv and 64 in bv and 65 in bv

    def test_to_from_dict(self):
        c = make_numeric_condition("Age", ["<18", ">=18"])
        d = c.to_dict()
        c2 = Condition.from_dict(d)
        assert c2.name == "Age"
        assert c2.is_numeric
        assert len(c2.ranges) == 2


class TestConstraint:
    def test_impossible(self):
        c = Constraint(ConstraintType.IMPOSSIBLE, {"A": "T", "B": "T"})
        assert c.is_violated({"A": "T", "B": "T"})
        assert not c.is_violated({"A": "T", "B": "F"})

    def test_exclusion(self):
        c = Constraint(ConstraintType.EXCLUSION, {"A": "T", "B": "T"})
        assert c.is_violated({"A": "T", "B": "T"})
        assert not c.is_violated({"A": "F", "B": "T"})

    def test_implication(self):
        c = Constraint(ConstraintType.IMPLICATION, {"A": "T", "B": "F"})
        # If A=T then B must be F. Violated when A=T and B != F
        assert c.is_violated({"A": "T", "B": "T"})
        assert not c.is_violated({"A": "T", "B": "F"})
        assert not c.is_violated({"A": "F", "B": "T"})

    def test_to_from_dict(self):
        c = Constraint(ConstraintType.IMPOSSIBLE, {"A": "T"}, "test")
        d = c.to_dict()
        c2 = Constraint.from_dict(d)
        assert c2.constraint_type == ConstraintType.IMPOSSIBLE
        assert c2.conditions == {"A": "T"}


class TestRule:
    def test_covers_exact_match(self):
        r = Rule(condition_entries={"A": "T", "B": "F"})
        assert r.covers({"A": "T", "B": "F"})
        assert not r.covers({"A": "F", "B": "F"})

    def test_covers_dont_care(self):
        r = Rule(condition_entries={"A": "T", "B": DONT_CARE})
        assert r.covers({"A": "T", "B": "T"})
        assert r.covers({"A": "T", "B": "F"})

    def test_else_rule_covers_everything(self):
        r = Rule(condition_entries={"A": "-"}, action_entries={"X": ""}, is_else=True)
        assert r.covers({"A": "T"})
        assert r.covers({"A": "F"})

    def test_priority(self):
        r = Rule(priority=10)
        assert r.priority == 10

    def test_expand_dont_cares(self):
        conditions = [Condition(name="A"), Condition(name="B")]
        r = Rule(condition_entries={"A": "T", "B": DONT_CARE}, action_entries={"X": "X"})
        expanded = r.expand_dont_cares(conditions)
        assert len(expanded) == 2

    def test_expand_else_rule(self):
        conditions = [Condition(name="A")]
        r = Rule(condition_entries={"A": "-"}, action_entries={"X": ""}, is_else=True)
        expanded = r.expand_dont_cares(conditions)
        assert len(expanded) == 1
        assert expanded[0].is_else


class TestDecisionTable:
    def test_add_remove_condition(self, empty_table):
        t = empty_table
        t.add_condition(Condition(name="A"))
        assert len(t.conditions) == 1
        t.remove_condition("A")
        assert len(t.conditions) == 0

    def test_add_duplicate_condition(self, empty_table):
        t = empty_table
        t.add_condition(Condition(name="A"))
        with pytest.raises(ValueError, match="already exists"):
            t.add_condition(Condition(name="A"))

    def test_add_remove_action(self, empty_table):
        t = empty_table
        t.add_action(Action(name="X"))
        assert len(t.actions) == 1
        t.remove_action("X")
        assert len(t.actions) == 0

    def test_add_rule_fills_defaults(self, empty_table):
        t = empty_table
        t.add_condition(Condition(name="A"))
        t.add_action(Action(name="X"))
        t.add_rule(Rule())
        assert t.rules[0].condition_entries["A"] == DONT_CARE
        assert t.rules[0].action_entries["X"] == ""

    def test_remove_rule_out_of_range(self, simple_boolean_table):
        with pytest.raises(IndexError):
            simple_boolean_table.remove_rule(10)

    def test_add_else_rule(self, empty_table):
        t = empty_table
        t.add_condition(Condition(name="A"))
        t.add_action(Action(name="X"))
        t.add_else_rule({"X": ""})
        assert t.rules[-1].is_else
        assert t.rules[-1].priority == -1

    def test_duplicate_rule(self, simple_boolean_table):
        t = simple_boolean_table
        t.duplicate_rule(0)
        assert len(t.rules) == 5
        assert t.rules[4].condition_entries == t.rules[0].condition_entries

    def test_move_rule(self, simple_boolean_table):
        t = simple_boolean_table
        first_conds = dict(t.rules[0].condition_entries)
        t.move_rule(0, 2)
        assert t.rules[2].condition_entries == first_conds

    def test_add_remove_constraint(self, empty_table):
        t = empty_table
        t.add_constraint(Constraint(ConstraintType.IMPOSSIBLE, {"A": "T"}))
        assert len(t.constraints) == 1
        t.remove_constraint(0)
        assert len(t.constraints) == 0

    def test_valid_input_combinations(self, constrained_table):
        valid = constrained_table.valid_input_combinations()
        # A=T,B=T is excluded
        assert len(valid) == 3
        assert {"A": "T", "B": "T"} not in valid

    def test_violates_constraints(self, constrained_table):
        assert constrained_table.violates_constraints({"A": "T", "B": "T"})
        assert not constrained_table.violates_constraints({"A": "T", "B": "F"})

    def test_firing_rules_priority(self, priority_table):
        fired = priority_table.firing_rules({"A": "T"})
        assert len(fired) == 2
        assert fired[0][1].priority == 10  # highest first

    def test_effective_actions_single_hit(self, priority_table):
        actions = priority_table.effective_actions({"A": "T"})
        assert actions["X"] == "X"  # priority 10 wins

    def test_effective_actions_multi_hit(self, multi_hit_table):
        actions = multi_hit_table.effective_actions({"A": "T"})
        assert actions["X"] == "X"
        assert actions["Y"] == "Y"

    def test_is_equivalent_to(self, simple_boolean_table):
        import copy
        other = copy.deepcopy(simple_boolean_table)
        is_eq, diffs = simple_boolean_table.is_equivalent_to(other)
        assert is_eq
        assert len(diffs) == 0

    def test_undo_redo(self, empty_table):
        t = empty_table
        t.add_condition(Condition(name="A"))
        assert len(t.conditions) == 1
        t.undo()
        assert len(t.conditions) == 0
        t.redo()
        assert len(t.conditions) == 1

    def test_to_from_dict_full(self, constrained_table):
        d = constrained_table.to_dict()
        t2 = DecisionTable.from_dict(d)
        assert t2.name == "Constrained"
        assert len(t2.constraints) == 1
        assert len(t2.rules) == 3

    def test_all_input_combinations(self, simple_boolean_table):
        combos = simple_boolean_table.all_input_combinations()
        assert len(combos) == 4

    def test_expand_all_rules(self, simple_boolean_table):
        expanded = simple_boolean_table.expand_all_rules()
        assert len(expanded) == 4
