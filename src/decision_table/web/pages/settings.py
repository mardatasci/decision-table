"""Settings page -- table metadata and configuration."""

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, html

from decision_table.model import TableType
from decision_table.web.state import apply_mutation, store_to_table

dash.register_page(__name__, path="/settings", name="Settings")

layout = html.Div(
    [
        html.H2("Settings", className="mb-3"),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Table Metadata"),
                            dbc.CardBody(
                                [
                                    dbc.Label("Table Name", className="small text-muted"),
                                    dbc.Input(
                                        id="settings-name",
                                        placeholder="Table name",
                                        size="sm",
                                        className="mb-3",
                                    ),
                                    dbc.Label("Hit Policy", className="small text-muted"),
                                    dbc.RadioItems(
                                        id="settings-hit-policy",
                                        options=[
                                            {"label": "Single Hit (one rule fires)", "value": "single_hit"},
                                            {"label": "Multi Hit (multiple rules fire)", "value": "multi_hit"},
                                        ],
                                        value="single_hit",
                                        className="mb-3",
                                    ),
                                    dbc.Button(
                                        "Apply Settings",
                                        id="apply-settings-btn",
                                        color="primary",
                                        size="sm",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    width=6,
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Table Info"),
                            dbc.CardBody(id="settings-info"),
                        ],
                    ),
                    width=6,
                ),
            ],
            className="g-3",
        ),
        dbc.Alert(id="settings-alert", is_open=False, duration=4000, className="mt-3"),
    ],
)


# ── Populate settings from current table ──
@callback(
    Output("settings-name", "value"),
    Output("settings-hit-policy", "value"),
    Output("settings-info", "children"),
    Input("table-store", "data"),
)
def populate_settings(store_data):
    table = store_to_table(store_data)

    info_items = [
        html.Div([html.Strong("Name: "), html.Span(table.name)], className="mb-1"),
        html.Div(
            [
                html.Strong("Hit Policy: "),
                html.Span(table.table_type.value.replace("_", " ").title()),
            ],
            className="mb-1",
        ),
        html.Div(
            [html.Strong("Conditions: "), html.Span(str(len(table.conditions)))],
            className="mb-1",
        ),
        html.Div(
            [html.Strong("Actions: "), html.Span(str(len(table.actions)))],
            className="mb-1",
        ),
        html.Div(
            [html.Strong("Rules: "), html.Span(str(len(table.rules)))],
            className="mb-1",
        ),
        html.Div(
            [html.Strong("Constraints: "), html.Span(str(len(table.constraints)))],
            className="mb-1",
        ),
    ]

    # Show condition details
    if table.conditions:
        cond_details = []
        for c in table.conditions:
            vals = ", ".join(c.possible_values)
            cond_details.append(
                html.Li(
                    f"{c.name} ({c.condition_type.value}): {vals}",
                    className="small text-muted",
                )
            )
        info_items.append(html.Hr())
        info_items.append(html.Strong("Condition Details:"))
        info_items.append(html.Ul(cond_details, className="mb-0"))

    if table.actions:
        action_details = []
        for a in table.actions:
            vals = ", ".join(repr(v) for v in a.possible_values)
            action_details.append(
                html.Li(f"{a.name}: {vals}", className="small text-muted")
            )
        info_items.append(html.Hr())
        info_items.append(html.Strong("Action Details:"))
        info_items.append(html.Ul(action_details, className="mb-0"))

    return table.name, table.table_type.value, html.Div(info_items)


# ── Apply settings ──
@callback(
    Output("table-store", "data", allow_duplicate=True),
    Output("settings-alert", "children"),
    Output("settings-alert", "is_open"),
    Output("settings-alert", "color"),
    Input("apply-settings-btn", "n_clicks"),
    State("settings-name", "value"),
    State("settings-hit-policy", "value"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def apply_settings(_, name, hit_policy, store_data):
    try:
        new_name = (name or "").strip() or "Untitled"
        new_type = TableType(hit_policy)

        def mutate(t):
            t.name = new_name
            t.table_type = new_type

        new_store = apply_mutation(store_data, mutate)
        return new_store, "Settings applied", True, "success"
    except Exception as e:
        return dash.no_update, str(e), True, "danger"
