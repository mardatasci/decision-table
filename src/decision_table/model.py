"""Core data model for decision tables."""

from __future__ import annotations

import copy
import itertools
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

DONT_CARE = "-"


class ConditionType(Enum):
    BOOLEAN = "boolean"
    ENUM = "enum"
    NUMERIC = "numeric"


class TableType(Enum):
    SINGLE_HIT = "single_hit"  # Only one rule fires per input
    MULTI_HIT = "multi_hit"    # Multiple rules can fire per input


@dataclass
class Range:
    """A numeric range partition, e.g., '<18', '18-64', '>=65'."""

    label: str
    lower: float | None = None
    upper: float | None = None
    lower_inclusive: bool = True
    upper_inclusive: bool = False

    def contains(self, value: float) -> bool:
        if self.lower is not None:
            if self.lower_inclusive:
                if value < self.lower:
                    return False
            else:
                if value <= self.lower:
                    return False
        if self.upper is not None:
            if self.upper_inclusive:
                if value > self.upper:
                    return False
            else:
                if value >= self.upper:
                    return False
        return True

    def boundary_values(self) -> list[float]:
        """Generate boundary test values for this range."""
        values = []
        if self.lower is not None:
            values.append(self.lower - 1)  # just below
            values.append(self.lower)       # at boundary
            values.append(self.lower + 1)  # just above
        if self.upper is not None:
            values.append(self.upper - 1)
            values.append(self.upper)
            values.append(self.upper + 1)
        return sorted(set(values))

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "lower": self.lower,
            "upper": self.upper,
            "lower_inclusive": self.lower_inclusive,
            "upper_inclusive": self.upper_inclusive,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Range:
        return cls(**data)


def parse_range(text: str) -> Range:
    """Parse a range string like '<18', '18-64', '>=65', '<=100'."""
    text = text.strip()
    if text.startswith("<="):
        val = float(text[2:])
        return Range(label=text, lower=None, upper=val, lower_inclusive=True, upper_inclusive=True)
    elif text.startswith("<"):
        val = float(text[1:])
        return Range(label=text, lower=None, upper=val, lower_inclusive=True, upper_inclusive=False)
    elif text.startswith(">="):
        val = float(text[2:])
        return Range(label=text, lower=val, upper=None, lower_inclusive=True, upper_inclusive=True)
    elif text.startswith(">"):
        val = float(text[1:])
        return Range(label=text, lower=val, upper=None, lower_inclusive=False, upper_inclusive=True)
    elif "-" in text and not text.startswith("-"):
        parts = text.split("-", 1)
        lo, hi = float(parts[0]), float(parts[1])
        return Range(label=text, lower=lo, upper=hi, lower_inclusive=True, upper_inclusive=False)
    else:
        val = float(text)
        return Range(label=text, lower=val, upper=val, lower_inclusive=True, upper_inclusive=True)


@dataclass
class Condition:
    """A condition (input) column in a decision table."""

    name: str
    possible_values: list[str] = field(default_factory=lambda: ["T", "F"])
    condition_type: ConditionType = ConditionType.BOOLEAN
    ranges: list[Range] = field(default_factory=list)
    description: str = ""

    @property
    def is_boolean(self) -> bool:
        return self.condition_type == ConditionType.BOOLEAN

    @property
    def is_numeric(self) -> bool:
        return self.condition_type == ConditionType.NUMERIC

    def boundary_values(self) -> list[float]:
        """Get all boundary test values for a numeric condition."""
        values = []
        for r in self.ranges:
            values.extend(r.boundary_values())
        return sorted(set(values))

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "possible_values": self.possible_values,
            "condition_type": self.condition_type.value,
            "description": self.description,
        }
        if self.ranges:
            d["ranges"] = [r.to_dict() for r in self.ranges]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Condition:
        ct = ConditionType(data.get("condition_type", "boolean"))
        ranges = [Range.from_dict(r) for r in data.get("ranges", [])]
        return cls(
            name=data["name"],
            possible_values=data.get("possible_values", ["T", "F"]),
            condition_type=ct,
            ranges=ranges,
            description=data.get("description", ""),
        )


def make_boolean_condition(name: str, description: str = "") -> Condition:
    return Condition(name=name, possible_values=["T", "F"],
                     condition_type=ConditionType.BOOLEAN, description=description)


def make_enum_condition(name: str, values: list[str], description: str = "") -> Condition:
    return Condition(name=name, possible_values=values,
                     condition_type=ConditionType.ENUM, description=description)


def make_numeric_condition(name: str, range_strings: list[str], description: str = "") -> Condition:
    """Create a numeric condition from range strings like ['<18', '18-64', '>=65']."""
    ranges = [parse_range(s) for s in range_strings]
    labels = [r.label for r in ranges]
    return Condition(name=name, possible_values=labels,
                     condition_type=ConditionType.NUMERIC, ranges=ranges, description=description)


@dataclass
class Action:
    """An action (output) column in a decision table."""

    name: str
    possible_values: list[str] = field(default_factory=lambda: ["X", ""])
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "possible_values": self.possible_values,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Action:
        return cls(
            name=data["name"],
            possible_values=data.get("possible_values", ["X", ""]),
            description=data.get("description", ""),
        )


class ConstraintType(Enum):
    EXCLUSION = "exclusion"        # These values cannot occur together
    IMPLICATION = "implication"    # If A=x then B must be y
    IMPOSSIBLE = "impossible"      # This specific combination cannot occur


@dataclass
class Constraint:
    """A constraint between conditions that restricts valid combinations."""

    constraint_type: ConstraintType
    conditions: dict[str, str]  # condition_name -> value
    description: str = ""

    def is_violated(self, combo: dict[str, str]) -> bool:
        """Check if a given input combination violates this constraint."""
        if self.constraint_type == ConstraintType.IMPOSSIBLE:
            return all(combo.get(k) == v for k, v in self.conditions.items())
        elif self.constraint_type == ConstraintType.EXCLUSION:
            return all(combo.get(k) == v for k, v in self.conditions.items())
        elif self.constraint_type == ConstraintType.IMPLICATION:
            # conditions should have "if_cond", "if_val", "then_cond", "then_val" encoded
            # We store as {cond1: val1, cond2: val2} meaning if cond1=val1 then cond2 must =val2
            items = list(self.conditions.items())
            if len(items) >= 2:
                if_cond, if_val = items[0]
                then_cond, then_val = items[1]
                if combo.get(if_cond) == if_val and combo.get(then_cond) != then_val:
                    return True
            return False
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "constraint_type": self.constraint_type.value,
            "conditions": dict(self.conditions),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Constraint:
        return cls(
            constraint_type=ConstraintType(data["constraint_type"]),
            conditions=dict(data["conditions"]),
            description=data.get("description", ""),
        )


@dataclass
class Rule:
    """A single rule (column) in a decision table."""

    condition_entries: dict[str, str] = field(default_factory=dict)
    action_entries: dict[str, str] = field(default_factory=dict)
    priority: int = 0
    is_else: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "condition_entries": dict(self.condition_entries),
            "action_entries": dict(self.action_entries),
        }
        if self.priority != 0:
            d["priority"] = self.priority
        if self.is_else:
            d["is_else"] = True
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Rule:
        return cls(
            condition_entries=dict(data.get("condition_entries", {})),
            action_entries=dict(data.get("action_entries", {})),
            priority=data.get("priority", 0),
            is_else=data.get("is_else", False),
        )

    def covers(self, input_combo: dict[str, str]) -> bool:
        """Check if this rule covers a given input combination."""
        if self.is_else:
            return True
        for cond_name, value in input_combo.items():
            entry = self.condition_entries.get(cond_name)
            if entry is not None and entry != DONT_CARE and entry != value:
                return False
        return True

    def action_profile(self) -> tuple[tuple[str, str], ...]:
        """Return a hashable representation of this rule's action entries."""
        return tuple(sorted(self.action_entries.items()))

    def expand_dont_cares(self, conditions: list[Condition]) -> list[Rule]:
        """Expand don't-care entries into explicit rules."""
        if self.is_else:
            return [Rule(
                condition_entries=dict(self.condition_entries),
                action_entries=dict(self.action_entries),
                priority=self.priority,
                is_else=True,
            )]

        dc_conditions = []
        dc_values = []
        fixed = {}

        for cond in conditions:
            entry = self.condition_entries.get(cond.name, DONT_CARE)
            if entry == DONT_CARE:
                dc_conditions.append(cond.name)
                dc_values.append(cond.possible_values)
            else:
                fixed[cond.name] = entry

        if not dc_conditions:
            return [Rule(
                condition_entries=dict(self.condition_entries),
                action_entries=dict(self.action_entries),
                priority=self.priority,
            )]

        expanded = []
        for combo in itertools.product(*dc_values):
            entries = dict(fixed)
            for name, val in zip(dc_conditions, combo):
                entries[name] = val
            expanded.append(Rule(
                condition_entries=entries,
                action_entries=dict(self.action_entries),
                priority=self.priority,
            ))
        return expanded


@dataclass
class DecisionTable:
    """A complete decision table with conditions, actions, rules, and constraints."""

    name: str = "Untitled"
    conditions: list[Condition] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    table_type: TableType = TableType.SINGLE_HIT
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Undo/redo ──

    _undo_stack: list[dict] = field(default_factory=list, repr=False)
    _redo_stack: list[dict] = field(default_factory=list, repr=False)

    def _save_state(self) -> None:
        """Save current state for undo."""
        state = {
            "conditions": [copy.deepcopy(c) for c in self.conditions],
            "actions": [copy.deepcopy(a) for a in self.actions],
            "rules": [copy.deepcopy(r) for r in self.rules],
            "constraints": [copy.deepcopy(c) for c in self.constraints],
            "table_type": self.table_type,
        }
        self._undo_stack.append(state)
        self._redo_stack.clear()
        # Limit stack size
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)

    def undo(self) -> bool:
        """Undo last change. Returns True if successful."""
        if not self._undo_stack:
            return False
        # Save current state to redo
        current = {
            "conditions": [copy.deepcopy(c) for c in self.conditions],
            "actions": [copy.deepcopy(a) for a in self.actions],
            "rules": [copy.deepcopy(r) for r in self.rules],
            "constraints": [copy.deepcopy(c) for c in self.constraints],
            "table_type": self.table_type,
        }
        self._redo_stack.append(current)
        state = self._undo_stack.pop()
        self.conditions = state["conditions"]
        self.actions = state["actions"]
        self.rules = state["rules"]
        self.constraints = state["constraints"]
        self.table_type = state["table_type"]
        return True

    def redo(self) -> bool:
        """Redo last undone change. Returns True if successful."""
        if not self._redo_stack:
            return False
        current = {
            "conditions": [copy.deepcopy(c) for c in self.conditions],
            "actions": [copy.deepcopy(a) for a in self.actions],
            "rules": [copy.deepcopy(r) for r in self.rules],
            "constraints": [copy.deepcopy(c) for c in self.constraints],
            "table_type": self.table_type,
        }
        self._undo_stack.append(current)
        state = self._redo_stack.pop()
        self.conditions = state["conditions"]
        self.actions = state["actions"]
        self.rules = state["rules"]
        self.constraints = state["constraints"]
        self.table_type = state["table_type"]
        return True

    # ── Conditions ──

    def add_condition(self, condition: Condition) -> None:
        if any(c.name == condition.name for c in self.conditions):
            raise ValueError(f"Condition '{condition.name}' already exists")
        self._save_state()
        self.conditions.append(condition)
        for rule in self.rules:
            rule.condition_entries.setdefault(condition.name, DONT_CARE)

    def remove_condition(self, name: str) -> None:
        idx = next((i for i, c in enumerate(self.conditions) if c.name == name), None)
        if idx is None:
            raise ValueError(f"Condition '{name}' not found")
        self._save_state()
        self.conditions.pop(idx)
        for rule in self.rules:
            rule.condition_entries.pop(name, None)

    # ── Actions ──

    def add_action(self, action: Action) -> None:
        if any(a.name == action.name for a in self.actions):
            raise ValueError(f"Action '{action.name}' already exists")
        self._save_state()
        self.actions.append(action)
        for rule in self.rules:
            rule.action_entries.setdefault(action.name, "")

    def remove_action(self, name: str) -> None:
        idx = next((i for i, a in enumerate(self.actions) if a.name == name), None)
        if idx is None:
            raise ValueError(f"Action '{name}' not found")
        self._save_state()
        self.actions.pop(idx)
        for rule in self.rules:
            rule.action_entries.pop(name, None)

    # ── Rules ──

    def add_rule(self, rule: Rule) -> None:
        self._save_state()
        for cond in self.conditions:
            rule.condition_entries.setdefault(cond.name, DONT_CARE)
        for action in self.actions:
            rule.action_entries.setdefault(action.name, "")
        self.rules.append(rule)

    def remove_rule(self, index: int) -> None:
        if index < 0 or index >= len(self.rules):
            raise IndexError(f"Rule index {index} out of range (0-{len(self.rules) - 1})")
        self._save_state()
        self.rules.pop(index)

    def add_else_rule(self, action_entries: dict[str, str] | None = None) -> None:
        """Add a catch-all else rule."""
        self._save_state()
        entries = action_entries or {}
        for action in self.actions:
            entries.setdefault(action.name, "")
        rule = Rule(
            condition_entries={c.name: DONT_CARE for c in self.conditions},
            action_entries=entries,
            priority=-1,
            is_else=True,
        )
        self.rules.append(rule)

    def duplicate_rule(self, index: int) -> None:
        """Copy a rule and append it."""
        if index < 0 or index >= len(self.rules):
            raise IndexError(f"Rule index {index} out of range")
        self._save_state()
        self.rules.append(copy.deepcopy(self.rules[index]))

    def move_rule(self, from_idx: int, to_idx: int) -> None:
        """Move a rule from one position to another."""
        if from_idx < 0 or from_idx >= len(self.rules):
            raise IndexError(f"Source index {from_idx} out of range")
        to_idx = max(0, min(to_idx, len(self.rules) - 1))
        self._save_state()
        rule = self.rules.pop(from_idx)
        self.rules.insert(to_idx, rule)

    # ── Constraints ──

    def add_constraint(self, constraint: Constraint) -> None:
        self._save_state()
        self.constraints.append(constraint)

    def remove_constraint(self, index: int) -> None:
        if index < 0 or index >= len(self.constraints):
            raise IndexError(f"Constraint index {index} out of range")
        self._save_state()
        self.constraints.pop(index)

    # ── Queries ──

    def all_input_combinations(self) -> list[dict[str, str]]:
        """Generate all possible input combinations from conditions."""
        if not self.conditions:
            return [{}]
        names = [c.name for c in self.conditions]
        value_lists = [c.possible_values for c in self.conditions]
        combos = []
        for vals in itertools.product(*value_lists):
            combos.append(dict(zip(names, vals)))
        return combos

    def valid_input_combinations(self) -> list[dict[str, str]]:
        """Generate all valid input combinations (filtered by constraints)."""
        all_combos = self.all_input_combinations()
        if not self.constraints:
            return all_combos
        return [c for c in all_combos if not self.violates_constraints(c)]

    def violates_constraints(self, combo: dict[str, str]) -> bool:
        """Check if an input combination violates any constraint."""
        return any(c.is_violated(combo) for c in self.constraints)

    def expand_all_rules(self) -> list[Rule]:
        """Expand all don't-care entries in all rules."""
        expanded = []
        for rule in self.rules:
            expanded.extend(rule.expand_dont_cares(self.conditions))
        return expanded

    def firing_rules(self, input_combo: dict[str, str]) -> list[tuple[int, Rule]]:
        """Get all rules that fire for a given input, sorted by priority (high first)."""
        fired = []
        for i, rule in enumerate(self.rules):
            if rule.covers(input_combo):
                fired.append((i, rule))
        fired.sort(key=lambda x: x[1].priority, reverse=True)
        return fired

    def effective_actions(self, input_combo: dict[str, str]) -> dict[str, str] | None:
        """Get the actions for a given input based on table type and priority."""
        fired = self.firing_rules(input_combo)
        if not fired:
            return None
        if self.table_type == TableType.SINGLE_HIT:
            return dict(fired[0][1].action_entries)
        else:
            # Multi-hit: merge all fired rule actions
            merged = {}
            for _, rule in fired:
                for k, v in rule.action_entries.items():
                    if v:  # non-empty action values accumulate
                        merged[k] = v
            # Fill in missing actions
            for action in self.actions:
                merged.setdefault(action.name, "")
            return merged

    def is_equivalent_to(self, other: DecisionTable) -> tuple[bool, list[dict]]:
        """Check if two tables produce identical outputs for all valid inputs.

        Returns (is_equivalent, list_of_differences).
        """
        diffs = []
        combos = self.valid_input_combinations()
        for combo in combos:
            my_actions = self.effective_actions(combo)
            other_actions = other.effective_actions(combo)
            if my_actions != other_actions:
                diffs.append({
                    "input": combo,
                    "table1_actions": my_actions,
                    "table2_actions": other_actions,
                })
        return len(diffs) == 0, diffs

    # ── Serialization ──

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "conditions": [c.to_dict() for c in self.conditions],
            "actions": [a.to_dict() for a in self.actions],
            "rules": [r.to_dict() for r in self.rules],
            "table_type": self.table_type.value,
            "metadata": {
                **self.metadata,
                "version": "2.0",
                "last_modified": datetime.now().isoformat(),
            },
        }
        if self.constraints:
            d["constraints"] = [c.to_dict() for c in self.constraints]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionTable:
        tt = TableType(data.get("table_type", "single_hit"))
        constraints = [Constraint.from_dict(c) for c in data.get("constraints", [])]
        return cls(
            name=data.get("name", "Untitled"),
            conditions=[Condition.from_dict(c) for c in data.get("conditions", [])],
            actions=[Action.from_dict(a) for a in data.get("actions", [])],
            rules=[Rule.from_dict(r) for r in data.get("rules", [])],
            constraints=constraints,
            table_type=tt,
            metadata=data.get("metadata", {}),
        )
