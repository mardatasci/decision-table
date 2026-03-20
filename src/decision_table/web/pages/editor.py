"""Editor page -- main decision table grid with validation, reduction, testing, constraints."""

import dash
import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, callback, ctx, html, dcc

from decision_table.model import (
    DONT_CARE,
    Action,
    Condition,
    ConditionType,
    Constraint,
    ConstraintType,
    DecisionTable,
    Rule,
    make_boolean_condition,
    make_enum_condition,
    make_numeric_condition,
)
from decision_table.validation import (
    Severity,
    check_completeness,
    check_consistency,
    check_constraints,
    check_contradiction,
    check_redundancy,
    validate_all,
)
from decision_table.reduction import (
    clustering_reduction,
    compare_reductions,
    espresso,
    incremental_reduction,
    petricks_method,
    positive_region_reduction,
    quine_mccluskey,
    rule_merging,
    variable_precision_reduction,
)
from decision_table.testing import (
    calculate_coverage,
    generate_all_tests,
    generate_boundary_tests,
    generate_pairwise_tests,
    generate_test_cases,
)
from decision_table.web.components import build_decision_grid, build_status_bar
from decision_table.web.state import apply_mutation, store_to_table

dash.register_page(__name__, path="/", name="Editor")

_CHECK_FUNCTIONS = {
    "completeness": ("Completeness", check_completeness),
    "redundancy": ("Redundancy", check_redundancy),
    "contradiction": ("Contradiction", check_contradiction),
    "consistency": ("Consistency", check_consistency),
    "constraints": ("Constraints", check_constraints),
}

_REDUCTION_METHODS = {
    "quine_mccluskey": ("Quine-McCluskey", quine_mccluskey),
    "petricks": ("Petrick's Method", petricks_method),
    "rule_merging": ("Rule Merging", rule_merging),
    "espresso": ("Espresso", espresso),
    "prr": ("Positive Region (RST)", positive_region_reduction),
    "vpr": ("Variable Precision (RST)", variable_precision_reduction),
    "clustering": ("Clustering", clustering_reduction),
    "incremental": ("Incremental", incremental_reduction),
}

# ═══════════════════════════════════════════════════════════════════
# Layout
# ═══════════════════════════════════════════════════════════════════

# -- Validation tab content --
_validation_tab = html.Div(
    [
        dbc.Row(
            [
                dbc.Col(
                    dbc.Button("Run All Checks", id="validate-all-btn", color="primary", size="sm", className="me-2"),
                    width="auto",
                ),
                dbc.Col(
                    dbc.Select(
                        id="validate-single-select",
                        options=[{"label": name, "value": key} for key, (name, _) in _CHECK_FUNCTIONS.items()],
                        placeholder="Run single check...",
                        size="sm",
                        style={"width": "200px"},
                    ),
                    width="auto",
                ),
                dbc.Col(
                    dbc.Button("Run", id="validate-single-btn", color="secondary", size="sm"),
                    width="auto",
                ),
            ],
            className="g-2 mb-3 align-items-center",
        ),
        html.Div(id="validation-summary", className="mb-2"),
        html.Div(id="validation-results"),
    ],
    className="p-3",
)

# -- Reduction tab content --
_reduction_tab = html.Div(
    [
        dbc.Row(
            [
                dbc.Col(
                    dbc.Select(
                        id="reduction-method",
                        options=[{"label": name, "value": key} for key, (name, _) in _REDUCTION_METHODS.items()],
                        value="quine_mccluskey",
                        size="sm",
                        style={"width": "220px"},
                    ),
                    width="auto",
                ),
                dbc.Col(dbc.Button("Reduce", id="reduce-btn", color="primary", size="sm"), width="auto"),
                dbc.Col(dbc.Button("Compare All", id="compare-btn", color="info", size="sm"), width="auto"),
                dbc.Col(
                    dbc.Button("Apply Reduced", id="apply-reduce-btn", color="success", size="sm", disabled=True),
                    width="auto",
                ),
            ],
            className="g-2 mb-3 align-items-center",
        ),
        dcc.Store(id="reduction-result-store"),
        html.Div(id="reduction-results"),
    ],
    className="p-3",
)

# -- Testing tab content --
_testing_tab = html.Div(
    [
        dbc.Row(
            [
                dbc.Col(
                    dbc.Select(
                        id="test-type",
                        options=[
                            {"label": "All Tests", "value": "all"},
                            {"label": "Per-Rule Coverage", "value": "per_rule"},
                            {"label": "Boundary Value", "value": "boundary"},
                            {"label": "Pairwise (All-Pairs)", "value": "pairwise"},
                        ],
                        value="all",
                        size="sm",
                        style={"width": "220px"},
                    ),
                    width="auto",
                ),
                dbc.Col(dbc.Button("Generate", id="generate-tests-btn", color="primary", size="sm"), width="auto"),
                dbc.Col(
                    dbc.Button("Export CSV", id="export-csv-btn", color="secondary", size="sm", disabled=True),
                    width="auto",
                ),
            ],
            className="g-2 mb-3 align-items-center",
        ),
        dcc.Store(id="test-cases-store"),
        dcc.Download(id="test-download"),
        html.Div(id="test-coverage", className="mb-3"),
        html.Div(id="test-results"),
    ],
    className="p-3",
)

# -- Constraints tab content --
_constraints_tab = html.Div(
    [
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Add Constraint"),
                            dbc.CardBody(
                                [
                                    dbc.Select(
                                        id="constraint-type",
                                        options=[
                                            {"label": "Impossible", "value": "impossible"},
                                            {"label": "Exclusion", "value": "exclusion"},
                                            {"label": "Implication", "value": "implication"},
                                        ],
                                        value="impossible",
                                        size="sm",
                                        className="mb-2",
                                    ),
                                    html.Div(id="constraint-form", className="mb-2"),
                                    dbc.Input(
                                        id="constraint-desc",
                                        placeholder="Description (optional)",
                                        size="sm",
                                        className="mb-2",
                                    ),
                                    dbc.Button(
                                        "Add Constraint", id="add-constraint-btn",
                                        color="primary", size="sm", className="w-100",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    width=5,
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Current Constraints"),
                            dbc.CardBody(html.Div(id="constraint-list")),
                        ],
                    ),
                    width=7,
                ),
            ],
            className="g-3",
        ),
        dbc.Alert(id="constraint-alert", is_open=False, duration=4000, className="mt-3"),
    ],
    className="p-3",
)


layout = html.Div(
    [
        html.H2("Decision Table Editor", className="mb-3"),
        # Status bar
        html.Div(id="editor-status-bar"),
        # Add controls
        dbc.Row(
            [
                # Add Condition
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Add Condition"),
                            dbc.CardBody(
                                [
                                    dbc.Input(id="cond-name", placeholder="Condition name", size="sm", className="mb-2"),
                                    dbc.Input(id="cond-values", placeholder="Values (comma-separated)", value="T, F", size="sm", className="mb-2"),
                                    dbc.Select(
                                        id="cond-type",
                                        options=[
                                            {"label": "Boolean", "value": "boolean"},
                                            {"label": "Enum", "value": "enum"},
                                            {"label": "Numeric", "value": "numeric"},
                                        ],
                                        value="boolean",
                                        size="sm",
                                        className="mb-2",
                                    ),
                                    dbc.Button("Add Condition", id="add-condition-btn", color="primary", size="sm", className="w-100"),
                                ],
                            ),
                        ],
                    ),
                    width=3,
                ),
                # Add Action
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Add Action"),
                            dbc.CardBody(
                                [
                                    dbc.Input(id="action-name", placeholder="Action name", size="sm", className="mb-2"),
                                    dbc.Input(id="action-values", placeholder="Values (comma-separated)", value="X, ", size="sm", className="mb-2"),
                                    dbc.Button("Add Action", id="add-action-btn", color="success", size="sm", className="w-100"),
                                ],
                            ),
                        ],
                    ),
                    width=3,
                ),
                # Add Rule
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Add Rule"),
                            dbc.CardBody(
                                [
                                    dbc.Button("+ Rule", id="add-rule-btn", color="info", size="sm", className="w-100 mb-2"),
                                    dbc.Button("+ Else Rule", id="add-else-btn", color="warning", size="sm", className="w-100 mb-2"),
                                    dbc.Button("Copy Last Rule", id="copy-rule-btn", color="secondary", size="sm", className="w-100"),
                                ],
                            ),
                        ],
                    ),
                    width=3,
                ),
                # Remove
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Remove"),
                            dbc.CardBody(
                                [
                                    dbc.Select(id="remove-target", options=[], size="sm", className="mb-2", placeholder="Select item..."),
                                    dbc.Button("Remove Selected", id="remove-btn", color="danger", size="sm", className="w-100"),
                                ],
                            ),
                        ],
                    ),
                    width=3,
                ),
            ],
            className="g-3 mb-3",
        ),
        # Decision table grid
        html.Div(id="editor-grid"),
        # Editor messages
        dbc.Alert(id="editor-alert", is_open=False, duration=4000, className="mt-3"),
        # ── Analysis tabs below the grid ──
        html.Hr(className="mt-4"),
        dbc.Tabs(
            [
                dbc.Tab(_validation_tab, label="Validation", tab_id="tab-validation"),
                dbc.Tab(_reduction_tab, label="Reduction", tab_id="tab-reduction"),
                dbc.Tab(_testing_tab, label="Testing", tab_id="tab-testing"),
                dbc.Tab(_constraints_tab, label="Constraints", tab_id="tab-constraints"),
            ],
            id="analysis-tabs",
            active_tab="tab-validation",
            className="mt-2",
        ),
    ],
)


# ═══════════════════════════════════════════════════════════════════
# Editor callbacks
# ═══════════════════════════════════════════════════════════════════

@callback(
    Output("remove-target", "options"),
    Input("table-store", "data"),
)
def update_remove_options(store_data):
    table = store_to_table(store_data)
    options = []
    for c in table.conditions:
        options.append({"label": f"Condition: {c.name}", "value": f"c:{c.name}"})
    for a in table.actions:
        options.append({"label": f"Action: {a.name}", "value": f"a:{a.name}"})
    for i, r in enumerate(table.rules):
        label = f"Rule R{i+1}"
        if r.is_else:
            label += " (ELSE)"
        options.append({"label": label, "value": f"r:{i}"})
    return options


@callback(
    Output("editor-grid", "children"),
    Output("editor-status-bar", "children"),
    Input("table-store", "data"),
)
def render_grid(store_data):
    table = store_to_table(store_data)
    return build_decision_grid(table), build_status_bar(table)


@callback(
    Output("table-store", "data", allow_duplicate=True),
    Output("editor-alert", "children", allow_duplicate=True),
    Output("editor-alert", "is_open", allow_duplicate=True),
    Output("editor-alert", "color", allow_duplicate=True),
    Input("add-condition-btn", "n_clicks"),
    State("cond-name", "value"),
    State("cond-values", "value"),
    State("cond-type", "value"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def add_condition(_, name, values, ctype, store_data):
    if not name or not name.strip():
        return dash.no_update, "Condition name is required", True, "warning"
    name = name.strip()
    vals = [v.strip() for v in (values or "T, F").split(",") if v.strip()]
    try:
        if ctype == "numeric":
            cond = make_numeric_condition(name, vals)
        elif ctype == "enum":
            cond = make_enum_condition(name, vals)
        else:
            cond = make_boolean_condition(name)
        new_store = apply_mutation(store_data, lambda t: t.add_condition(cond))
        return new_store, f"Added condition '{name}'", True, "success"
    except Exception as e:
        return dash.no_update, str(e), True, "danger"


@callback(
    Output("table-store", "data", allow_duplicate=True),
    Output("editor-alert", "children", allow_duplicate=True),
    Output("editor-alert", "is_open", allow_duplicate=True),
    Output("editor-alert", "color", allow_duplicate=True),
    Input("add-action-btn", "n_clicks"),
    State("action-name", "value"),
    State("action-values", "value"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def add_action(_, name, values, store_data):
    if not name or not name.strip():
        return dash.no_update, "Action name is required", True, "warning"
    name = name.strip()
    vals = [v.strip() for v in (values or "X, ").split(",")]
    try:
        action = Action(name=name, possible_values=vals)
        new_store = apply_mutation(store_data, lambda t: t.add_action(action))
        return new_store, f"Added action '{name}'", True, "success"
    except Exception as e:
        return dash.no_update, str(e), True, "danger"


@callback(
    Output("table-store", "data", allow_duplicate=True),
    Output("editor-alert", "children", allow_duplicate=True),
    Output("editor-alert", "is_open", allow_duplicate=True),
    Output("editor-alert", "color", allow_duplicate=True),
    Input("add-rule-btn", "n_clicks"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def add_rule(_, store_data):
    new_store = apply_mutation(store_data, lambda t: t.add_rule(Rule()))
    return new_store, "Added new rule", True, "success"


@callback(
    Output("table-store", "data", allow_duplicate=True),
    Output("editor-alert", "children", allow_duplicate=True),
    Output("editor-alert", "is_open", allow_duplicate=True),
    Output("editor-alert", "color", allow_duplicate=True),
    Input("add-else-btn", "n_clicks"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def add_else_rule(_, store_data):
    new_store = apply_mutation(store_data, lambda t: t.add_else_rule())
    return new_store, "Added else rule", True, "success"


@callback(
    Output("table-store", "data", allow_duplicate=True),
    Output("editor-alert", "children", allow_duplicate=True),
    Output("editor-alert", "is_open", allow_duplicate=True),
    Output("editor-alert", "color", allow_duplicate=True),
    Input("copy-rule-btn", "n_clicks"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def copy_last_rule(_, store_data):
    table = store_to_table(store_data)
    if not table.rules:
        return dash.no_update, "No rules to copy", True, "warning"
    idx = len(table.rules) - 1
    new_store = apply_mutation(store_data, lambda t: t.duplicate_rule(idx))
    return new_store, f"Copied rule R{idx + 1}", True, "success"


@callback(
    Output("table-store", "data", allow_duplicate=True),
    Output("editor-alert", "children", allow_duplicate=True),
    Output("editor-alert", "is_open", allow_duplicate=True),
    Output("editor-alert", "color", allow_duplicate=True),
    Input("remove-btn", "n_clicks"),
    State("remove-target", "value"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def remove_item(_, target, store_data):
    if not target:
        return dash.no_update, "Select an item to remove", True, "warning"
    try:
        kind, val = target.split(":", 1)
        if kind == "c":
            new_store = apply_mutation(store_data, lambda t: t.remove_condition(val))
            msg = f"Removed condition '{val}'"
        elif kind == "a":
            new_store = apply_mutation(store_data, lambda t: t.remove_action(val))
            msg = f"Removed action '{val}'"
        elif kind == "r":
            idx = int(val)
            new_store = apply_mutation(store_data, lambda t: t.remove_rule(idx))
            msg = f"Removed rule R{idx + 1}"
        else:
            return dash.no_update, "Unknown item type", True, "danger"
        return new_store, msg, True, "success"
    except Exception as e:
        return dash.no_update, str(e), True, "danger"


@callback(
    Output("table-store", "data", allow_duplicate=True),
    Input({"type": "grid-cell", "kind": ALL, "row": ALL, "col": ALL}, "n_clicks"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def cycle_cell(n_clicks_list, store_data):
    if not ctx.triggered_id:
        return dash.no_update

    # When the grid is re-rendered (e.g. on browser refresh), Dash re-registers
    # all pattern-matching components and may fire this callback even though no
    # real click occurred.  Guard against that by checking n_clicks > 0.
    triggered = ctx.triggered
    if triggered and triggered[0]["value"] == 0:
        return dash.no_update

    cell_id = ctx.triggered_id
    kind = cell_id["kind"]
    row = cell_id["row"]
    col = cell_id["col"]

    table = store_to_table(store_data)
    if col >= len(table.rules):
        return dash.no_update

    rule = table.rules[col]

    if kind == "condition":
        if row >= len(table.conditions):
            return dash.no_update
        cond = table.conditions[row]
        current = rule.condition_entries.get(cond.name, DONT_CARE)
        cycle_vals = cond.possible_values + [DONT_CARE]
        try:
            idx = cycle_vals.index(current)
        except ValueError:
            idx = -1
        next_val = cycle_vals[(idx + 1) % len(cycle_vals)]

        def mutate(t):
            t.rules[col].condition_entries[cond.name] = next_val
        return apply_mutation(store_data, mutate)

    elif kind == "action":
        if row >= len(table.actions):
            return dash.no_update
        action = table.actions[row]
        current = rule.action_entries.get(action.name, "")
        cycle_vals = action.possible_values
        if not cycle_vals:
            return dash.no_update
        try:
            idx = cycle_vals.index(current)
        except ValueError:
            idx = -1
        next_val = cycle_vals[(idx + 1) % len(cycle_vals)]

        def mutate(t):
            t.rules[col].action_entries[action.name] = next_val
        return apply_mutation(store_data, mutate)

    return dash.no_update


# ═══════════════════════════════════════════════════════════════════
# Validation callbacks
# ═══════════════════════════════════════════════════════════════════

def _render_val_results(result):
    if not result.messages:
        return dbc.Alert("All checks passed!", color="success")
    severity_css = {
        Severity.ERROR: "val-msg-error",
        Severity.WARNING: "val-msg-warning",
        Severity.INFO: "val-msg-info",
    }
    severity_icons = {Severity.ERROR: "ERROR", Severity.WARNING: "WARN", Severity.INFO: "INFO"}
    items = []
    for msg in result.messages:
        css = severity_css.get(msg.severity, "val-msg-info")
        icon = severity_icons.get(msg.severity, "INFO")
        check_name = msg.check.upper() if msg.check else ""
        text = f"[{icon}] [{check_name}] {msg.message}"
        if msg.rule_indices:
            text += f" (rules: {', '.join(f'R{i+1}' for i in msg.rule_indices)})"
        items.append(html.Div(text, className=css))
    return html.Div(items)


def _render_val_summary(result):
    errors = sum(1 for m in result.messages if m.severity == Severity.ERROR)
    warnings = sum(1 for m in result.messages if m.severity == Severity.WARNING)
    infos = sum(1 for m in result.messages if m.severity == Severity.INFO)
    badges = []
    if errors:
        badges.append(dbc.Badge(f"{errors} errors", color="danger", className="me-2"))
    if warnings:
        badges.append(dbc.Badge(f"{warnings} warnings", color="warning", className="me-2"))
    if infos:
        badges.append(dbc.Badge(f"{infos} info", color="info", className="me-2"))
    if not result.messages:
        badges.append(dbc.Badge("PASS", color="success"))
    return html.Div(badges)


@callback(
    Output("validation-results", "children"),
    Output("validation-summary", "children"),
    Input("validate-all-btn", "n_clicks"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def run_all_checks(_, store_data):
    table = store_to_table(store_data)
    if not table.conditions and not table.actions:
        return dbc.Alert("Add conditions and actions first.", color="warning"), ""
    result = validate_all(table)
    return _render_val_results(result), _render_val_summary(result)


@callback(
    Output("validation-results", "children", allow_duplicate=True),
    Output("validation-summary", "children", allow_duplicate=True),
    Input("validate-single-btn", "n_clicks"),
    State("validate-single-select", "value"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def run_single_check(_, check_key, store_data):
    if not check_key or check_key not in _CHECK_FUNCTIONS:
        return dbc.Alert("Select a check to run.", color="warning"), ""
    table = store_to_table(store_data)
    if not table.conditions and not table.actions:
        return dbc.Alert("Add conditions and actions first.", color="warning"), ""
    name, fn = _CHECK_FUNCTIONS[check_key]
    result = fn(table)
    return _render_val_results(result), _render_val_summary(result)


# ═══════════════════════════════════════════════════════════════════
# Reduction callbacks
# ═══════════════════════════════════════════════════════════════════

@callback(
    Output("reduction-results", "children"),
    Output("reduction-result-store", "data"),
    Output("apply-reduce-btn", "disabled"),
    Input("reduce-btn", "n_clicks"),
    State("reduction-method", "value"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def run_reduction(_, method_key, store_data):
    table = store_to_table(store_data)
    if not table.rules:
        return dbc.Alert("No rules to reduce.", color="warning"), None, True
    method_name, fn = _REDUCTION_METHODS[method_key]
    try:
        result = fn(table)
        children = []
        orig = len(result.original_rules)
        reduced = len(result.reduced_rules)
        pct = result.reduction_percentage
        children.append(
            dbc.Alert(
                f"{method_name}: {orig} rules -> {reduced} rules ({pct:.0f}% reduction)",
                color="success" if reduced < orig else "info",
            )
        )
        # Build a reduced table for display
        import copy
        reduced_table = copy.deepcopy(table)
        reduced_table.rules = list(result.reduced_rules)
        children.append(html.H5("Reduced Table", className="mb-2"))
        children.append(build_decision_grid(reduced_table))

        if result.steps:
            step_items = [
                html.Div(
                    [
                        html.Strong(step.description),
                        html.Div(
                            str(step.details) if step.details else "",
                            className="text-muted small",
                        ) if step.details else None,
                    ],
                    className="reduction-step",
                )
                for step in result.steps
            ]
            children.append(
                dbc.Accordion(
                    [dbc.AccordionItem(html.Div(step_items), title=f"Steps ({len(result.steps)})")],
                    start_collapsed=True,
                    className="mt-3",
                )
            )
        # Check equivalence
        is_eq, _ = table.is_equivalent_to(reduced_table)
        eq_text = "Equivalent to original" if is_eq else "NOT equivalent!"
        children.append(dbc.Badge(eq_text, color="success" if is_eq else "danger", className="mt-2"))

        reduced_data = reduced_table.to_dict()
        return html.Div(children), reduced_data, False
    except Exception as e:
        return dbc.Alert(f"Reduction error: {e}", color="danger"), None, True


@callback(
    Output("reduction-results", "children", allow_duplicate=True),
    Input("compare-btn", "n_clicks"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def run_compare(_, store_data):
    table = store_to_table(store_data)
    if not table.rules:
        return dbc.Alert("No rules to compare.", color="warning")
    try:
        import copy
        comparison = compare_reductions(table)
        header = html.Thead(html.Tr([html.Th("Method"), html.Th("Original"), html.Th("Reduced"), html.Th("%"), html.Th("Equivalent")]))
        rows = []
        for r in [comparison.qm_result, comparison.petrick_result, comparison.rule_merging_result, comparison.espresso_result, comparison.prr_result, comparison.vpr_result, comparison.clustering_result]:
            if r is None:
                continue
            orig = len(r.original_rules)
            reduced_count = len(r.reduced_rules)
            pct = r.reduction_percentage
            reduced_table = copy.deepcopy(table)
            reduced_table.rules = list(r.reduced_rules)
            is_eq, _ = table.is_equivalent_to(reduced_table)
            eq = dbc.Badge("Yes" if is_eq else "No", color="success" if is_eq else "danger")
            rows.append(html.Tr([html.Td(r.method), html.Td(str(orig)), html.Td(str(reduced_count)), html.Td(f"{pct:.0f}%"), html.Td(eq)]))
        return dbc.Table([header, html.Tbody(rows)], bordered=True, hover=True, responsive=True)
    except Exception as e:
        return dbc.Alert(f"Error: {e}", color="danger")


@callback(
    Output("table-store", "data", allow_duplicate=True),
    Input("apply-reduce-btn", "n_clicks"),
    State("reduction-result-store", "data"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def apply_reduction(_, reduced_data, store_data):
    if not reduced_data:
        return dash.no_update
    reduced_table = DecisionTable.from_dict(reduced_data)

    def mutate(t):
        t.rules = reduced_table.rules
    return apply_mutation(store_data, mutate)


# ═══════════════════════════════════════════════════════════════════
# Testing callbacks
# ═══════════════════════════════════════════════════════════════════

def _render_coverage(coverage):
    # Compute condition/action coverage percentages from the dicts
    cond_covered = sum(len(v) for v in coverage.condition_value_coverage.values())
    cond_total = coverage.total_conditions if coverage.total_conditions else max(cond_covered, 1)
    cond_pct = (cond_covered / cond_total * 100) if cond_total else 100.0

    action_covered = sum(len(v) for v in coverage.action_value_coverage.values())
    action_total = coverage.total_actions if coverage.total_actions else max(action_covered, 1)
    action_pct = (action_covered / action_total * 100) if action_total else 100.0

    items = [
        dbc.Col(
            html.Div([
                html.Div(f"{coverage.rule_coverage:.0f}%", className="metric-value"),
                html.Div(f"Rule Coverage ({len(coverage.covered_rules)}/{coverage.total_rules})", className="metric-label"),
            ], className="metric-card"),
            width="auto",
        ),
        dbc.Col(
            html.Div([
                html.Div(f"{cond_pct:.0f}%", className="metric-value", style={"color": "#3fb950"}),
                html.Div(f"Condition Values ({cond_covered}/{cond_total})", className="metric-label"),
            ], className="metric-card"),
            width="auto",
        ),
        dbc.Col(
            html.Div([
                html.Div(f"{action_pct:.0f}%", className="metric-value", style={"color": "#d2a8ff"}),
                html.Div(f"Action Values ({action_covered}/{action_total})", className="metric-label"),
            ], className="metric-card"),
            width="auto",
        ),
    ]
    children = [dbc.Row(items, className="g-3 mb-3")]
    if coverage.uncovered_rules:
        uncovered = ", ".join(f"R{i+1}" for i in sorted(coverage.uncovered_rules))
        children.append(dbc.Alert(f"Uncovered rules: {uncovered}", color="warning"))
    return html.Div(children)


@callback(
    Output("test-results", "children"),
    Output("test-coverage", "children"),
    Output("test-cases-store", "data"),
    Output("export-csv-btn", "disabled"),
    Input("generate-tests-btn", "n_clicks"),
    State("test-type", "value"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def generate_tests(_, test_type, store_data):
    table = store_to_table(store_data)
    if not table.conditions or not table.rules:
        return dbc.Alert("Need conditions and rules.", color="warning"), "", None, True
    try:
        if test_type == "per_rule":
            tests = generate_test_cases(table)
        elif test_type == "boundary":
            tests = generate_boundary_tests(table)
        elif test_type == "pairwise":
            tests = generate_pairwise_tests(table)
        else:
            tests = generate_all_tests(table)

        coverage = calculate_coverage(table, tests)
        cond_names = [c.name for c in table.conditions]
        action_names = [a.name for a in table.actions]

        header_cells = [html.Th("#"), html.Th("Type")]
        for n in cond_names:
            header_cells.append(html.Th(n, style={"color": "#58a6ff"}))
        for n in action_names:
            header_cells.append(html.Th(n, style={"color": "#3fb950"}))
        header_cells.append(html.Th("Covering Rules"))
        header = html.Thead(html.Tr(header_cells))

        rows = []
        for i, tc in enumerate(tests):
            cells = [html.Td(str(i + 1)), html.Td(tc.test_type, className="text-muted small")]
            for n in cond_names:
                cells.append(html.Td(tc.inputs.get(n, "-")))
            for n in action_names:
                cells.append(html.Td(tc.expected_outputs.get(n, "-")))
            covering = ", ".join(f"R{r+1}" for r in tc.covering_rules) if tc.covering_rules else "-"
            cells.append(html.Td(covering, className="text-muted small"))
            rows.append(html.Tr(cells))

        test_table = dbc.Table([header, html.Tbody(rows)], bordered=True, hover=True, responsive=True, size="sm")
        test_data = [
            {"inputs": tc.inputs, "expected_outputs": tc.expected_outputs, "test_type": tc.test_type, "covering_rules": tc.covering_rules}
            for tc in tests
        ]
        return test_table, _render_coverage(coverage), test_data, False
    except Exception as e:
        return dbc.Alert(f"Error: {e}", color="danger"), "", None, True


@callback(
    Output("test-download", "data"),
    Input("export-csv-btn", "n_clicks"),
    State("test-cases-store", "data"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def export_csv(_, test_data, store_data):
    if not test_data:
        return dash.no_update
    table = store_to_table(store_data)
    cond_names = [c.name for c in table.conditions]
    action_names = [a.name for a in table.actions]
    lines = [",".join(["#", "Type"] + cond_names + action_names + ["Covering Rules"])]
    for i, tc in enumerate(test_data):
        row = [str(i + 1), tc["test_type"]]
        for n in cond_names:
            row.append(tc["inputs"].get(n, "-"))
        for n in action_names:
            row.append(tc["expected_outputs"].get(n, "-"))
        covering = "; ".join(f"R{r+1}" for r in tc.get("covering_rules", []))
        row.append(covering)
        lines.append(",".join(row))
    name = table.name.replace(" ", "_") or "decision_table"
    return dcc.send_string("\n".join(lines), f"{name}_tests.csv")


# ═══════════════════════════════════════════════════════════════════
# Constraints callbacks
# ═══════════════════════════════════════════════════════════════════

@callback(
    Output("constraint-form", "children"),
    Input("constraint-type", "value"),
    Input("table-store", "data"),
)
def build_constraint_form(ctype, store_data):
    table = store_to_table(store_data)
    if not table.conditions:
        return html.Small("Add conditions first.", className="text-muted")
    cond_options = [{"label": c.name, "value": c.name} for c in table.conditions]

    if ctype == "implication":
        return html.Div([
            html.Small("IF", className="text-muted fw-bold"),
            dbc.Row([
                dbc.Col(dbc.Select(id="if-cond", options=cond_options, placeholder="Condition", size="sm"), width=6),
                dbc.Col(dbc.Select(id="if-val", options=[], placeholder="Value", size="sm"), width=6),
            ], className="g-1 mb-2"),
            html.Small("THEN", className="text-muted fw-bold"),
            dbc.Row([
                dbc.Col(dbc.Select(id="then-cond", options=cond_options, placeholder="Condition", size="sm"), width=6),
                dbc.Col(dbc.Select(id="then-val", options=[], placeholder="Value", size="sm"), width=6),
            ], className="g-1"),
            html.Div(id="pair-cond-1", style={"display": "none"}),
            html.Div(id="pair-val-1", style={"display": "none"}),
            html.Div(id="pair-cond-2", style={"display": "none"}),
            html.Div(id="pair-val-2", style={"display": "none"}),
        ])
    else:
        label = "Impossible combination:" if ctype == "impossible" else "Mutually exclusive:"
        return html.Div([
            html.Small(label, className="text-muted fw-bold"),
            dbc.Row([
                dbc.Col(dbc.Select(id="pair-cond-1", options=cond_options, placeholder="Condition 1", size="sm"), width=3),
                dbc.Col(dbc.Select(id="pair-val-1", options=[], placeholder="Value 1", size="sm"), width=3),
                dbc.Col(dbc.Select(id="pair-cond-2", options=cond_options, placeholder="Condition 2", size="sm"), width=3),
                dbc.Col(dbc.Select(id="pair-val-2", options=[], placeholder="Value 2", size="sm"), width=3),
            ], className="g-1 mt-1"),
            html.Div(id="if-cond", style={"display": "none"}),
            html.Div(id="if-val", style={"display": "none"}),
            html.Div(id="then-cond", style={"display": "none"}),
            html.Div(id="then-val", style={"display": "none"}),
        ])


@callback(Output("if-val", "options"), Input("if-cond", "value"), State("table-store", "data"), prevent_initial_call=True)
def populate_if_values(cond_name, store_data):
    if not cond_name:
        return []
    table = store_to_table(store_data)
    cond = next((c for c in table.conditions if c.name == cond_name), None)
    return [{"label": v, "value": v} for v in cond.possible_values] if cond else []


@callback(Output("then-val", "options"), Input("then-cond", "value"), State("table-store", "data"), prevent_initial_call=True)
def populate_then_values(cond_name, store_data):
    if not cond_name:
        return []
    table = store_to_table(store_data)
    cond = next((c for c in table.conditions if c.name == cond_name), None)
    return [{"label": v, "value": v} for v in cond.possible_values] if cond else []


@callback(Output("pair-val-1", "options"), Input("pair-cond-1", "value"), State("table-store", "data"), prevent_initial_call=True)
def populate_pair_values_1(cond_name, store_data):
    if not cond_name:
        return []
    table = store_to_table(store_data)
    cond = next((c for c in table.conditions if c.name == cond_name), None)
    return [{"label": v, "value": v} for v in cond.possible_values] if cond else []


@callback(Output("pair-val-2", "options"), Input("pair-cond-2", "value"), State("table-store", "data"), prevent_initial_call=True)
def populate_pair_values_2(cond_name, store_data):
    if not cond_name:
        return []
    table = store_to_table(store_data)
    cond = next((c for c in table.conditions if c.name == cond_name), None)
    return [{"label": v, "value": v} for v in cond.possible_values] if cond else []


@callback(
    Output("table-store", "data", allow_duplicate=True),
    Output("constraint-alert", "children"),
    Output("constraint-alert", "is_open"),
    Output("constraint-alert", "color"),
    Input("add-constraint-btn", "n_clicks"),
    State("constraint-type", "value"),
    State("constraint-desc", "value"),
    State("if-cond", "value"),
    State("if-val", "value"),
    State("then-cond", "value"),
    State("then-val", "value"),
    State("pair-cond-1", "value"),
    State("pair-val-1", "value"),
    State("pair-cond-2", "value"),
    State("pair-val-2", "value"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def add_constraint(_, ctype, desc, if_cond, if_val, then_cond, then_val, pair_cond_1, pair_val_1, pair_cond_2, pair_val_2, store_data):
    try:
        ct = ConstraintType(ctype)
        if ctype == "implication":
            if not all([if_cond, if_val, then_cond, then_val]):
                return dash.no_update, "Fill all fields for implication.", True, "warning"
            conditions = {if_cond: if_val, then_cond: then_val}
        else:
            if not all([pair_cond_1, pair_val_1, pair_cond_2, pair_val_2]):
                return dash.no_update, "Fill all fields.", True, "warning"
            conditions = {pair_cond_1: pair_val_1, pair_cond_2: pair_val_2}
        constraint = Constraint(constraint_type=ct, conditions=conditions, description=desc or "")
        new_store = apply_mutation(store_data, lambda t: t.add_constraint(constraint))
        return new_store, f"Added {ctype} constraint", True, "success"
    except Exception as e:
        return dash.no_update, str(e), True, "danger"


@callback(Output("constraint-list", "children"), Input("table-store", "data"))
def render_constraints(store_data):
    table = store_to_table(store_data)
    if not table.constraints:
        return html.Small("No constraints defined.", className="text-muted")
    items = []
    for i, c in enumerate(table.constraints):
        conds_str = ", ".join(f"{k}={v}" for k, v in c.conditions.items())
        label = f"[{c.constraint_type.value.upper()}] {conds_str}"
        if c.description:
            label += f" -- {c.description}"
        items.append(
            dbc.ListGroupItem(html.Div([
                html.Span(label),
                dbc.Button("Remove", id={"type": "remove-constraint", "index": i}, color="danger", size="sm", className="float-end"),
            ], className="d-flex justify-content-between align-items-center"))
        )
    return dbc.ListGroup(items)


@callback(
    Output("table-store", "data", allow_duplicate=True),
    Output("constraint-alert", "children", allow_duplicate=True),
    Output("constraint-alert", "is_open", allow_duplicate=True),
    Output("constraint-alert", "color", allow_duplicate=True),
    Input({"type": "remove-constraint", "index": ALL}, "n_clicks"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def remove_constraint(n_clicks_list, store_data):
    if not ctx.triggered_id or not any(n for n in n_clicks_list if n):
        return dash.no_update, dash.no_update, False, dash.no_update
    idx = ctx.triggered_id["index"]
    try:
        new_store = apply_mutation(store_data, lambda t: t.remove_constraint(idx))
        return new_store, f"Removed constraint #{idx + 1}", True, "success"
    except Exception as e:
        return dash.no_update, str(e), True, "danger"
