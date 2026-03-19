"""Logic reduction using Quine-McCluskey algorithm and Petrick's Method."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any

from .model import DONT_CARE, Action, Condition, DecisionTable, Rule


@dataclass
class ReductionStep:
    """Records one step in the reduction process for educational display."""

    description: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReductionResult:
    """Result of a reduction algorithm."""

    method: str
    original_rules: list[Rule]
    reduced_rules: list[Rule]
    steps: list[ReductionStep] = field(default_factory=list)

    @property
    def reduction_count(self) -> int:
        return len(self.original_rules) - len(self.reduced_rules)

    @property
    def reduction_percentage(self) -> float:
        if not self.original_rules:
            return 0.0
        return (self.reduction_count / len(self.original_rules)) * 100


def _encode_rule_binary(rule: Rule, conditions: list[Condition]) -> str:
    """Encode a rule's condition entries as a binary string.

    For boolean conditions: T=1, F=0, -=-.
    For multi-valued conditions, each value gets a bit position.
    """
    bits = []
    for cond in conditions:
        entry = rule.condition_entries.get(cond.name, DONT_CARE)
        if cond.is_boolean:
            if entry == "T":
                bits.append("1")
            elif entry == "F":
                bits.append("0")
            else:
                bits.append("-")
        else:
            # Multi-valued: use one-hot encoding
            for val in cond.possible_values:
                if entry == DONT_CARE:
                    bits.append("-")
                elif entry == val:
                    bits.append("1")
                else:
                    bits.append("0")
    return "".join(bits)


def _decode_binary_rule(binary: str, conditions: list[Condition], actions: dict[str, str]) -> Rule:
    """Decode a binary string back to a Rule."""
    condition_entries = {}
    pos = 0
    for cond in conditions:
        if cond.is_boolean:
            bit = binary[pos]
            if bit == "1":
                condition_entries[cond.name] = "T"
            elif bit == "0":
                condition_entries[cond.name] = "F"
            else:
                condition_entries[cond.name] = DONT_CARE
            pos += 1
        else:
            bits = binary[pos:pos + len(cond.possible_values)]
            if all(b == "-" for b in bits):
                condition_entries[cond.name] = DONT_CARE
            else:
                for k, val in enumerate(cond.possible_values):
                    if bits[k] == "1":
                        condition_entries[cond.name] = val
                        break
            pos += len(cond.possible_values)
    return Rule(condition_entries=condition_entries, action_entries=dict(actions))


def _binary_to_combo(binary: str, conditions: list[Condition]) -> dict[str, str]:
    """Convert a fully-specified binary minterm to a condition combo dict.

    Used for constraint checking. The binary string must be fully specified
    (no don't-care '-' positions).
    """
    combo: dict[str, str] = {}
    pos = 0
    for cond in conditions:
        if cond.is_boolean:
            combo[cond.name] = "T" if binary[pos] == "1" else "F"
            pos += 1
        else:
            for k, val in enumerate(cond.possible_values):
                if binary[pos + k] == "1":
                    combo[cond.name] = val
                    break
            pos += len(cond.possible_values)
    return combo


def _filter_valid_minterms(
    minterms: set[str], table: DecisionTable
) -> set[str]:
    """Remove minterms that violate table constraints.

    Constrained-out minterms are effectively don't-cares and don't need
    coverage during reduction.
    """
    if not table.constraints:
        return minterms
    return {
        mt for mt in minterms
        if not table.violates_constraints(_binary_to_combo(mt, table.conditions))
    }


def _can_combine(a: str, b: str) -> tuple[bool, int]:
    """Check if two binary strings differ in exactly one non-don't-care position."""
    if len(a) != len(b):
        return False, -1
    diff_pos = -1
    diff_count = 0
    for i in range(len(a)):
        if a[i] == "-" and b[i] == "-":
            continue
        if a[i] == "-" or b[i] == "-":
            return False, -1  # Can't combine if don't-care vs non-don't-care
        if a[i] != b[i]:
            diff_count += 1
            diff_pos = i
            if diff_count > 1:
                return False, -1
    return diff_count == 1, diff_pos


def _combine(a: str, b: str, pos: int) -> str:
    """Combine two binary strings at the differing position."""
    result = list(a)
    result[pos] = "-"
    return "".join(result)


def _minterms_covered(binary: str) -> set[str]:
    """Return the set of fully-specified minterms covered by a (possibly don't-care) binary."""
    positions = [i for i, b in enumerate(binary) if b == "-"]
    if not positions:
        return {binary}

    result = set()
    base = list(binary)
    for bits in range(2 ** len(positions)):
        term = list(base)
        for k, pos in enumerate(positions):
            term[pos] = "1" if (bits >> (len(positions) - 1 - k)) & 1 else "0"
        result.add("".join(term))
    return result


def _collapse_multi_valued(rules: list[Rule], conditions: list[Condition]) -> list[Rule]:
    """Post-process: collapse rules that only differ on one multi-valued condition
    and cover all its values back into a single don't-care rule.

    This fixes the limitation where QM one-hot encoding can't recombine
    multi-valued conditions (e.g., 3-value enums expand to 3 rules that
    should be 1 rule with '-').
    """
    if not rules or not conditions:
        return rules

    multi_conds = [c for c in conditions if len(c.possible_values) > 2]
    if not multi_conds:
        return rules

    changed = True
    result = list(rules)

    while changed:
        changed = False
        for cond in multi_conds:
            # Group rules by everything except this condition
            groups: dict[tuple, list[Rule]] = {}
            for rule in result:
                key_parts = []
                for c in conditions:
                    if c.name == cond.name:
                        continue
                    key_parts.append((c.name, rule.condition_entries.get(c.name, DONT_CARE)))
                # Include actions in the key
                key_parts.extend(sorted(rule.action_entries.items()))
                key_parts.append(("__priority", str(rule.priority)))
                groups.setdefault(tuple(key_parts), []).append(rule)

            new_result = []
            consumed = set()
            for key, group in groups.items():
                # Check if this group covers all values of the condition
                covered_values = {r.condition_entries.get(cond.name, DONT_CARE) for r in group}
                if covered_values == set(cond.possible_values) or (
                    DONT_CARE in covered_values and len(group) >= len(cond.possible_values)
                ):
                    # Collapse into one rule with don't-care
                    base = group[0]
                    collapsed = Rule(
                        condition_entries={**base.condition_entries, cond.name: DONT_CARE},
                        action_entries=dict(base.action_entries),
                        priority=base.priority,
                    )
                    new_result.append(collapsed)
                    for r in group:
                        consumed.add(id(r))
                    changed = True
                else:
                    for r in group:
                        if id(r) not in consumed:
                            new_result.append(r)
                            consumed.add(id(r))

            if changed:
                result = new_result
                break  # restart outer loop with updated result

    return result


def _split_else_rules(rules: list[Rule]) -> tuple[list[Rule], list[Rule]]:
    """Separate else rules from normal rules.

    Returns (normal_rules, else_rules).
    """
    normal = []
    else_rules = []
    for rule in rules:
        if rule.is_else:
            else_rules.append(rule)
        else:
            normal.append(rule)
    return normal, else_rules


def quine_mccluskey(table: DecisionTable) -> ReductionResult:
    """Reduce a decision table using the Quine-McCluskey algorithm."""
    steps: list[ReductionStep] = []

    if not table.rules or not table.conditions:
        return ReductionResult("Quine-McCluskey", list(table.rules), list(table.rules), steps)

    # Separate else rules -- they are kept as-is and re-added at the end
    normal_rules, else_rules = _split_else_rules(table.rules)

    if not normal_rules:
        return ReductionResult("Quine-McCluskey", list(table.rules), list(else_rules), steps)

    # Group rules by action profile
    action_groups: dict[tuple, list[int]] = {}
    for i, rule in enumerate(normal_rules):
        profile = rule.action_profile()
        action_groups.setdefault(profile, []).append(i)

    steps.append(ReductionStep(
        "Group rules by action profile",
        {"groups": {str(k): v for k, v in action_groups.items()}},
    ))

    if else_rules:
        steps.append(ReductionStep(
            "Else rules preserved without reduction",
            {"else_rule_count": len(else_rules)},
        ))

    all_reduced_rules: list[Rule] = []

    for profile, rule_indices in action_groups.items():
        actions = dict(profile)
        group_rules = [normal_rules[i] for i in rule_indices]

        # Expand don't-cares to get all minterms
        expanded: list[Rule] = []
        for rule in group_rules:
            expanded.extend(rule.expand_dont_cares(table.conditions))

        # Encode as binary
        minterms: set[str] = set()
        for rule in expanded:
            minterms.add(_encode_rule_binary(rule, table.conditions))

        # Filter out minterms that violate constraints (they are don't-cares)
        minterms = _filter_valid_minterms(minterms, table)

        if not minterms:
            # All minterms for this group are constrained out; skip
            steps.append(ReductionStep(
                f"All minterms constrained out for action profile {actions}",
                {"minterms": []},
            ))
            continue

        steps.append(ReductionStep(
            f"Encoded minterms for action profile {actions}",
            {"minterms": sorted(minterms)},
        ))

        # Iterative combination
        prime_implicants: set[str] = set()
        current = minterms

        iteration = 0
        while current:
            iteration += 1
            used = set()
            next_level: set[str] = set()

            terms = sorted(current)
            for i in range(len(terms)):
                for j in range(i + 1, len(terms)):
                    can, pos = _can_combine(terms[i], terms[j])
                    if can:
                        combined = _combine(terms[i], terms[j], pos)
                        next_level.add(combined)
                        used.add(terms[i])
                        used.add(terms[j])

            # Unused terms are prime implicants
            for term in terms:
                if term not in used:
                    prime_implicants.add(term)

            steps.append(ReductionStep(
                f"QM iteration {iteration} for {actions}",
                {
                    "terms": terms,
                    "combined": sorted(next_level),
                    "new_prime_implicants": sorted(prime_implicants - (prime_implicants - {t for t in terms if t not in used})),
                },
            ))

            current = next_level

        steps.append(ReductionStep(
            f"Prime implicants for {actions}",
            {"prime_implicants": sorted(prime_implicants)},
        ))

        # Select minimal cover using greedy approach
        remaining_minterms = set(minterms)
        selected: list[str] = []

        # First, find essential prime implicants
        for minterm in sorted(minterms):
            covering_pis = [pi for pi in prime_implicants if minterm in _minterms_covered(pi)]
            if len(covering_pis) == 1:
                pi = covering_pis[0]
                if pi not in selected:
                    selected.append(pi)
                    remaining_minterms -= _minterms_covered(pi)

        steps.append(ReductionStep(
            f"Essential prime implicants for {actions}",
            {"essential": selected, "remaining_minterms": sorted(remaining_minterms)},
        ))

        # Greedy cover for remaining
        available_pis = sorted(prime_implicants - set(selected))
        while remaining_minterms:
            best = max(available_pis, key=lambda pi: len(_minterms_covered(pi) & remaining_minterms))
            selected.append(best)
            remaining_minterms -= _minterms_covered(best)
            available_pis.remove(best)

        # Decode back to rules
        for binary in selected:
            all_reduced_rules.append(_decode_binary_rule(binary, table.conditions, actions))

    # Collapse multi-valued conditions back into don't-cares where possible
    all_reduced_rules = _collapse_multi_valued(all_reduced_rules, table.conditions)

    # Re-add else rules at the end
    all_reduced_rules.extend(else_rules)

    steps.append(ReductionStep(
        "Reduction complete",
        {
            "original_count": len(table.rules),
            "reduced_count": len(all_reduced_rules),
        },
    ))

    return ReductionResult("Quine-McCluskey", list(table.rules), all_reduced_rules, steps)


def petricks_method(table: DecisionTable) -> ReductionResult:
    """Reduce a decision table using Petrick's Method (builds on QM prime implicants)."""
    steps: list[ReductionStep] = []

    if not table.rules or not table.conditions:
        return ReductionResult("Petrick's Method", list(table.rules), list(table.rules), steps)

    # Separate else rules -- they are kept as-is and re-added at the end
    normal_rules, else_rules = _split_else_rules(table.rules)

    if not normal_rules:
        return ReductionResult("Petrick's Method", list(table.rules), list(else_rules), steps)

    # Group rules by action profile
    action_groups: dict[tuple, list[int]] = {}
    for i, rule in enumerate(normal_rules):
        profile = rule.action_profile()
        action_groups.setdefault(profile, []).append(i)

    if else_rules:
        steps.append(ReductionStep(
            "Else rules preserved without reduction",
            {"else_rule_count": len(else_rules)},
        ))

    all_reduced_rules: list[Rule] = []

    for profile, rule_indices in action_groups.items():
        actions = dict(profile)
        group_rules = [normal_rules[i] for i in rule_indices]

        # Get minterms
        expanded: list[Rule] = []
        for rule in group_rules:
            expanded.extend(rule.expand_dont_cares(table.conditions))

        all_minterms: set[str] = {
            _encode_rule_binary(rule, table.conditions) for rule in expanded
        }

        # Filter out minterms that violate constraints (they are don't-cares)
        valid_minterms = _filter_valid_minterms(all_minterms, table)
        minterms: list[str] = sorted(valid_minterms)

        if not minterms:
            # All minterms for this group are constrained out; skip
            steps.append(ReductionStep(
                f"All minterms constrained out for action profile {actions}",
                {"minterms": []},
            ))
            continue

        # Get prime implicants via QM iteration
        prime_implicants: set[str] = set()
        current = set(minterms)

        while current:
            used = set()
            next_level: set[str] = set()
            terms = sorted(current)
            for i in range(len(terms)):
                for j in range(i + 1, len(terms)):
                    can, pos = _can_combine(terms[i], terms[j])
                    if can:
                        combined = _combine(terms[i], terms[j], pos)
                        next_level.add(combined)
                        used.add(terms[i])
                        used.add(terms[j])
            for term in terms:
                if term not in used:
                    prime_implicants.add(term)
            current = next_level

        pi_list = sorted(prime_implicants)

        steps.append(ReductionStep(
            f"Prime implicants for {actions}",
            {"prime_implicants": pi_list},
        ))

        # Build PI chart: which PIs cover which minterms
        pi_coverage: dict[str, set[str]] = {}
        for pi in pi_list:
            pi_coverage[pi] = _minterms_covered(pi) & set(minterms)

        steps.append(ReductionStep(
            f"PI coverage chart for {actions}",
            {"chart": {pi: sorted(covered) for pi, covered in pi_coverage.items()}},
        ))

        # Find essential PIs
        essential: list[str] = []
        remaining_minterms = set(minterms)
        for mt in minterms:
            covering = [pi for pi in pi_list if mt in pi_coverage[pi]]
            if len(covering) == 1 and covering[0] not in essential:
                essential.append(covering[0])

        for pi in essential:
            remaining_minterms -= pi_coverage[pi]

        steps.append(ReductionStep(
            f"Essential PIs for {actions}",
            {"essential": essential, "remaining_minterms": sorted(remaining_minterms)},
        ))

        if not remaining_minterms:
            # Essential PIs cover everything
            selected = essential
        else:
            # Petrick's method: build product-of-sums
            remaining_pis = [pi for pi in pi_list if pi not in essential]

            # For each uncovered minterm, find which remaining PIs cover it
            pos_terms: list[set[str]] = []
            for mt in sorted(remaining_minterms):
                covering = {pi for pi in remaining_pis if mt in pi_coverage[pi]}
                if covering:
                    pos_terms.append(covering)

            steps.append(ReductionStep(
                f"Petrick's POS expression for {actions}",
                {"terms": [sorted(t) for t in pos_terms]},
            ))

            if not pos_terms:
                selected = essential
            else:
                # Multiply out POS to get SOP (all minimal covers)
                # Start with first term
                products: list[set[str]] = [{pi} for pi in pos_terms[0]]

                for term in pos_terms[1:]:
                    new_products: list[set[str]] = []
                    for existing in products:
                        for pi in term:
                            new_set = existing | {pi}
                            # Absorption: skip if a smaller set already exists
                            if not any(other < new_set for other in new_products):
                                # Remove any larger sets
                                new_products = [p for p in new_products if not new_set < p]
                                if new_set not in new_products:
                                    new_products.append(new_set)
                    products = new_products

                # Find minimum-cost cover
                min_size = min(len(p) for p in products)
                minimal_covers = [p for p in products if len(p) == min_size]

                steps.append(ReductionStep(
                    f"Minimal covers for {actions}",
                    {"covers": [sorted(c) for c in minimal_covers], "count": len(minimal_covers)},
                ))

                # Pick the first minimal cover
                selected = essential + sorted(minimal_covers[0])

        # Decode back to rules
        for binary in selected:
            all_reduced_rules.append(_decode_binary_rule(binary, table.conditions, actions))

    # Collapse multi-valued conditions back into don't-cares where possible
    all_reduced_rules = _collapse_multi_valued(all_reduced_rules, table.conditions)

    # Re-add else rules at the end
    all_reduced_rules.extend(else_rules)

    steps.append(ReductionStep(
        "Reduction complete",
        {
            "original_count": len(table.rules),
            "reduced_count": len(all_reduced_rules),
        },
    ))

    return ReductionResult("Petrick's Method", list(table.rules), all_reduced_rules, steps)


def rule_merging(table: DecisionTable) -> ReductionResult:
    """Reduce by iteratively merging rule pairs that differ in exactly one condition.

    This is the most intuitive algorithm: scan all pairs of rules with the same
    actions. If two rules differ in exactly one condition and together cover all
    values of that condition, replace them with a single rule using don't-care.
    Repeat until no more merges are possible.

    Works directly on the table representation (no binary encoding) so it
    handles multi-valued and numeric conditions naturally.
    """
    steps: list[ReductionStep] = []

    if not table.rules or not table.conditions:
        return ReductionResult("Rule Merging", list(table.rules), list(table.rules), steps)

    normal_rules, else_rules = _split_else_rules(table.rules)
    if not normal_rules:
        return ReductionResult("Rule Merging", list(table.rules), list(else_rules), steps)

    import copy
    rules = [copy.deepcopy(r) for r in normal_rules]
    cond_values = {c.name: set(c.possible_values) for c in table.conditions}

    iteration = 0
    changed = True

    while changed:
        changed = False
        iteration += 1
        merges_this_round = []

        i = 0
        while i < len(rules):
            j = i + 1
            merged = False
            while j < len(rules):
                ri, rj = rules[i], rules[j]

                # Must have same action profile
                if ri.action_profile() != rj.action_profile():
                    j += 1
                    continue

                # Find conditions where they differ
                diff_conds = []
                for cond_name in cond_values:
                    vi = ri.condition_entries.get(cond_name, DONT_CARE)
                    vj = rj.condition_entries.get(cond_name, DONT_CARE)
                    if vi != vj:
                        diff_conds.append(cond_name)

                if len(diff_conds) == 1:
                    dc = diff_conds[0]
                    vi = ri.condition_entries.get(dc, DONT_CARE)
                    vj = rj.condition_entries.get(dc, DONT_CARE)

                    # Collect all values covered by the two rules for this condition
                    covered = set()
                    if vi == DONT_CARE:
                        covered |= cond_values[dc]
                    else:
                        covered.add(vi)
                    if vj == DONT_CARE:
                        covered |= cond_values[dc]
                    else:
                        covered.add(vj)

                    if covered >= cond_values[dc]:
                        # Merge: replace with don't-care
                        merges_this_round.append(
                            f"Merged rules differing on '{dc}' "
                            f"({vi} + {vj} -> {DONT_CARE})"
                        )
                        ri.condition_entries[dc] = DONT_CARE
                        rules.pop(j)
                        changed = True
                        merged = True
                        continue  # re-check i against remaining rules

                j += 1
            i += 1

        if merges_this_round:
            steps.append(ReductionStep(
                f"Iteration {iteration}: {len(merges_this_round)} merge(s)",
                {"merges": merges_this_round},
            ))

    # Collapse multi-valued and re-add else rules
    rules = _collapse_multi_valued(rules, table.conditions)
    rules.extend(else_rules)

    steps.append(ReductionStep(
        "Reduction complete",
        {"original_count": len(table.rules), "reduced_count": len(rules)},
    ))

    return ReductionResult("Rule Merging", list(table.rules), rules, steps)


def espresso(table: DecisionTable) -> ReductionResult:
    """Reduce using the Espresso heuristic algorithm.

    Espresso is the industry-standard logic minimizer used in chip design
    (developed at UC Berkeley). It uses three iterative operations:

    1. EXPAND: Make each rule as general as possible (add don't-cares)
       without covering inputs assigned to different actions.
    2. IRREDUNDANT: Remove rules that are fully covered by others.
    3. REDUCE: Make each rule as specific as possible to create new
       opportunities for expansion in the next iteration.

    Repeat until stable. Not guaranteed optimal like Petrick, but much
    faster on large tables and produces near-optimal results.
    """
    steps: list[ReductionStep] = []

    if not table.rules or not table.conditions:
        return ReductionResult("Espresso", list(table.rules), list(table.rules), steps)

    normal_rules, else_rules = _split_else_rules(table.rules)
    if not normal_rules:
        return ReductionResult("Espresso", list(table.rules), list(else_rules), steps)

    import copy

    # Group by action profile
    action_groups: dict[tuple, list[Rule]] = {}
    for rule in normal_rules:
        profile = rule.action_profile()
        action_groups.setdefault(profile, []).append(copy.deepcopy(rule))

    valid_combos = table.valid_input_combinations()

    # Build a map: for each valid combo, which action profile it should have
    # (from the original table)
    combo_actions: dict[tuple, tuple] = {}
    for combo in valid_combos:
        for rule in normal_rules:
            if rule.covers(combo):
                combo_actions[tuple(sorted(combo.items()))] = rule.action_profile()
                break

    all_reduced: list[Rule] = []

    for profile, group_rules in action_groups.items():
        actions = dict(profile)

        # Get the set of combos this group must cover
        target_combos = {
            k for k, v in combo_actions.items() if v == profile
        }

        # Get the set of combos with OTHER action profiles (must NOT cover)
        off_combos = {
            k for k, v in combo_actions.items() if v != profile
        }

        rules = [copy.deepcopy(r) for r in group_rules]
        cond_names = [c.name for c in table.conditions]
        cond_values = {c.name: list(c.possible_values) for c in table.conditions}

        best_rules = list(rules)
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            prev_count = len(rules)

            # ── EXPAND: generalize each rule as much as possible ──
            for ri, rule in enumerate(rules):
                for cond_name in cond_names:
                    if rule.condition_entries.get(cond_name, DONT_CARE) == DONT_CARE:
                        continue

                    # Try setting to don't-care
                    old_val = rule.condition_entries[cond_name]
                    rule.condition_entries[cond_name] = DONT_CARE

                    # Check if this covers any off-set combo
                    covers_off = False
                    for oc in off_combos:
                        if rule.covers(dict(oc)):
                            covers_off = True
                            break

                    if covers_off:
                        rule.condition_entries[cond_name] = old_val  # revert
                    # else: keep the expansion

            steps.append(ReductionStep(
                f"Espresso iteration {iteration}: EXPAND",
                {"rules_after_expand": len(rules)},
            ))

            # ── IRREDUNDANT: remove rules covered by others ──
            irredundant = []
            for ri in range(len(rules)):
                # Check if all combos covered by rules[ri] are also covered
                # by the other rules
                others = rules[:ri] + rules[ri + 1:]
                needed = False
                for combo_key in target_combos:
                    combo = dict(combo_key)
                    if rules[ri].covers(combo):
                        if not any(r.covers(combo) for r in others):
                            needed = True
                            break
                if needed:
                    irredundant.append(rules[ri])
                elif not any(rules[ri].covers(dict(ck)) for ck in target_combos):
                    pass  # rule covers nothing in target, drop it
                else:
                    irredundant.append(rules[ri])  # keep redundant for safety

            # Check coverage - make sure we still cover everything
            uncovered = set()
            for ck in target_combos:
                combo = dict(ck)
                if not any(r.covers(combo) for r in irredundant):
                    uncovered.add(ck)

            if not uncovered:
                rules = irredundant
            # else keep all rules to avoid losing coverage

            # Actually remove truly redundant rules
            final_irredundant = []
            for ri in range(len(rules)):
                others = rules[:ri] + rules[ri + 1:] + final_irredundant
                # Remove only if NOT needed
                is_needed = False
                for ck in target_combos:
                    combo = dict(ck)
                    if rules[ri].covers(combo):
                        covered_by_others = any(
                            r.covers(combo) for r in (rules[:ri] + rules[ri + 1:])
                        )
                        if not covered_by_others:
                            is_needed = True
                            break
                if is_needed:
                    final_irredundant.append(rules[ri])
                else:
                    # Check if removing it leaves everything covered
                    remaining = final_irredundant + rules[ri + 1:]
                    all_covered = all(
                        any(r.covers(dict(ck)) for r in remaining)
                        for ck in target_combos
                    )
                    if all_covered:
                        pass  # safe to remove
                    else:
                        final_irredundant.append(rules[ri])

            rules = final_irredundant

            steps.append(ReductionStep(
                f"Espresso iteration {iteration}: IRREDUNDANT",
                {"rules_after_irredundant": len(rules)},
            ))

            # ── REDUCE: make rules more specific to create expand opportunities ──
            for rule in rules:
                for cond_name in cond_names:
                    if rule.condition_entries.get(cond_name, DONT_CARE) != DONT_CARE:
                        continue

                    # Try each specific value
                    others = [r for r in rules if r is not rule]
                    for val in cond_values[cond_name]:
                        rule.condition_entries[cond_name] = val
                        # Check all target combos are still covered
                        all_ok = all(
                            any(r.covers(dict(ck)) for r in rules)
                            for ck in target_combos
                        )
                        if all_ok:
                            break  # keep this reduction
                        rule.condition_entries[cond_name] = DONT_CARE

            steps.append(ReductionStep(
                f"Espresso iteration {iteration}: REDUCE",
                {"rules_after_reduce": len(rules)},
            ))

            # Check for convergence
            if len(rules) >= prev_count:
                # No improvement, but try one more expand pass
                if len(rules) <= len(best_rules):
                    best_rules = [copy.deepcopy(r) for r in rules]
                break
            else:
                best_rules = [copy.deepcopy(r) for r in rules]

        all_reduced.extend(best_rules)

    # Collapse multi-valued and re-add else rules
    all_reduced = _collapse_multi_valued(all_reduced, table.conditions)
    all_reduced.extend(else_rules)

    steps.append(ReductionStep(
        "Reduction complete",
        {"original_count": len(table.rules), "reduced_count": len(all_reduced)},
    ))

    return ReductionResult("Espresso", list(table.rules), all_reduced, steps)


def _project_rules_to_dont_care(
    rules: list[Rule], conditions_to_remove: list[str],
) -> list[Rule]:
    """Set removed conditions to DONT_CARE and deduplicate resulting rules."""
    projected: list[Rule] = []
    seen: set[tuple] = set()

    for rule in rules:
        new_rule = copy.deepcopy(rule)
        for cond_name in conditions_to_remove:
            new_rule.condition_entries[cond_name] = DONT_CARE

        cond_key = tuple(sorted(new_rule.condition_entries.items()))
        act_key = new_rule.action_profile()
        key = (cond_key, act_key)

        if key not in seen:
            seen.add(key)
            projected.append(new_rule)

    return projected


def _condition_significance(
    cond_name: str,
    valid_combos: list[dict[str, str]],
    combo_actions: dict[tuple, tuple],
) -> float:
    """Compute conditional entropy of the decision given a condition's value.

    Lower entropy means the condition is more significant (more informative).
    Returns the weighted average entropy across partitions.
    """
    # Partition combos by this condition's value
    partitions: dict[str, list[tuple]] = {}
    for combo in valid_combos:
        val = combo.get(cond_name, DONT_CARE)
        key = tuple(sorted(combo.items()))
        partitions.setdefault(val, []).append(key)

    total = len(valid_combos)
    if total == 0:
        return 0.0

    weighted_entropy = 0.0
    for val, keys in partitions.items():
        # Count action distribution within this partition
        action_counts: dict[tuple, int] = {}
        for key in keys:
            action = combo_actions.get(key)
            if action is not None:
                action_counts[action] = action_counts.get(action, 0) + 1

        partition_total = sum(action_counts.values())
        if partition_total == 0:
            continue

        entropy = 0.0
        for count in action_counts.values():
            p = count / partition_total
            if p > 0:
                entropy -= p * math.log2(p)

        weighted_entropy += (partition_total / total) * entropy

    return weighted_entropy


def positive_region_reduction(table: DecisionTable) -> ReductionResult:
    """Reduce by finding minimal attribute subset preserving the positive region.

    Uses Rough Set Theory (RST) to identify conditions that can be entirely
    removed without changing the table's decision-making. This is column
    reduction (removing conditions) as opposed to row reduction (merging rules).

    The positive region is the set of input combinations that are unambiguously
    classified. A condition is dispensable if removing it does not shrink the
    positive region.
    """
    steps: list[ReductionStep] = []

    if not table.rules or not table.conditions:
        return ReductionResult("Positive Region (RST)", list(table.rules), list(table.rules), steps)

    normal_rules, else_rules = _split_else_rules(table.rules)
    if not normal_rules:
        return ReductionResult("Positive Region (RST)", list(table.rules), list(else_rules), steps)

    # Get all valid input combinations and their actions from the original table
    valid_combos = table.valid_input_combinations()
    combo_actions: dict[tuple, tuple] = {}
    for combo in valid_combos:
        actions = table.effective_actions(combo)
        if actions is not None:
            combo_actions[tuple(sorted(combo.items()))] = tuple(sorted(actions.items()))

    all_cond_names = [c.name for c in table.conditions]

    # Find pairs of combos with different actions - these must remain distinguishable
    diff_pairs: list[tuple[dict[str, str], dict[str, str]]] = []
    combo_list = list(combo_actions.items())
    for i in range(len(combo_list)):
        for j in range(i + 1, len(combo_list)):
            if combo_list[i][1] != combo_list[j][1]:
                diff_pairs.append((dict(combo_list[i][0]), dict(combo_list[j][0])))

    steps.append(ReductionStep(
        "Identified distinguishing requirements",
        {"total_combos": len(combo_actions), "different_action_pairs": len(diff_pairs)},
    ))

    if not diff_pairs:
        # All combos have the same action - all conditions are dispensable
        removed = list(all_cond_names)
        reduced = _project_rules_to_dont_care(normal_rules, removed)
        reduced.extend(else_rules)
        steps.append(ReductionStep(
            "All conditions dispensable (uniform actions)",
            {"kept": [], "removed": removed},
        ))
        return ReductionResult("Positive Region (RST)", list(table.rules), reduced, steps)

    # For each condition, determine which diff_pairs it can distinguish
    cond_distinguishes: dict[str, set[int]] = {}
    for cond_name in all_cond_names:
        distinguished = set()
        for idx, (c1, c2) in enumerate(diff_pairs):
            if c1.get(cond_name) != c2.get(cond_name):
                distinguished.add(idx)
        cond_distinguishes[cond_name] = distinguished

    steps.append(ReductionStep(
        "Condition distinguishing power",
        {c: len(d) for c, d in cond_distinguishes.items()},
    ))

    # Greedy set cover: pick condition that distinguishes the most uncovered pairs
    remaining_pairs = set(range(len(diff_pairs)))
    selected_conds: list[str] = []
    available = list(all_cond_names)

    while remaining_pairs and available:
        best_cond = max(
            available,
            key=lambda c: len(cond_distinguishes[c] & remaining_pairs),
        )
        newly_covered = cond_distinguishes[best_cond] & remaining_pairs
        if not newly_covered:
            break  # remaining pairs can't be distinguished (inconsistent table)
        selected_conds.append(best_cond)
        available.remove(best_cond)
        remaining_pairs -= newly_covered

    # Try removing each selected condition to see if it's truly necessary (minimize)
    for cond in list(selected_conds):
        test_set = [c for c in selected_conds if c != cond]
        # Check if test_set still distinguishes all pairs
        covered = set()
        for c in test_set:
            covered |= cond_distinguishes[c]
        if covered >= set(range(len(diff_pairs))):
            selected_conds = test_set

    removed_conds = [c for c in all_cond_names if c not in selected_conds]

    steps.append(ReductionStep(
        "Selected minimal condition subset",
        {"kept": selected_conds, "removed": removed_conds},
    ))

    # Build reduced rules
    reduced_rules = _project_rules_to_dont_care(normal_rules, removed_conds)
    reduced_rules = _collapse_multi_valued(reduced_rules, table.conditions)
    reduced_rules.extend(else_rules)

    steps.append(ReductionStep(
        "Reduction complete",
        {
            "original_conditions": len(all_cond_names),
            "reduced_conditions": len(selected_conds),
            "original_rules": len(table.rules),
            "reduced_rules": len(reduced_rules),
        },
    ))

    return ReductionResult("Positive Region (RST)", list(table.rules), reduced_rules, steps)


def variable_precision_reduction(
    table: DecisionTable, threshold: float = 0.9,
) -> ReductionResult:
    """Reduce using Variable Precision Rough Set (VPRS) theory.

    Extends Positive Region Reduction by allowing a controlled degree of
    inconsistency. The *threshold* parameter (0.0-1.0) specifies the minimum
    classification accuracy that must be preserved.

    A threshold of 1.0 is equivalent to standard PRR. Lower thresholds allow
    more aggressive condition removal at the cost of some misclassification,
    which is useful for noisy data.
    """
    steps: list[ReductionStep] = []

    if not table.rules or not table.conditions:
        return ReductionResult("Variable Precision (RST)", list(table.rules), list(table.rules), steps)

    normal_rules, else_rules = _split_else_rules(table.rules)
    if not normal_rules:
        return ReductionResult("Variable Precision (RST)", list(table.rules), list(else_rules), steps)

    valid_combos = table.valid_input_combinations()
    combo_actions: dict[tuple, tuple] = {}
    for combo in valid_combos:
        actions = table.effective_actions(combo)
        if actions is not None:
            combo_actions[tuple(sorted(combo.items()))] = tuple(sorted(actions.items()))

    all_cond_names = [c.name for c in table.conditions]
    total_combos = len(combo_actions)

    steps.append(ReductionStep(
        "Variable precision parameters",
        {"threshold": threshold, "total_combos": total_combos},
    ))

    def _classification_accuracy(cond_subset: list[str]) -> float:
        """Compute fraction of combos correctly classified using only cond_subset."""
        # Group combos by their projected condition values (equivalence classes)
        equiv_classes: dict[tuple, list[tuple]] = {}
        for combo_key, action in combo_actions.items():
            combo = dict(combo_key)
            projected = tuple((c, combo.get(c, DONT_CARE)) for c in cond_subset)
            equiv_classes.setdefault(projected, []).append(action)

        correct = 0
        for actions_in_class in equiv_classes.values():
            # Majority vote: count the most common action
            action_counts: dict[tuple, int] = {}
            for a in actions_in_class:
                action_counts[a] = action_counts.get(a, 0) + 1
            correct += max(action_counts.values())

        return correct / total_combos if total_combos > 0 else 1.0

    # Start with all conditions, try removing each
    current_conds = list(all_cond_names)
    full_accuracy = _classification_accuracy(current_conds)

    steps.append(ReductionStep(
        "Full table classification accuracy",
        {"accuracy": full_accuracy},
    ))

    # Rank conditions by significance (conditional entropy)
    significance: dict[str, float] = {}
    for cond_name in all_cond_names:
        significance[cond_name] = _condition_significance(
            cond_name, valid_combos, combo_actions,
        )

    # Sort by entropy ascending = most significant first (lowest entropy = most useful)
    sorted_by_significance = sorted(all_cond_names, key=lambda c: significance[c])

    steps.append(ReductionStep(
        "Condition significance (conditional entropy, lower = more significant)",
        {c: round(significance[c], 4) for c in sorted_by_significance},
    ))

    # Try removing conditions starting from least significant
    removed_conds: list[str] = []
    for cond_name in reversed(sorted_by_significance):
        test_conds = [c for c in current_conds if c != cond_name]
        if not test_conds:
            break  # keep at least one condition
        accuracy = _classification_accuracy(test_conds)
        if accuracy >= threshold:
            current_conds = test_conds
            removed_conds.append(cond_name)
            steps.append(ReductionStep(
                f"Removed '{cond_name}' (accuracy {accuracy:.4f} >= {threshold})",
                {"remaining": list(current_conds), "accuracy": accuracy},
            ))
        else:
            steps.append(ReductionStep(
                f"Kept '{cond_name}' (accuracy {accuracy:.4f} < {threshold})",
                {"remaining": list(current_conds), "accuracy_without": accuracy},
            ))

    # Build reduced rules
    reduced_rules = _project_rules_to_dont_care(normal_rules, removed_conds)
    reduced_rules = _collapse_multi_valued(reduced_rules, table.conditions)
    reduced_rules.extend(else_rules)

    final_accuracy = _classification_accuracy(current_conds)

    steps.append(ReductionStep(
        "Reduction complete",
        {
            "original_conditions": len(all_cond_names),
            "reduced_conditions": len(current_conds),
            "kept": current_conds,
            "removed": removed_conds,
            "final_accuracy": final_accuracy,
            "original_rules": len(table.rules),
            "reduced_rules": len(reduced_rules),
        },
    ))

    return ReductionResult("Variable Precision (RST)", list(table.rules), reduced_rules, steps)


def clustering_reduction(table: DecisionTable) -> ReductionResult:
    """Reduce by clustering similar conditions and selecting representatives.

    Groups conditions based on how similarly they partition the input space
    (using a distance metric derived from agreement on input combos).
    Selects the most informative condition from each cluster using
    Partitioning Around Medoids (PAM).
    """
    steps: list[ReductionStep] = []

    if not table.rules or not table.conditions:
        return ReductionResult("Clustering", list(table.rules), list(table.rules), steps)

    normal_rules, else_rules = _split_else_rules(table.rules)
    if not normal_rules:
        return ReductionResult("Clustering", list(table.rules), list(else_rules), steps)

    valid_combos = table.valid_input_combinations()
    combo_actions: dict[tuple, tuple] = {}
    for combo in valid_combos:
        actions = table.effective_actions(combo)
        if actions is not None:
            combo_actions[tuple(sorted(combo.items()))] = tuple(sorted(actions.items()))

    all_cond_names = [c.name for c in table.conditions]

    if len(all_cond_names) <= 1:
        # Can't cluster a single condition
        reduced = list(normal_rules)
        reduced.extend(else_rules)
        return ReductionResult("Clustering", list(table.rules), reduced, steps)

    # Build condition partition vectors: for each condition, how it splits combos
    # Two combos are in the same partition cell if they have the same value for that condition
    partitions: dict[str, dict[str, set[int]]] = {}
    for cond_name in all_cond_names:
        part: dict[str, set[int]] = {}
        for idx, combo in enumerate(valid_combos):
            val = combo.get(cond_name, DONT_CARE)
            part.setdefault(val, set()).add(idx)
        partitions[cond_name] = part

    # Compute pairwise distance between conditions based on partition agreement
    # Distance = fraction of combo pairs where the two conditions disagree
    # on whether they're in the same partition cell
    n = len(valid_combos)
    distances: dict[tuple[str, str], float] = {}
    for i, c1 in enumerate(all_cond_names):
        for j, c2 in enumerate(all_cond_names):
            if i >= j:
                continue
            # Count agreements: pairs where both conditions agree (same cell or different cell)
            agreements = 0
            total_pairs = 0
            for p_idx in range(n):
                for q_idx in range(p_idx + 1, n):
                    total_pairs += 1
                    # Are p,q in same cell for c1?
                    same_c1 = any(
                        p_idx in cell and q_idx in cell
                        for cell in partitions[c1].values()
                    )
                    same_c2 = any(
                        p_idx in cell and q_idx in cell
                        for cell in partitions[c2].values()
                    )
                    if same_c1 == same_c2:
                        agreements += 1
            dist = 1.0 - (agreements / total_pairs) if total_pairs > 0 else 0.0
            distances[(c1, c2)] = dist
            distances[(c2, c1)] = dist

    steps.append(ReductionStep(
        "Condition pairwise distances",
        {f"{c1}-{c2}": round(d, 4) for (c1, c2), d in distances.items() if c1 < c2},
    ))

    # Determine number of clusters using condition significance
    # Keep enough clusters to preserve decision-making
    significance: dict[str, float] = {}
    for cond_name in all_cond_names:
        significance[cond_name] = _condition_significance(
            cond_name, valid_combos, combo_actions,
        )

    # Count how many conditions have non-zero distinguishing power
    # (conditions with 0 entropy are perfectly correlated with the decision)
    useful_conds = [c for c in all_cond_names if significance[c] < math.log2(max(len(combo_actions), 2))]
    # Use at least 1 cluster, at most all conditions
    k = max(1, min(len(useful_conds), len(all_cond_names) - 1))

    # If k >= number of conditions, no clustering benefit
    if k >= len(all_cond_names):
        reduced = list(normal_rules)
        reduced.extend(else_rules)
        steps.append(ReductionStep(
            "No clustering benefit (all conditions needed)",
            {"k": k, "conditions": len(all_cond_names)},
        ))
        return ReductionResult("Clustering", list(table.rules), reduced, steps)

    steps.append(ReductionStep(
        "Cluster count determined",
        {"k": k, "total_conditions": len(all_cond_names)},
    ))

    # PAM (Partitioning Around Medoids) clustering
    # Initialize medoids: pick k conditions with lowest significance (most informative)
    sorted_by_sig = sorted(all_cond_names, key=lambda c: significance[c])
    medoids = sorted_by_sig[:k]

    max_pam_iterations = 20
    for pam_iter in range(max_pam_iterations):
        # Assign each condition to nearest medoid
        clusters: dict[str, list[str]] = {m: [] for m in medoids}
        for cond in all_cond_names:
            if cond in medoids:
                clusters[cond].append(cond)
            else:
                nearest = min(medoids, key=lambda m: distances.get((cond, m), 0.0))
                clusters[nearest].append(cond)

        # Try swapping each medoid with each non-medoid
        improved = False
        best_cost = sum(
            min(distances.get((c, m), 0.0) for m in medoids)
            for c in all_cond_names if c not in medoids
        )

        for mi, medoid in enumerate(list(medoids)):
            for cond in all_cond_names:
                if cond in medoids:
                    continue
                # Swap
                new_medoids = list(medoids)
                new_medoids[mi] = cond
                new_cost = sum(
                    min(distances.get((c, m), 0.0) for m in new_medoids)
                    for c in all_cond_names if c not in new_medoids
                )
                if new_cost < best_cost:
                    best_cost = new_cost
                    medoids = new_medoids
                    improved = True
                    break
            if improved:
                break

        if not improved:
            break

    # Final cluster assignment
    clusters = {m: [] for m in medoids}
    for cond in all_cond_names:
        if cond in medoids:
            clusters[cond].append(cond)
        else:
            nearest = min(medoids, key=lambda m: distances.get((cond, m), 0.0))
            clusters[nearest].append(cond)

    steps.append(ReductionStep(
        "Clusters formed (medoid = representative)",
        {medoid: members for medoid, members in clusters.items()},
    ))

    # Verify the selected medoids preserve the decision logic
    # If not, add back conditions greedily until logic is preserved
    diff_pairs: list[tuple[dict[str, str], dict[str, str]]] = []
    combo_list = list(combo_actions.items())
    for i in range(len(combo_list)):
        for j in range(i + 1, len(combo_list)):
            if combo_list[i][1] != combo_list[j][1]:
                diff_pairs.append((dict(combo_list[i][0]), dict(combo_list[j][0])))

    selected_conds = list(medoids)
    if diff_pairs:
        # Check if medoids distinguish all diff pairs
        undistinguished = set()
        for idx, (c1, c2) in enumerate(diff_pairs):
            if not any(c1.get(c) != c2.get(c) for c in selected_conds):
                undistinguished.add(idx)

        # Add back conditions to cover undistinguished pairs
        remaining = [c for c in all_cond_names if c not in selected_conds]
        while undistinguished and remaining:
            best = max(remaining, key=lambda c: sum(
                1 for idx in undistinguished
                if diff_pairs[idx][0].get(c) != diff_pairs[idx][1].get(c)
            ))
            newly_covered = {
                idx for idx in undistinguished
                if diff_pairs[idx][0].get(best) != diff_pairs[idx][1].get(best)
            }
            if not newly_covered:
                break
            selected_conds.append(best)
            remaining.remove(best)
            undistinguished -= newly_covered

    removed_conds = [c for c in all_cond_names if c not in selected_conds]

    if removed_conds != [c for c in all_cond_names if c not in medoids]:
        steps.append(ReductionStep(
            "Added conditions back to preserve logic",
            {"final_kept": selected_conds, "removed": removed_conds},
        ))

    # Build reduced rules
    reduced_rules = _project_rules_to_dont_care(normal_rules, removed_conds)
    reduced_rules = _collapse_multi_valued(reduced_rules, table.conditions)
    reduced_rules.extend(else_rules)

    steps.append(ReductionStep(
        "Reduction complete",
        {
            "original_conditions": len(all_cond_names),
            "reduced_conditions": len(selected_conds),
            "original_rules": len(table.rules),
            "reduced_rules": len(reduced_rules),
        },
    ))

    return ReductionResult("Clustering", list(table.rules), reduced_rules, steps)


def incremental_reduction(
    table: DecisionTable,
    previous_result: ReductionResult | None = None,
    method: str = "qm",
) -> ReductionResult:
    """Incrementally update a previous reduction when the table changes.

    Instead of recomputing the full reduction from scratch, this method:
    1. Identifies which rules changed (added, removed, or modified)
    2. Determines if affected rules can be locally re-reduced
    3. Falls back to full reduction only when necessary

    This is significantly faster for interactive editing where changes are
    small relative to the total table size.

    Args:
        table: The current (modified) decision table.
        previous_result: The result of a prior reduction on a similar table.
            If None, performs a full reduction.
        method: Which base reduction algorithm to use ('qm', 'petrick',
            'merge', 'espresso'). Defaults to 'qm'.
    """
    methods = {
        "qm": quine_mccluskey,
        "petrick": petricks_method,
        "merge": rule_merging,
        "espresso": espresso,
    }
    reduce_fn = methods.get(method, quine_mccluskey)
    method_name = f"Incremental ({method.upper()})"
    steps: list[ReductionStep] = []

    if not table.rules or not table.conditions:
        return ReductionResult(method_name, list(table.rules), list(table.rules), steps)

    # No previous result — full reduction
    if previous_result is None:
        steps.append(ReductionStep(
            "No previous result — full reduction",
            {"method": method},
        ))
        full_result = reduce_fn(table)
        return ReductionResult(
            method_name,
            full_result.original_rules,
            full_result.reduced_rules,
            steps + full_result.steps,
        )

    # Identify what changed between previous original rules and current rules
    prev_rules = previous_result.original_rules
    prev_reduced = previous_result.reduced_rules
    curr_rules = table.rules

    # Build fingerprints for comparison
    def _rule_fingerprint(rule: Rule) -> tuple:
        return (
            tuple(sorted(rule.condition_entries.items())),
            rule.action_profile(),
            rule.is_else,
        )

    prev_fps = {_rule_fingerprint(r) for r in prev_rules}
    curr_fps = {_rule_fingerprint(r) for r in curr_rules}

    added_fps = curr_fps - prev_fps
    removed_fps = prev_fps - curr_fps

    steps.append(ReductionStep(
        "Change detection",
        {
            "rules_added": len(added_fps),
            "rules_removed": len(removed_fps),
            "rules_unchanged": len(prev_fps & curr_fps),
        },
    ))

    # If nothing changed, return previous result
    if not added_fps and not removed_fps:
        steps.append(ReductionStep("No changes detected — reusing previous result", {}))
        return ReductionResult(method_name, list(curr_rules), list(prev_reduced), steps)

    # Identify affected action profiles
    affected_profiles: set[tuple] = set()
    for fp in added_fps | removed_fps:
        affected_profiles.add(fp[1])  # action_profile

    steps.append(ReductionStep(
        "Affected action profiles",
        {"profiles": [str(p) for p in affected_profiles]},
    ))

    # For unaffected action profiles, reuse previous reduced rules
    reused_rules: list[Rule] = []
    needs_reduction_rules: list[Rule] = []

    for rule in prev_reduced:
        if rule.action_profile() not in affected_profiles and not rule.is_else:
            reused_rules.append(copy.deepcopy(rule))

    steps.append(ReductionStep(
        "Reused rules from previous reduction",
        {"reused_count": len(reused_rules)},
    ))

    # Build a partial table with only the affected rules for re-reduction
    affected_rules = [
        r for r in curr_rules
        if r.action_profile() in affected_profiles or r.is_else
    ]

    if affected_rules:
        partial_table = DecisionTable(
            name=table.name,
            conditions=list(table.conditions),
            actions=list(table.actions),
            rules=affected_rules,
            constraints=list(table.constraints),
            table_type=table.table_type,
        )
        partial_result = reduce_fn(partial_table)
        needs_reduction_rules = list(partial_result.reduced_rules)

        steps.append(ReductionStep(
            "Partial re-reduction on affected rules",
            {
                "affected_rules": len(affected_rules),
                "reduced_to": len(needs_reduction_rules),
            },
        ))
        steps.extend(partial_result.steps)

    # Combine reused + newly reduced
    all_reduced = reused_rules + needs_reduction_rules

    # Verify equivalence — if not equivalent, fall back to full reduction
    reduced_table = DecisionTable(
        name=table.name,
        conditions=list(table.conditions),
        actions=list(table.actions),
        rules=all_reduced,
        constraints=list(table.constraints),
        table_type=table.table_type,
    )
    is_equiv, diffs = table.is_equivalent_to(reduced_table)

    if not is_equiv:
        steps.append(ReductionStep(
            "Incremental result not equivalent — falling back to full reduction",
            {"differences": len(diffs)},
        ))
        full_result = reduce_fn(table)
        return ReductionResult(
            method_name,
            list(curr_rules),
            full_result.reduced_rules,
            steps + full_result.steps,
        )

    steps.append(ReductionStep(
        "Reduction complete (incremental)",
        {
            "original_rules": len(curr_rules),
            "reduced_rules": len(all_reduced),
            "reused_from_previous": len(reused_rules),
            "newly_reduced": len(needs_reduction_rules),
        },
    ))

    return ReductionResult(method_name, list(curr_rules), all_reduced, steps)


@dataclass
class ComparisonResult:
    qm_result: ReductionResult
    petrick_result: ReductionResult
    rule_merging_result: ReductionResult | None = None
    espresso_result: ReductionResult | None = None
    prr_result: ReductionResult | None = None
    vpr_result: ReductionResult | None = None
    clustering_result: ReductionResult | None = None


def compare_reductions(table: DecisionTable) -> ComparisonResult:
    """Run all reduction methods and return results for comparison."""
    return ComparisonResult(
        qm_result=quine_mccluskey(table),
        petrick_result=petricks_method(table),
        rule_merging_result=rule_merging(table),
        espresso_result=espresso(table),
        prr_result=positive_region_reduction(table),
        vpr_result=variable_precision_reduction(table),
        clustering_result=clustering_reduction(table),
    )
