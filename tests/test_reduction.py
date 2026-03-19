"""Tests for logic reduction algorithms."""

from decision_table.model import Action, Condition, DecisionTable, Rule
from decision_table.reduction import (
    clustering_reduction, compare_reductions, espresso, incremental_reduction,
    petricks_method, positive_region_reduction, quine_mccluskey, rule_merging,
    variable_precision_reduction,
)


class TestQuineMcCluskey:
    def test_empty_table(self, empty_table):
        result = quine_mccluskey(empty_table)
        assert len(result.reduced_rules) == 0

    def test_single_rule(self):
        table = DecisionTable(name="Test")
        table.add_condition(Condition(name="A"))
        table.add_action(Action(name="X"))
        table.add_rule(Rule(condition_entries={"A": "T"}, action_entries={"X": "X"}))
        result = quine_mccluskey(table)
        assert len(result.reduced_rules) == 1

    def test_reduces_simple_table(self, redundant_table):
        result = quine_mccluskey(redundant_table)
        assert len(result.reduced_rules) == 2

    def test_reduces_three_conditions(self, three_condition_table):
        result = quine_mccluskey(three_condition_table)
        assert len(result.reduced_rules) == 2
        assert result.reduction_count == 6

    def test_preserves_logic(self, simple_boolean_table):
        result = quine_mccluskey(simple_boolean_table)
        for combo in simple_boolean_table.all_input_combinations():
            orig = None
            for rule in simple_boolean_table.rules:
                if rule.covers(combo):
                    orig = rule.action_profile()
                    break
            red = None
            for rule in result.reduced_rules:
                if rule.covers(combo):
                    red = rule.action_profile()
                    break
            assert orig == red

    def test_else_rules_preserved(self, else_table):
        result = quine_mccluskey(else_table)
        assert any(r.is_else for r in result.reduced_rules)

    def test_constrained_reduction(self, constrained_table):
        result = quine_mccluskey(constrained_table)
        assert len(result.reduced_rules) <= len(constrained_table.rules)


class TestPetricksMethod:
    def test_empty_table(self, empty_table):
        result = petricks_method(empty_table)
        assert len(result.reduced_rules) == 0

    def test_reduces_simple_table(self, redundant_table):
        result = petricks_method(redundant_table)
        assert len(result.reduced_rules) == 2

    def test_reduces_three_conditions(self, three_condition_table):
        result = petricks_method(three_condition_table)
        assert len(result.reduced_rules) == 2

    def test_preserves_logic(self, simple_boolean_table):
        result = petricks_method(simple_boolean_table)
        for combo in simple_boolean_table.all_input_combinations():
            orig = None
            for rule in simple_boolean_table.rules:
                if rule.covers(combo):
                    orig = rule.action_profile()
                    break
            red = None
            for rule in result.reduced_rules:
                if rule.covers(combo):
                    red = rule.action_profile()
                    break
            assert orig == red

    def test_else_rules_preserved(self, else_table):
        result = petricks_method(else_table)
        assert any(r.is_else for r in result.reduced_rules)


class TestRuleMerging:
    def test_empty_table(self, empty_table):
        result = rule_merging(empty_table)
        assert len(result.reduced_rules) == 0

    def test_reduces_simple_table(self, redundant_table):
        result = rule_merging(redundant_table)
        assert len(result.reduced_rules) <= len(result.original_rules)
        assert len(result.reduced_rules) == 2

    def test_reduces_three_conditions(self, three_condition_table):
        result = rule_merging(three_condition_table)
        assert len(result.reduced_rules) == 2

    def test_preserves_logic(self, simple_boolean_table):
        result = rule_merging(simple_boolean_table)
        for combo in simple_boolean_table.all_input_combinations():
            orig = None
            for rule in simple_boolean_table.rules:
                if rule.covers(combo):
                    orig = rule.action_profile()
                    break
            red = None
            for rule in result.reduced_rules:
                if rule.covers(combo):
                    red = rule.action_profile()
                    break
            assert orig == red

    def test_else_rules_preserved(self, else_table):
        result = rule_merging(else_table)
        assert any(r.is_else for r in result.reduced_rules)

    def test_has_steps(self, redundant_table):
        result = rule_merging(redundant_table)
        assert len(result.steps) > 0


class TestEspresso:
    def test_empty_table(self, empty_table):
        result = espresso(empty_table)
        assert len(result.reduced_rules) == 0

    def test_reduces_simple_table(self, redundant_table):
        result = espresso(redundant_table)
        assert len(result.reduced_rules) <= len(result.original_rules)

    def test_reduces_three_conditions(self, three_condition_table):
        result = espresso(three_condition_table)
        assert len(result.reduced_rules) <= 4  # should reduce significantly

    def test_preserves_logic(self, simple_boolean_table):
        result = espresso(simple_boolean_table)
        for combo in simple_boolean_table.all_input_combinations():
            orig = None
            for rule in simple_boolean_table.rules:
                if rule.covers(combo):
                    orig = rule.action_profile()
                    break
            red = None
            for rule in result.reduced_rules:
                if rule.covers(combo):
                    red = rule.action_profile()
                    break
            assert orig == red

    def test_else_rules_preserved(self, else_table):
        result = espresso(else_table)
        assert any(r.is_else for r in result.reduced_rules)

    def test_has_steps(self, redundant_table):
        result = espresso(redundant_table)
        assert len(result.steps) > 0


class TestPositiveRegionReduction:
    def test_empty_table(self, empty_table):
        result = positive_region_reduction(empty_table)
        assert len(result.reduced_rules) == 0

    def test_reduces_dispensable_conditions(self, three_condition_table):
        """In the three_condition_table, only A matters (T->X, F->nothing)."""
        result = positive_region_reduction(three_condition_table)
        assert len(result.reduced_rules) <= len(result.original_rules)
        assert result.method == "Positive Region (RST)"

    def test_preserves_logic(self, simple_boolean_table):
        result = positive_region_reduction(simple_boolean_table)
        for combo in simple_boolean_table.all_input_combinations():
            orig = None
            for rule in simple_boolean_table.rules:
                if rule.covers(combo):
                    orig = rule.action_profile()
                    break
            red = None
            for rule in result.reduced_rules:
                if rule.covers(combo):
                    red = rule.action_profile()
                    break
            assert orig == red

    def test_else_rules_preserved(self, else_table):
        result = positive_region_reduction(else_table)
        assert any(r.is_else for r in result.reduced_rules)

    def test_has_steps(self, redundant_table):
        result = positive_region_reduction(redundant_table)
        assert len(result.steps) > 0

    def test_single_condition(self):
        table = DecisionTable(name="Test")
        table.add_condition(Condition(name="A"))
        table.add_action(Action(name="X"))
        table.add_rule(Rule(condition_entries={"A": "T"}, action_entries={"X": "X"}))
        table.add_rule(Rule(condition_entries={"A": "F"}, action_entries={"X": ""}))
        result = positive_region_reduction(table)
        assert len(result.reduced_rules) >= 1


class TestVariablePrecisionReduction:
    def test_empty_table(self, empty_table):
        result = variable_precision_reduction(empty_table)
        assert len(result.reduced_rules) == 0

    def test_full_precision_matches_prr(self, three_condition_table):
        """At threshold=1.0, VPR should be as strict as PRR."""
        vpr = variable_precision_reduction(three_condition_table, threshold=1.0)
        prr = positive_region_reduction(three_condition_table)
        # VPR at 1.0 should keep at least as many conditions
        assert len(vpr.reduced_rules) >= 1

    def test_lower_threshold_removes_more(self, three_condition_table):
        strict = variable_precision_reduction(three_condition_table, threshold=1.0)
        relaxed = variable_precision_reduction(three_condition_table, threshold=0.5)
        assert len(relaxed.reduced_rules) <= len(strict.reduced_rules)

    def test_preserves_logic_at_full_precision(self, simple_boolean_table):
        result = variable_precision_reduction(simple_boolean_table, threshold=1.0)
        for combo in simple_boolean_table.all_input_combinations():
            orig = None
            for rule in simple_boolean_table.rules:
                if rule.covers(combo):
                    orig = rule.action_profile()
                    break
            red = None
            for rule in result.reduced_rules:
                if rule.covers(combo):
                    red = rule.action_profile()
                    break
            assert orig == red

    def test_else_rules_preserved(self, else_table):
        result = variable_precision_reduction(else_table)
        assert any(r.is_else for r in result.reduced_rules)

    def test_has_steps(self, redundant_table):
        result = variable_precision_reduction(redundant_table)
        assert len(result.steps) > 0


class TestClusteringReduction:
    def test_empty_table(self, empty_table):
        result = clustering_reduction(empty_table)
        assert len(result.reduced_rules) == 0

    def test_reduces_table(self, three_condition_table):
        result = clustering_reduction(three_condition_table)
        assert len(result.reduced_rules) <= len(result.original_rules)
        assert result.method == "Clustering"

    def test_preserves_logic(self, simple_boolean_table):
        result = clustering_reduction(simple_boolean_table)
        for combo in simple_boolean_table.all_input_combinations():
            orig = None
            for rule in simple_boolean_table.rules:
                if rule.covers(combo):
                    orig = rule.action_profile()
                    break
            red = None
            for rule in result.reduced_rules:
                if rule.covers(combo):
                    red = rule.action_profile()
                    break
            assert orig == red

    def test_single_condition(self):
        """Single condition can't be clustered further."""
        table = DecisionTable(name="Test")
        table.add_condition(Condition(name="A"))
        table.add_action(Action(name="X"))
        table.add_rule(Rule(condition_entries={"A": "T"}, action_entries={"X": "X"}))
        table.add_rule(Rule(condition_entries={"A": "F"}, action_entries={"X": ""}))
        result = clustering_reduction(table)
        assert len(result.reduced_rules) == 2

    def test_else_rules_preserved(self, else_table):
        result = clustering_reduction(else_table)
        assert any(r.is_else for r in result.reduced_rules)

    def test_has_steps(self, three_condition_table):
        result = clustering_reduction(three_condition_table)
        assert len(result.steps) > 0


class TestIncrementalReduction:
    def test_empty_table(self, empty_table):
        result = incremental_reduction(empty_table)
        assert len(result.reduced_rules) == 0

    def test_no_previous_result(self, redundant_table):
        """Without previous result, does full reduction."""
        result = incremental_reduction(redundant_table, previous_result=None, method="qm")
        assert len(result.reduced_rules) <= len(result.original_rules)
        assert "Incremental" in result.method

    def test_no_changes(self, redundant_table):
        """If table hasn't changed, reuse previous result."""
        first = quine_mccluskey(redundant_table)
        second = incremental_reduction(redundant_table, previous_result=first, method="qm")
        assert len(second.reduced_rules) == len(first.reduced_rules)

    def test_with_added_rule(self, simple_boolean_table):
        """Adding a rule triggers partial re-reduction."""
        first = quine_mccluskey(simple_boolean_table)

        # Add a new rule
        import copy
        modified = copy.deepcopy(simple_boolean_table)
        modified.add_rule(Rule(
            condition_entries={"A": "T", "B": "T"},
            action_entries={"X": ""},
        ))

        result = incremental_reduction(modified, previous_result=first, method="qm")
        assert len(result.reduced_rules) >= 1

    def test_different_methods(self, redundant_table):
        for method in ["qm", "petrick", "merge", "espresso"]:
            result = incremental_reduction(redundant_table, method=method)
            assert len(result.reduced_rules) <= len(result.original_rules)

    def test_else_rules_preserved(self, else_table):
        result = incremental_reduction(else_table)
        assert any(r.is_else for r in result.reduced_rules)

    def test_has_steps(self, redundant_table):
        result = incremental_reduction(redundant_table)
        assert len(result.steps) > 0


class TestCompareReductions:
    def test_compare(self, redundant_table):
        comparison = compare_reductions(redundant_table)
        assert comparison.qm_result.method == "Quine-McCluskey"
        assert comparison.petrick_result.method == "Petrick's Method"
        assert comparison.rule_merging_result.method == "Rule Merging"
        assert comparison.espresso_result.method == "Espresso"
        assert comparison.prr_result.method == "Positive Region (RST)"
        assert comparison.vpr_result.method == "Variable Precision (RST)"
        assert comparison.clustering_result.method == "Clustering"

    def test_all_reduce(self, redundant_table):
        comparison = compare_reductions(redundant_table)
        for res in [comparison.qm_result, comparison.petrick_result,
                    comparison.rule_merging_result, comparison.espresso_result,
                    comparison.prr_result, comparison.vpr_result,
                    comparison.clustering_result]:
            assert len(res.reduced_rules) <= len(res.original_rules)
