"""Shared test fixtures for decision table tests."""

import pytest

from decision_table.model import (
    Action, Condition, ConditionType, Constraint, ConstraintType,
    DecisionTable, Rule, TableType, make_boolean_condition,
    make_enum_condition, make_numeric_condition,
)


@pytest.fixture
def empty_table():
    return DecisionTable(name="Empty")


@pytest.fixture
def simple_boolean_table():
    table = DecisionTable(name="Simple Boolean")
    table.add_condition(Condition(name="A", possible_values=["T", "F"]))
    table.add_condition(Condition(name="B", possible_values=["T", "F"]))
    table.add_action(Action(name="X", possible_values=["X", ""]))
    table.add_rule(Rule(condition_entries={"A": "T", "B": "T"}, action_entries={"X": "X"}))
    table.add_rule(Rule(condition_entries={"A": "T", "B": "F"}, action_entries={"X": "X"}))
    table.add_rule(Rule(condition_entries={"A": "F", "B": "T"}, action_entries={"X": ""}))
    table.add_rule(Rule(condition_entries={"A": "F", "B": "F"}, action_entries={"X": ""}))
    # Clear undo stack from setup
    table._undo_stack.clear()
    return table


@pytest.fixture
def redundant_table():
    table = DecisionTable(name="Redundant")
    table.add_condition(Condition(name="A", possible_values=["T", "F"]))
    table.add_condition(Condition(name="B", possible_values=["T", "F"]))
    table.add_action(Action(name="X", possible_values=["X", ""]))
    table.add_rule(Rule(condition_entries={"A": "T", "B": "T"}, action_entries={"X": "X"}))
    table.add_rule(Rule(condition_entries={"A": "T", "B": "F"}, action_entries={"X": "X"}))
    table.add_rule(Rule(condition_entries={"A": "F", "B": "T"}, action_entries={"X": ""}))
    table.add_rule(Rule(condition_entries={"A": "F", "B": "F"}, action_entries={"X": ""}))
    table._undo_stack.clear()
    return table


@pytest.fixture
def contradictory_table():
    table = DecisionTable(name="Contradictory")
    table.add_condition(Condition(name="A", possible_values=["T", "F"]))
    table.add_action(Action(name="X", possible_values=["X", ""]))
    table.add_rule(Rule(condition_entries={"A": "T"}, action_entries={"X": "X"}))
    table.add_rule(Rule(condition_entries={"A": "T"}, action_entries={"X": ""}))
    table._undo_stack.clear()
    return table


@pytest.fixture
def incomplete_table():
    table = DecisionTable(name="Incomplete")
    table.add_condition(Condition(name="A", possible_values=["T", "F"]))
    table.add_condition(Condition(name="B", possible_values=["T", "F"]))
    table.add_action(Action(name="X", possible_values=["X", ""]))
    table.add_rule(Rule(condition_entries={"A": "T", "B": "-"}, action_entries={"X": "X"}))
    table._undo_stack.clear()
    return table


@pytest.fixture
def three_condition_table():
    table = DecisionTable(name="Three Conditions")
    table.add_condition(Condition(name="A", possible_values=["T", "F"]))
    table.add_condition(Condition(name="B", possible_values=["T", "F"]))
    table.add_condition(Condition(name="C", possible_values=["T", "F"]))
    table.add_action(Action(name="X", possible_values=["X", ""]))
    for a, b, c in [("T","T","T"),("T","T","F"),("T","F","T"),("T","F","F")]:
        table.add_rule(Rule(condition_entries={"A": a, "B": b, "C": c}, action_entries={"X": "X"}))
    for a, b, c in [("F","T","T"),("F","T","F"),("F","F","T"),("F","F","F")]:
        table.add_rule(Rule(condition_entries={"A": a, "B": b, "C": c}, action_entries={"X": ""}))
    table._undo_stack.clear()
    return table


@pytest.fixture
def constrained_table():
    """Table with a constraint: A=T and B=T is impossible."""
    table = DecisionTable(name="Constrained")
    table.add_condition(Condition(name="A", possible_values=["T", "F"]))
    table.add_condition(Condition(name="B", possible_values=["T", "F"]))
    table.add_action(Action(name="X", possible_values=["X", ""]))
    table.add_constraint(Constraint(
        constraint_type=ConstraintType.IMPOSSIBLE,
        conditions={"A": "T", "B": "T"},
        description="A and B cannot both be true",
    ))
    table.add_rule(Rule(condition_entries={"A": "T", "B": "F"}, action_entries={"X": "X"}))
    table.add_rule(Rule(condition_entries={"A": "F", "B": "T"}, action_entries={"X": ""}))
    table.add_rule(Rule(condition_entries={"A": "F", "B": "F"}, action_entries={"X": ""}))
    table._undo_stack.clear()
    return table


@pytest.fixture
def numeric_table():
    """Table with a numeric range condition."""
    table = DecisionTable(name="Numeric")
    table.add_condition(make_numeric_condition("Age", ["<18", "18-64", ">=65"]))
    table.add_condition(make_boolean_condition("Member"))
    table.add_action(Action(name="Discount", possible_values=["10%", "20%", ""]))
    table.add_rule(Rule(condition_entries={"Age": "<18", "Member": "T"}, action_entries={"Discount": "10%"}))
    table.add_rule(Rule(condition_entries={"Age": "18-64", "Member": "T"}, action_entries={"Discount": "20%"}))
    table.add_rule(Rule(condition_entries={"Age": ">=65", "Member": "-"}, action_entries={"Discount": "10%"}))
    table.add_rule(Rule(condition_entries={"Age": "-", "Member": "F"}, action_entries={"Discount": ""}))
    table._undo_stack.clear()
    return table


@pytest.fixture
def else_table():
    """Table with an else rule."""
    table = DecisionTable(name="Else Table")
    table.add_condition(Condition(name="A", possible_values=["T", "F"]))
    table.add_action(Action(name="X", possible_values=["X", ""]))
    table.add_rule(Rule(condition_entries={"A": "T"}, action_entries={"X": "X"}))
    table.add_else_rule({"X": ""})
    table._undo_stack.clear()
    return table


@pytest.fixture
def priority_table():
    """Table with priority rules."""
    table = DecisionTable(name="Priority")
    table.add_condition(Condition(name="A", possible_values=["T", "F"]))
    table.add_action(Action(name="X", possible_values=["X", ""]))
    # Both cover A=T, but different priorities
    table.add_rule(Rule(condition_entries={"A": "T"}, action_entries={"X": "X"}, priority=10))
    table.add_rule(Rule(condition_entries={"A": "T"}, action_entries={"X": ""}, priority=5))
    table.add_rule(Rule(condition_entries={"A": "F"}, action_entries={"X": ""}))
    table._undo_stack.clear()
    return table


@pytest.fixture
def multi_hit_table():
    """Multi-hit table where multiple rules can fire."""
    table = DecisionTable(name="Multi-Hit", table_type=TableType.MULTI_HIT)
    table.add_condition(Condition(name="A", possible_values=["T", "F"]))
    table.add_action(Action(name="X", possible_values=["X", ""]))
    table.add_action(Action(name="Y", possible_values=["Y", ""]))
    table.add_rule(Rule(condition_entries={"A": "T"}, action_entries={"X": "X", "Y": ""}))
    table.add_rule(Rule(condition_entries={"A": "T"}, action_entries={"X": "", "Y": "Y"}))
    table.add_rule(Rule(condition_entries={"A": "F"}, action_entries={"X": "", "Y": ""}))
    table._undo_stack.clear()
    return table
