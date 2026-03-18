"""Test case generation: full coverage, boundary value analysis, pairwise, and coverage metrics."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any

from .model import DONT_CARE, DecisionTable, Rule


@dataclass
class TestCase:
    """A single test case derived from the decision table."""

    inputs: dict[str, str]
    expected_outputs: dict[str, str]
    covering_rules: list[int] = field(default_factory=list)
    test_type: str = "normal"  # normal, boundary, pairwise, else
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputs": dict(self.inputs),
            "expected_outputs": dict(self.expected_outputs),
            "covering_rules": self.covering_rules,
            "test_type": self.test_type,
            "description": self.description,
        }


@dataclass
class CoverageReport:
    """Coverage metrics for a set of test cases against a decision table."""

    total_rules: int
    covered_rules: set[int] = field(default_factory=set)
    total_conditions: int = 0
    condition_value_coverage: dict[str, set[str]] = field(default_factory=dict)
    total_actions: int = 0
    action_value_coverage: dict[str, set[str]] = field(default_factory=dict)

    @property
    def rule_coverage(self) -> float:
        if self.total_rules == 0:
            return 100.0
        return (len(self.covered_rules) / self.total_rules) * 100

    @property
    def uncovered_rules(self) -> set[int]:
        return set(range(self.total_rules)) - self.covered_rules

    def summary(self) -> str:
        lines = [
            f"Rule coverage: {len(self.covered_rules)}/{self.total_rules} ({self.rule_coverage:.0f}%)",
        ]
        if self.uncovered_rules:
            lines.append(f"Uncovered rules: {sorted(self.uncovered_rules)}")
        if self.condition_value_coverage:
            lines.append("Condition value coverage:")
            for cond, vals in sorted(self.condition_value_coverage.items()):
                lines.append(f"  {cond}: {sorted(vals)}")
        if self.action_value_coverage:
            lines.append("Action value coverage:")
            for act, vals in sorted(self.action_value_coverage.items()):
                lines.append(f"  {act}: {sorted(vals)}")
        return "\n".join(lines)


def generate_test_cases(table: DecisionTable) -> list[TestCase]:
    """Generate one test case per rule, covering all rules."""
    test_cases = []
    for i, rule in enumerate(table.rules):
        if rule.is_else:
            # For else rules, find an uncovered input
            covered_inputs = set()
            for j, r in enumerate(table.rules):
                if j != i and not r.is_else:
                    for expanded in r.expand_dont_cares(table.conditions):
                        key = tuple(sorted(expanded.condition_entries.items()))
                        covered_inputs.add(key)
            # Find any valid combo not covered by other rules
            for combo in table.valid_input_combinations():
                key = tuple(sorted(combo.items()))
                if key not in covered_inputs:
                    actions = table.effective_actions(combo)
                    test_cases.append(TestCase(
                        inputs=combo,
                        expected_outputs=actions or {},
                        covering_rules=[i],
                        test_type="else",
                        description=f"Else rule (R{i+1})",
                    ))
                    break
            continue

        # Pick the first expanded combination for this rule
        expanded = rule.expand_dont_cares(table.conditions)
        if expanded:
            combo = expanded[0].condition_entries
            # Filter out constrained combos
            if table.violates_constraints(combo) and len(expanded) > 1:
                for exp in expanded[1:]:
                    if not table.violates_constraints(exp.condition_entries):
                        combo = exp.condition_entries
                        break

            actions = table.effective_actions(combo)
            desc_parts = [f"{k}={v}" for k, v in sorted(combo.items())]
            test_cases.append(TestCase(
                inputs=dict(combo),
                expected_outputs=actions or {},
                covering_rules=[i],
                test_type="normal",
                description=f"R{i+1}: {', '.join(desc_parts)}",
            ))

    return test_cases


def generate_boundary_tests(table: DecisionTable) -> list[TestCase]:
    """Generate boundary value test cases for numeric conditions."""
    test_cases = []
    numeric_conds = [c for c in table.conditions if c.is_numeric and c.ranges]

    if not numeric_conds:
        return test_cases

    # For each numeric condition, generate tests at each boundary
    for cond in numeric_conds:
        boundaries = cond.boundary_values()
        for bval in boundaries:
            # Find which range this value falls into
            matching_range = None
            for r in cond.ranges:
                if r.contains(bval):
                    matching_range = r.label
                    break

            if matching_range is None:
                # Value falls outside all ranges (interesting boundary test)
                matching_range = "OUT_OF_RANGE"

            # Build a full input combo using this boundary value
            # Use first valid value for other conditions
            inputs = {}
            for c in table.conditions:
                if c.name == cond.name:
                    inputs[c.name] = matching_range
                else:
                    inputs[c.name] = c.possible_values[0] if c.possible_values else DONT_CARE

            if table.violates_constraints(inputs):
                continue

            actions = table.effective_actions(inputs)
            test_cases.append(TestCase(
                inputs=inputs,
                expected_outputs=actions or {},
                test_type="boundary",
                description=f"Boundary: {cond.name}={bval} (range: {matching_range})",
            ))

    # Deduplicate by input
    seen = set()
    unique = []
    for tc in test_cases:
        key = tuple(sorted(tc.inputs.items()))
        if key not in seen:
            seen.add(key)
            unique.append(tc)

    return unique


def generate_pairwise_tests(table: DecisionTable) -> list[TestCase]:
    """Generate pairwise (all-pairs) test cases covering all 2-way value combinations."""
    if len(table.conditions) < 2:
        return generate_test_cases(table)

    cond_names = [c.name for c in table.conditions]
    cond_values = {c.name: c.possible_values for c in table.conditions}

    # Collect all pairs that need to be covered
    uncovered_pairs: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for i in range(len(cond_names)):
        for j in range(i + 1, len(cond_names)):
            c1, c2 = cond_names[i], cond_names[j]
            for v1 in cond_values[c1]:
                for v2 in cond_values[c2]:
                    uncovered_pairs.setdefault((c1, c2), set()).add((v1, v2))

    test_cases = []

    # Greedy algorithm: pick test cases that cover the most uncovered pairs
    while any(pairs for pairs in uncovered_pairs.values()):
        best_combo = None
        best_count = -1

        # Try all combinations to find the one covering the most uncovered pairs
        for vals in itertools.product(*[cond_values[c] for c in cond_names]):
            combo = dict(zip(cond_names, vals))
            if table.violates_constraints(combo):
                continue

            count = 0
            for i in range(len(cond_names)):
                for j in range(i + 1, len(cond_names)):
                    c1, c2 = cond_names[i], cond_names[j]
                    pair = (combo[c1], combo[c2])
                    if pair in uncovered_pairs.get((c1, c2), set()):
                        count += 1

            if count > best_count:
                best_count = count
                best_combo = combo

        if best_combo is None or best_count == 0:
            break

        # Mark pairs as covered
        for i in range(len(cond_names)):
            for j in range(i + 1, len(cond_names)):
                c1, c2 = cond_names[i], cond_names[j]
                pair = (best_combo[c1], best_combo[c2])
                uncovered_pairs.get((c1, c2), set()).discard(pair)

        actions = table.effective_actions(best_combo)
        desc_parts = [f"{k}={v}" for k, v in sorted(best_combo.items())]
        test_cases.append(TestCase(
            inputs=best_combo,
            expected_outputs=actions or {},
            test_type="pairwise",
            description=f"Pairwise: {', '.join(desc_parts)}",
        ))

    # Determine covering rules
    for tc in test_cases:
        tc.covering_rules = [i for i, rule in enumerate(table.rules) if rule.covers(tc.inputs)]

    return test_cases


def calculate_coverage(table: DecisionTable, test_cases: list[TestCase]) -> CoverageReport:
    """Calculate coverage metrics for a set of test cases."""
    report = CoverageReport(
        total_rules=len(table.rules),
        total_conditions=len(table.conditions),
        total_actions=len(table.actions),
    )

    for cond in table.conditions:
        report.condition_value_coverage[cond.name] = set()
    for action in table.actions:
        report.action_value_coverage[action.name] = set()

    for tc in test_cases:
        # Track which rules are covered
        for i, rule in enumerate(table.rules):
            if rule.covers(tc.inputs):
                report.covered_rules.add(i)

        # Track condition value coverage
        for cond_name, value in tc.inputs.items():
            if cond_name in report.condition_value_coverage:
                report.condition_value_coverage[cond_name].add(value)

        # Track action value coverage
        for act_name, value in tc.expected_outputs.items():
            if act_name in report.action_value_coverage:
                report.action_value_coverage[act_name].add(value)

    return report


def generate_all_tests(table: DecisionTable) -> list[TestCase]:
    """Generate a comprehensive test suite: normal + boundary + pairwise, deduplicated."""
    all_tests = []
    seen = set()

    for tc in generate_test_cases(table):
        key = tuple(sorted(tc.inputs.items()))
        if key not in seen:
            seen.add(key)
            all_tests.append(tc)

    for tc in generate_boundary_tests(table):
        key = tuple(sorted(tc.inputs.items()))
        if key not in seen:
            seen.add(key)
            all_tests.append(tc)

    for tc in generate_pairwise_tests(table):
        key = tuple(sorted(tc.inputs.items()))
        if key not in seen:
            seen.add(key)
            all_tests.append(tc)

    return all_tests


def export_test_cases_csv(test_cases: list[TestCase], table: DecisionTable, path: str) -> None:
    """Export test cases to CSV."""
    import csv
    from pathlib import Path

    cond_names = [c.name for c in table.conditions]
    act_names = [a.name for a in table.actions]

    with open(Path(path), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["#", "Type", "Description"] + cond_names + act_names + ["Covering Rules"]
        writer.writerow(header)
        for i, tc in enumerate(test_cases, 1):
            row = [
                i,
                tc.test_type,
                tc.description,
            ]
            row.extend(tc.inputs.get(c, "") for c in cond_names)
            row.extend(tc.expected_outputs.get(a, "") for a in act_names)
            row.append(", ".join(f"R{r+1}" for r in tc.covering_rules))
            writer.writerow(row)
