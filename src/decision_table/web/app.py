"""Main Dash application for the Decision Table web editor."""

import base64
import io
import os
import json

import dash
import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, callback, ctx, dcc, html

from decision_table.model import DecisionTable
from decision_table.serialization import load_json, load_csv, load_excel, save_json, save_csv, save_excel
from decision_table.web.state import empty_store, store_to_table, do_undo, do_redo

pages_dir = os.path.join(os.path.dirname(__file__), "pages")
assets_dir = os.path.join(os.path.dirname(__file__), "assets")

app = dash.Dash(
    __name__,
    use_pages=True,
    pages_folder=pages_dir,
    assets_folder=assets_dir,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True,
    title="Decision Table Editor",
)

# Silently ignore callbacks from browser extensions that inject unknown
# Dash components (e.g. accessibility scanners adding "scan-trigger").
@app.server.errorhandler(KeyError)
def _handle_unknown_callback(exc):
    if "Callback function not found" in str(exc):
        return "", 204
    raise exc

# Sidebar navigation
sidebar = dbc.Nav(
    [
        dbc.NavLink("Editor", href="/", active="exact"),
        html.Hr(),
        dbc.NavLink("Settings", href="/settings", active="exact"),
    ],
    vertical=True,
    pills=True,
    className="flex-column",
)

# Toolbar
toolbar = dbc.Row(
    [
        dbc.Col(
            dbc.ButtonGroup(
                [
                    dbc.Button("New", id="toolbar-new", color="secondary", size="sm"),
                    dcc.Upload(
                        dbc.Button("Open", color="secondary", size="sm"),
                        id="toolbar-open",
                        accept=".json,.csv,.xlsx",
                    ),
                    dbc.Button("Save", id="toolbar-save", color="secondary", size="sm"),
                ],
            ),
            width="auto",
        ),
        dbc.Col(
            dbc.ButtonGroup(
                [
                    dbc.Button("Undo", id="toolbar-undo", color="secondary", size="sm"),
                    dbc.Button("Redo", id="toolbar-redo", color="secondary", size="sm"),
                ],
            ),
            width="auto",
        ),
        dbc.Col(
            dbc.Select(
                id="save-format",
                options=[
                    {"label": "JSON", "value": "json"},
                    {"label": "CSV", "value": "csv"},
                    {"label": "Excel", "value": "xlsx"},
                ],
                value="json",
                size="sm",
                style={"width": "100px"},
            ),
            width="auto",
        ),
        dbc.Col(
            html.Span(id="toolbar-status", className="text-muted small"),
            width="auto",
            className="ms-auto",
        ),
    ],
    className="g-2 mb-3 align-items-center",
)

# Main layout
app.layout = dbc.Container(
    [
        dbc.Row(
            [
                # Sidebar
                dbc.Col(
                    [
                        html.H4("Decision Table", className="text-light mb-1 mt-3"),
                        html.Small("Web Editor", className="text-muted"),
                        html.Hr(),
                        sidebar,
                        html.Hr(),
                        html.Div(id="sidebar-info", className="px-2"),
                    ],
                    width=2,
                    className="bg-dark vh-100 position-fixed",
                    style={"overflowY": "auto"},
                ),
                # Main content
                dbc.Col(
                    [
                        toolbar,
                        dash.page_container,
                    ],
                    width=10,
                    className="ms-auto p-4",
                ),
            ],
        ),
        # Global stores
        dcc.Store(id="table-store", storage_type="session", data=empty_store()),
        dcc.Store(id="output-message", data=""),
        dcc.Download(id="file-download"),
    ],
    fluid=True,
    className="p-0",
)


# ── Sidebar info ──
@callback(
    Output("sidebar-info", "children"),
    Input("table-store", "data"),
)
def update_sidebar_info(store_data):
    table = store_to_table(store_data)
    return [
        html.Div(
            [
                html.Small(table.name, className="text-light d-block fw-bold"),
                html.Small(
                    f"{len(table.conditions)}C / {len(table.actions)}A / {len(table.rules)}R",
                    className="text-muted d-block",
                ),
                html.Small(
                    table.table_type.value.replace("_", " ").title(),
                    className="text-muted d-block",
                ),
            ],
        ),
    ]


# ── Toolbar: New ──
@callback(
    Output("table-store", "data", allow_duplicate=True),
    Output("toolbar-status", "children", allow_duplicate=True),
    Input("toolbar-new", "n_clicks"),
    prevent_initial_call=True,
)
def toolbar_new(_):
    return empty_store(), "New table created"


# ── Toolbar: Open file ──
@callback(
    Output("table-store", "data", allow_duplicate=True),
    Output("toolbar-status", "children", allow_duplicate=True),
    Input("toolbar-open", "contents"),
    State("toolbar-open", "filename"),
    prevent_initial_call=True,
)
def toolbar_open(contents, filename):
    if contents is None:
        return dash.no_update, dash.no_update

    _, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)

    try:
        if filename.endswith(".json"):
            data = json.loads(decoded.decode("utf-8"))
            table = DecisionTable.from_dict(data)
        elif filename.endswith(".csv"):
            buf = io.StringIO(decoded.decode("utf-8"))
            # Write to temp file for load_csv
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
                f.write(buf.getvalue())
                tmp = f.name
            table = load_csv(tmp)
            os.unlink(tmp)
        elif filename.endswith(".xlsx"):
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
                f.write(decoded)
                tmp = f.name
            table = load_excel(tmp)
            os.unlink(tmp)
        else:
            return dash.no_update, f"Unsupported format: {filename}"
    except Exception as e:
        return dash.no_update, f"Error loading {filename}: {e}"

    from decision_table.web.state import table_to_store
    store = table_to_store(table)
    return store, f"Loaded {filename}"


# ── Toolbar: Save ──
@callback(
    Output("file-download", "data"),
    Output("toolbar-status", "children", allow_duplicate=True),
    Input("toolbar-save", "n_clicks"),
    State("table-store", "data"),
    State("save-format", "value"),
    prevent_initial_call=True,
)
def toolbar_save(_, store_data, fmt):
    table = store_to_table(store_data)
    name = table.name.replace(" ", "_") or "decision_table"

    try:
        if fmt == "json":
            content = json.dumps(table.to_dict(), indent=2)
            return dcc.send_string(content, f"{name}.json"), f"Saved {name}.json"
        elif fmt == "csv":
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
                tmp = f.name
            save_csv(table, tmp)
            with open(tmp) as f:
                content = f.read()
            os.unlink(tmp)
            return dcc.send_string(content, f"{name}.csv"), f"Saved {name}.csv"
        elif fmt == "xlsx":
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
                tmp = f.name
            save_excel(table, tmp)
            with open(tmp, "rb") as f:
                content = f.read()
            os.unlink(tmp)
            return dcc.send_bytes(content, f"{name}.xlsx"), f"Saved {name}.xlsx"
    except Exception as e:
        return dash.no_update, f"Save error: {e}"

    return dash.no_update, "Unknown format"


# ── Toolbar: Undo/Redo ──
@callback(
    Output("table-store", "data", allow_duplicate=True),
    Output("toolbar-status", "children", allow_duplicate=True),
    Input("toolbar-undo", "n_clicks"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def toolbar_undo(_, store_data):
    result = do_undo(store_data)
    if result is store_data:
        return dash.no_update, "Nothing to undo"
    return result, "Undo"


@callback(
    Output("table-store", "data", allow_duplicate=True),
    Output("toolbar-status", "children", allow_duplicate=True),
    Input("toolbar-redo", "n_clicks"),
    State("table-store", "data"),
    prevent_initial_call=True,
)
def toolbar_redo(_, store_data):
    result = do_redo(store_data)
    if result is store_data:
        return dash.no_update, "Nothing to redo"
    return result, "Redo"
