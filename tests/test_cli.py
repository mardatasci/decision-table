"""Tests for the CLI interface."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from decision_table.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def table_file(tmp_path):
    data = {
        "name": "Test",
        "conditions": [
            {"name": "A", "possible_values": ["T", "F"], "condition_type": "boolean"},
            {"name": "B", "possible_values": ["T", "F"], "condition_type": "boolean"},
        ],
        "actions": [{"name": "X", "possible_values": ["X", ""]}],
        "rules": [
            {"condition_entries": {"A": "T", "B": "T"}, "action_entries": {"X": "X"}},
            {"condition_entries": {"A": "T", "B": "F"}, "action_entries": {"X": "X"}},
            {"condition_entries": {"A": "F", "B": "T"}, "action_entries": {"X": ""}},
            {"condition_entries": {"A": "F", "B": "F"}, "action_entries": {"X": ""}},
        ],
        "table_type": "single_hit",
        "metadata": {},
    }
    path = tmp_path / "test.json"
    path.write_text(json.dumps(data))
    return str(path)


class TestCreate:
    def test_create(self, runner, tmp_path):
        output = str(tmp_path / "new.json")
        result = runner.invoke(cli, ["create", "My Table", "-o", output])
        assert result.exit_code == 0
        data = json.loads(Path(output).read_text())
        assert data["name"] == "My Table"
        assert data["table_type"] == "single_hit"


class TestShow:
    def test_show(self, runner, table_file):
        result = runner.invoke(cli, ["show", table_file])
        assert result.exit_code == 0
        assert "Test" in result.output


class TestCondition:
    def test_add_boolean(self, runner, table_file):
        result = runner.invoke(cli, ["condition", "add", table_file, "C"])
        assert result.exit_code == 0

    def test_add_numeric(self, runner, table_file):
        result = runner.invoke(cli, ["condition", "add", table_file, "Age",
                                     "--values", "<18,18-64,>=65", "--type", "numeric"])
        assert result.exit_code == 0
        data = json.loads(Path(table_file).read_text())
        age = next(c for c in data["conditions"] if c["name"] == "Age")
        assert age["condition_type"] == "numeric"

    def test_remove(self, runner, table_file):
        result = runner.invoke(cli, ["condition", "remove", table_file, "B"])
        assert result.exit_code == 0


class TestRule:
    def test_add(self, runner, table_file):
        result = runner.invoke(cli, ["rule", "add", table_file, "-c", "A=T,B=T", "-a", "X=X"])
        assert result.exit_code == 0

    def test_add_with_priority(self, runner, table_file):
        result = runner.invoke(cli, ["rule", "add", table_file, "-c", "A=T,B=T", "-a", "X=X", "-p", "10"])
        assert result.exit_code == 0
        data = json.loads(Path(table_file).read_text())
        assert data["rules"][-1]["priority"] == 10

    def test_duplicate(self, runner, table_file):
        result = runner.invoke(cli, ["rule", "duplicate", table_file, "0"])
        assert result.exit_code == 0
        data = json.loads(Path(table_file).read_text())
        assert len(data["rules"]) == 5

    def test_move(self, runner, table_file):
        result = runner.invoke(cli, ["rule", "move", table_file, "0", "2"])
        assert result.exit_code == 0


class TestConstraint:
    def test_add_and_list(self, runner, table_file):
        result = runner.invoke(cli, ["constraint", "add", table_file,
                                     "--type", "impossible", "-c", "A=T,B=T"])
        assert result.exit_code == 0
        result = runner.invoke(cli, ["constraint", "list", table_file])
        assert result.exit_code == 0
        assert "impossible" in result.output

    def test_remove(self, runner, table_file):
        runner.invoke(cli, ["constraint", "add", table_file,
                           "--type", "impossible", "-c", "A=T,B=T"])
        result = runner.invoke(cli, ["constraint", "remove", table_file, "0"])
        assert result.exit_code == 0


class TestValidate:
    def test_validate_all(self, runner, table_file):
        result = runner.invoke(cli, ["validate", table_file])
        assert result.exit_code == 0

    def test_validate_constraints(self, runner, table_file):
        result = runner.invoke(cli, ["validate", table_file, "--check", "constraints"])
        assert result.exit_code == 0


class TestReduce:
    def test_reduce_qm(self, runner, table_file):
        result = runner.invoke(cli, ["reduce", table_file])
        assert result.exit_code == 0
        assert "Quine-McCluskey" in result.output

    def test_reduce_petrick(self, runner, table_file):
        result = runner.invoke(cli, ["reduce", table_file, "--method", "petrick"])
        assert result.exit_code == 0

    def test_reduce_with_output(self, runner, table_file, tmp_path):
        output = str(tmp_path / "reduced.json")
        result = runner.invoke(cli, ["reduce", table_file, "-o", output])
        assert result.exit_code == 0
        assert Path(output).exists()


class TestCompare:
    def test_compare(self, runner, table_file):
        result = runner.invoke(cli, ["compare", table_file])
        assert result.exit_code == 0


class TestConvert:
    def test_json_to_csv(self, runner, table_file, tmp_path):
        output = str(tmp_path / "test.csv")
        result = runner.invoke(cli, ["convert", table_file, "-o", output])
        assert result.exit_code == 0

    def test_json_to_excel(self, runner, table_file, tmp_path):
        output = str(tmp_path / "test.xlsx")
        result = runner.invoke(cli, ["convert", table_file, "-o", output])
        assert result.exit_code == 0


class TestTesting:
    def test_generate_all(self, runner, table_file):
        result = runner.invoke(cli, ["test", "generate", table_file])
        assert result.exit_code == 0
        assert "test cases" in result.output.lower()

    def test_generate_with_export(self, runner, table_file, tmp_path):
        output = str(tmp_path / "tests.csv")
        result = runner.invoke(cli, ["test", "generate", table_file, "-o", output])
        assert result.exit_code == 0
        assert Path(output).exists()

    def test_coverage(self, runner, table_file):
        result = runner.invoke(cli, ["test", "coverage", table_file])
        assert result.exit_code == 0
        assert "coverage" in result.output.lower()
