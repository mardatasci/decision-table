"""Tests for serialization (JSON, CSV, Excel)."""

import json
from pathlib import Path

import pytest
from decision_table.model import (
    Action, Condition, Constraint, ConstraintType, DecisionTable, Rule, TableType,
    make_numeric_condition,
)
from decision_table.serialization import (
    load_csv, load_excel, load_file, load_json,
    save_csv, save_excel, save_file, save_json,
)


class TestJSON:
    def test_save_load_roundtrip(self, simple_boolean_table, tmp_path):
        path = tmp_path / "test.json"
        save_json(simple_boolean_table, path)
        loaded = load_json(path)
        assert loaded.name == "Simple Boolean"
        assert len(loaded.conditions) == 2
        assert len(loaded.rules) == 4

    def test_roundtrip_with_constraints(self, constrained_table, tmp_path):
        path = tmp_path / "test.json"
        save_json(constrained_table, path)
        loaded = load_json(path)
        assert len(loaded.constraints) == 1
        assert loaded.constraints[0].constraint_type == ConstraintType.IMPOSSIBLE

    def test_roundtrip_with_else(self, else_table, tmp_path):
        path = tmp_path / "test.json"
        save_json(else_table, path)
        loaded = load_json(path)
        assert any(r.is_else for r in loaded.rules)

    def test_roundtrip_with_numeric(self, numeric_table, tmp_path):
        path = tmp_path / "test.json"
        save_json(numeric_table, path)
        loaded = load_json(path)
        age_cond = next(c for c in loaded.conditions if c.name == "Age")
        assert age_cond.is_numeric
        assert len(age_cond.ranges) == 3


class TestCSV:
    def test_save_load_roundtrip(self, simple_boolean_table, tmp_path):
        path = tmp_path / "test.csv"
        save_csv(simple_boolean_table, path)
        loaded = load_csv(path)
        assert len(loaded.conditions) == 2
        assert len(loaded.rules) == 4

    def test_roundtrip_preserves_values(self, simple_boolean_table, tmp_path):
        path = tmp_path / "test.csv"
        save_csv(simple_boolean_table, path)
        loaded = load_csv(path)
        assert loaded.rules[0].condition_entries["A"] == "T"

    def test_roundtrip_with_else(self, else_table, tmp_path):
        path = tmp_path / "test.csv"
        save_csv(else_table, path)
        loaded = load_csv(path)
        assert any(r.is_else for r in loaded.rules)

    def test_roundtrip_with_constraints(self, constrained_table, tmp_path):
        path = tmp_path / "test.csv"
        save_csv(constrained_table, path)
        loaded = load_csv(path)
        assert len(loaded.constraints) == 1


class TestExcel:
    def test_save_load_roundtrip(self, simple_boolean_table, tmp_path):
        path = tmp_path / "test.xlsx"
        save_excel(simple_boolean_table, path)
        loaded = load_excel(path)
        assert len(loaded.conditions) == 2
        assert len(loaded.rules) == 4

    def test_roundtrip_with_else(self, else_table, tmp_path):
        path = tmp_path / "test.xlsx"
        save_excel(else_table, path)
        loaded = load_excel(path)
        assert any(r.is_else for r in loaded.rules)


class TestFileDispatch:
    def test_save_load_json(self, simple_boolean_table, tmp_path):
        path = tmp_path / "test.json"
        save_file(simple_boolean_table, path)
        loaded = load_file(path)
        assert len(loaded.rules) == 4

    def test_save_load_csv(self, simple_boolean_table, tmp_path):
        path = tmp_path / "test.csv"
        save_file(simple_boolean_table, path)
        loaded = load_file(path)
        assert len(loaded.rules) == 4

    def test_save_load_xlsx(self, simple_boolean_table, tmp_path):
        path = tmp_path / "test.xlsx"
        save_file(simple_boolean_table, path)
        loaded = load_file(path)
        assert len(loaded.rules) == 4

    def test_unsupported_format(self, simple_boolean_table, tmp_path):
        with pytest.raises(ValueError, match="Unsupported"):
            save_file(simple_boolean_table, tmp_path / "test.txt")
