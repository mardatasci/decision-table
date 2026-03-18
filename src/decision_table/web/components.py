"""Reusable UI components for the decision table web app."""

from __future__ import annotations

from dash import html

from decision_table.model import DONT_CARE, ConditionType, DecisionTable


def build_decision_grid(table: DecisionTable) -> html.Div:
    """Build the decision table as an interactive HTML grid.

    Each cell gets a dict id for pattern-matching callbacks:
        {"type": "grid-cell", "kind": "condition"|"action", "row": i, "col": j}
    """
    if not table.conditions and not table.actions:
        return html.Div(
            "Add conditions and actions to get started.",
            className="text-muted p-4 text-center",
        )

    n_rules = len(table.rules)

    # Build header row: first cell is empty label, then R1, R2, ...
    header_cells = [html.Th("", className="dt-corner")]
    header_cells.append(html.Th("Type", className="dt-header-type"))
    for j, rule in enumerate(table.rules):
        label = f"R{j + 1}"
        cls = "dt-header-else" if rule.is_else else "dt-header-rule"
        if rule.is_else:
            label += " ELSE"
        header_cells.append(html.Th(label, className=cls))
    header = html.Thead(html.Tr(header_cells))

    rows = []

    # Condition rows
    for i, cond in enumerate(table.conditions):
        cells = [
            html.Td(cond.name, className="dt-row-label dt-label-condition"),
            html.Td(
                _type_badge(cond.condition_type),
                className="dt-type-cell",
            ),
        ]
        for j, rule in enumerate(table.rules):
            val = rule.condition_entries.get(cond.name, DONT_CARE)
            cell_cls = "dt-cell-else" if rule.is_else else "dt-cell-condition"
            if val == DONT_CARE:
                cell_cls += " dt-cell-dontcare"
            cells.append(
                html.Td(
                    val,
                    id={"type": "grid-cell", "kind": "condition", "row": i, "col": j},
                    className=cell_cls,
                    n_clicks=0,
                )
            )
        rows.append(html.Tr(cells))

    # Separator row
    if table.conditions and table.actions:
        sep_cols = 2 + n_rules
        rows.append(
            html.Tr(
                html.Td(
                    "",
                    colSpan=sep_cols,
                    className="dt-separator",
                )
            )
        )

    # Action rows
    for i, action in enumerate(table.actions):
        cells = [
            html.Td(action.name, className="dt-row-label dt-label-action"),
            html.Td("", className="dt-type-cell"),
        ]
        for j, rule in enumerate(table.rules):
            val = rule.action_entries.get(action.name, "")
            cell_cls = "dt-cell-else" if rule.is_else else "dt-cell-action"
            if not val:
                cell_cls += " dt-cell-empty"
            cells.append(
                html.Td(
                    val if val else "\u00a0",  # nbsp for empty
                    id={"type": "grid-cell", "kind": "action", "row": i, "col": j},
                    className=cell_cls,
                    n_clicks=0,
                )
            )
        rows.append(html.Tr(cells))

    tbody = html.Tbody(rows)
    return html.Div(
        html.Table([header, tbody], className="dt-grid"),
        className="dt-grid-wrapper",
    )


def _type_badge(ct: ConditionType) -> str:
    labels = {
        ConditionType.BOOLEAN: "bool",
        ConditionType.ENUM: "enum",
        ConditionType.NUMERIC: "num",
    }
    return labels.get(ct, "")


def build_metric_card(value: str | int, label: str, color: str = "#58a6ff") -> html.Div:
    """Build a small metric display card."""
    return html.Div(
        [
            html.Div(str(value), className="metric-value", style={"color": color}),
            html.Div(label, className="metric-label"),
        ],
        className="metric-card",
    )


def build_status_bar(table: DecisionTable) -> html.Div:
    """Build a status bar showing table summary metrics."""
    import dash_bootstrap_components as dbc

    items = [
        build_metric_card(len(table.conditions), "Conditions"),
        build_metric_card(len(table.actions), "Actions"),
        build_metric_card(len(table.rules), "Rules", "#3fb950"),
        build_metric_card(len(table.constraints), "Constraints", "#d2a8ff"),
        build_metric_card(table.table_type.value.replace("_", " ").title(), "Hit Policy", "#d29922"),
    ]
    return dbc.Row(
        [dbc.Col(item, width="auto") for item in items],
        className="g-3 mb-3",
    )
