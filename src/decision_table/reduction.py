"""Logic reduction using Quine-McCluskey algorithm and Petrick's Method."""

from __future__ import annotations

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


@dataclass
class ComparisonResult:
    qm_result: ReductionResult
    petrick_result: ReductionResult
    rule_merging_result: ReductionResult | None = None
    espresso_result: ReductionResult | None = None


def compare_reductions(table: DecisionTable) -> ComparisonResult:
    """Run all reduction methods and return results for comparison."""
    return ComparisonResult(
        qm_result=quine_mccluskey(table),
        petrick_result=petricks_method(table),
        rule_merging_result=rule_merging(table),
        espresso_result=espresso(table),
    )
