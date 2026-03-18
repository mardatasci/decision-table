"""Tests for logic reduction algorithms."""

from decision_table.model import Action, Condition, DecisionTable, Rule
from decision_table.reduction import compare_reductions, espresso, petricks_method, quine_mccluskey, rule_merging


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


class TestCompareReductions:
    def test_compare(self, redundant_table):
        comparison = compare_reductions(redundant_table)
        assert comparison.qm_result.method == "Quine-McCluskey"
        assert comparison.petrick_result.method == "Petrick's Method"
        assert comparison.rule_merging_result.method == "Rule Merging"
        assert comparison.espresso_result.method == "Espresso"

    def test_all_reduce(self, redundant_table):
        comparison = compare_reductions(redundant_table)
        for res in [comparison.qm_result, comparison.petrick_result,
                    comparison.rule_merging_result, comparison.espresso_result]:
            assert len(res.reduced_rules) <= len(res.original_rules)
