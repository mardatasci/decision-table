"""State management: serialize/deserialize DecisionTable + undo stack for dcc.Store."""

from __future__ import annotations

import copy
from typing import Any, Callable

from decision_table.model import DecisionTable

MAX_UNDO = 50


def empty_store() -> dict[str, Any]:
    """Return initial store state with a blank DecisionTable."""
    table = DecisionTable()
    return {
        "table": table.to_dict(),
        "undo": [],
        "redo": [],
    }


def store_to_table(store_data: dict[str, Any]) -> DecisionTable:
    """Reconstruct a DecisionTable from store data."""
    if store_data is None:
        return DecisionTable()
    return DecisionTable.from_dict(store_data["table"])


def table_to_store(
    table: DecisionTable,
    undo: list[dict] | None = None,
    redo: list[dict] | None = None,
) -> dict[str, Any]:
    """Serialize table + stacks into store-safe dict."""
    return {
        "table": table.to_dict(),
        "undo": undo or [],
        "redo": redo or [],
    }


def apply_mutation(
    store_data: dict[str, Any],
    mutation_fn: Callable[[DecisionTable], None],
) -> dict[str, Any]:
    """Apply a mutation to the table, saving undo state.

    Returns the new store data dict.
    """
    if store_data is None:
        store_data = empty_store()

    # Save current state to undo stack
    undo = list(store_data.get("undo", []))
    undo.append(copy.deepcopy(store_data["table"]))
    if len(undo) > MAX_UNDO:
        undo.pop(0)

    # Reconstruct, mutate (without using DecisionTable's own undo)
    table = DecisionTable.from_dict(store_data["table"])
    # Temporarily disable internal undo to avoid double-tracking
    table._undo_stack = []
    table._redo_stack = []
    mutation_fn(table)

    return {
        "table": table.to_dict(),
        "undo": undo,
        "redo": [],  # Clear redo on new mutation
    }


def do_undo(store_data: dict[str, Any]) -> dict[str, Any]:
    """Undo the last mutation."""
    if store_data is None or not store_data.get("undo"):
        return store_data

    undo = list(store_data["undo"])
    redo = list(store_data.get("redo", []))

    # Push current to redo
    redo.append(copy.deepcopy(store_data["table"]))
    # Pop from undo
    prev = undo.pop()

    return {"table": prev, "undo": undo, "redo": redo}


def do_redo(store_data: dict[str, Any]) -> dict[str, Any]:
    """Redo the last undone mutation."""
    if store_data is None or not store_data.get("redo"):
        return store_data

    undo = list(store_data["undo"])
    redo = list(store_data.get("redo", []))

    # Push current to undo
    undo.append(copy.deepcopy(store_data["table"]))
    # Pop from redo
    nxt = redo.pop()

    return {"table": nxt, "undo": undo, "redo": redo}
