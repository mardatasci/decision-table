"""Tests for test case generation."""

from decision_table.model import Action, Condition, DecisionTable, Rule, make_numeric_condition
from decision_table.testing import (
    calculate_coverage, generate_all_tests, generate_boundary_tests,
    generate_pairwise_tests, generate_test_cases,
)


class TestGenerateTestCases:
    def test_one_per_rule(self, simple_boolean_table):
        tests = generate_test_cases(simple_boolean_table)
        assert len(tests) == 4
        for tc in tests:
            assert tc.test_type == "normal"
            assert tc.inputs
            assert tc.expected_outputs is not None

    def test_else_rule(self, else_table):
        tests = generate_test_cases(else_table)
        assert any(tc.test_type == "else" for tc in tests)

    def test_constrained(self, constrained_table):
        tests = generate_test_cases(constrained_table)
        # Should not generate test with A=T, B=T
        for tc in tests:
            assert not (tc.inputs.get("A") == "T" and tc.inputs.get("B") == "T")


class TestBoundaryTests:
    def test_numeric_boundaries(self, numeric_table):
        tests = generate_boundary_tests(numeric_table)
        assert len(tests) > 0
        for tc in tests:
            assert tc.test_type == "boundary"

    def test_no_numeric_returns_empty(self, simple_boolean_table):
        tests = generate_boundary_tests(simple_boolean_table)
        assert len(tests) == 0


class TestPairwiseTests:
    def test_covers_all_pairs(self, three_condition_table):
        tests = generate_pairwise_tests(three_condition_table)
        # With 3 boolean conditions, pairwise should cover all 2-way combos
        assert len(tests) >= 4

    def test_pairwise_type(self, simple_boolean_table):
        tests = generate_pairwise_tests(simple_boolean_table)
        for tc in tests:
            assert tc.test_type == "pairwise"


class TestCoverage:
    def test_full_coverage(self, simple_boolean_table):
        tests = generate_test_cases(simple_boolean_table)
        report = calculate_coverage(simple_boolean_table, tests)
        assert report.rule_coverage == 100.0
        assert len(report.uncovered_rules) == 0

    def test_partial_coverage(self, simple_boolean_table):
        # Only one test case
        tests = generate_test_cases(simple_boolean_table)[:1]
        report = calculate_coverage(simple_boolean_table, tests)
        assert report.rule_coverage < 100.0

    def test_summary(self, simple_boolean_table):
        tests = generate_test_cases(simple_boolean_table)
        report = calculate_coverage(simple_boolean_table, tests)
        summary = report.summary()
        assert "Rule coverage" in summary


class TestGenerateAllTests:
    def test_deduplication(self, simple_boolean_table):
        tests = generate_all_tests(simple_boolean_table)
        inputs = [tuple(sorted(tc.inputs.items())) for tc in tests]
        assert len(inputs) == len(set(inputs))  # no duplicates
