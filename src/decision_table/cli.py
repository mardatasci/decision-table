"""CLI interface for the decision table editor."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table as RichTable

from .model import (
    Action, Condition, Constraint, ConstraintType, DecisionTable,
    Rule, TableType, make_boolean_condition, make_enum_condition,
    make_numeric_condition,
)
from .reduction import (
    clustering_reduction, compare_reductions, espresso, incremental_reduction,
    petricks_method, positive_region_reduction, quine_mccluskey, rule_merging,
    variable_precision_reduction,
)
from .serialization import load_file, save_file
from .testing import (
    calculate_coverage, export_test_cases_csv, generate_all_tests,
    generate_boundary_tests, generate_pairwise_tests, generate_test_cases,
)
from .validation import (
    Severity, check_completeness, check_consistency, check_constraints,
    check_contradiction, check_redundancy, validate_all,
)

console = Console()


def _load_table(path: str) -> DecisionTable:
    try:
        return load_file(path)
    except FileNotFoundError:
        console.print(f"[red]Error: File '{path}' not found.[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error loading file: {e}[/red]")
        raise SystemExit(1)


def _save_table(table: DecisionTable, path: str) -> None:
    try:
        save_file(table, path)
        console.print(f"[green]Saved to {path}[/green]")
    except Exception as e:
        console.print(f"[red]Error saving file: {e}[/red]")
        raise SystemExit(1)


def _display_table(table: DecisionTable) -> None:
    """Display a decision table using rich."""
    rt = RichTable(title=table.name, show_lines=True)
    rt.add_column("", style="bold")
    for i, rule in enumerate(table.rules):
        label = f"R{i + 1}"
        if rule.is_else:
            label += " (ELSE)"
        if rule.priority != 0:
            label += f" p={rule.priority}"
        rt.add_column(label, justify="center")

    for cond in table.conditions:
        type_str = f" [{cond.condition_type.value}]" if not cond.is_boolean else ""
        values = [rule.condition_entries.get(cond.name, "-") for rule in table.rules]
        rt.add_row(f"[cyan]{cond.name}{type_str}[/cyan]", *values)

    for action in table.actions:
        values = [rule.action_entries.get(action.name, "") for rule in table.rules]
        rt.add_row(f"[green]{action.name}[/green]", *values)

    console.print(rt)

    info = f"  {len(table.conditions)} conditions, {len(table.actions)} actions, {len(table.rules)} rules"
    info += f"  |  Type: {table.table_type.value}"
    if table.constraints:
        info += f"  |  {len(table.constraints)} constraints"
    console.print(info)


@click.group()
def cli():
    """Decision Table Editor - Create, validate, and optimize decision tables."""
    pass


@cli.command()
@click.argument("name")
@click.option("-o", "--output", required=True, help="Output file path")
@click.option("--type", "table_type", type=click.Choice(["single_hit", "multi_hit"]),
              default="single_hit", help="Table type")
def create(name: str, output: str, table_type: str):
    """Create a new empty decision table."""
    table = DecisionTable(name=name, table_type=TableType(table_type))
    _save_table(table, output)


@cli.command()
@click.argument("file")
def show(file: str):
    """Display a decision table."""
    table = _load_table(file)
    _display_table(table)
    if table.constraints:
        console.print("\n[bold]Constraints:[/bold]")
        for i, c in enumerate(table.constraints):
            console.print(f"  {i}: [{c.constraint_type.value}] {c.conditions} - {c.description}")


@cli.group()
def condition():
    """Manage conditions."""
    pass


@condition.command("add")
@click.argument("file")
@click.argument("name")
@click.option("--values", default="T,F", help="Comma-separated possible values")
@click.option("--type", "cond_type", type=click.Choice(["boolean", "enum", "numeric"]),
              default="boolean", help="Condition type")
@click.option("--description", default="", help="Condition description")
def condition_add(file: str, name: str, values: str, cond_type: str, description: str):
    """Add a condition to the table."""
    table = _load_table(file)
    val_list = [v.strip() for v in values.split(",")]
    if cond_type == "numeric":
        cond = make_numeric_condition(name, val_list, description)
    elif cond_type == "enum":
        cond = make_enum_condition(name, val_list, description)
    else:
        cond = make_boolean_condition(name, description)
    table.add_condition(cond)
    _save_table(table, file)


@condition.command("remove")
@click.argument("file")
@click.argument("name")
def condition_remove(file: str, name: str):
    """Remove a condition from the table."""
    table = _load_table(file)
    table.remove_condition(name)
    _save_table(table, file)


@cli.group()
def action():
    """Manage actions."""
    pass


@action.command("add")
@click.argument("file")
@click.argument("name")
@click.option("--values", default="X,", help="Comma-separated possible values")
@click.option("--description", default="", help="Action description")
def action_add(file: str, name: str, values: str, description: str):
    """Add an action to the table."""
    table = _load_table(file)
    possible_values = [v.strip() for v in values.split(",")]
    table.add_action(Action(name=name, possible_values=possible_values, description=description))
    _save_table(table, file)


@action.command("remove")
@click.argument("file")
@click.argument("name")
def action_remove(file: str, name: str):
    """Remove an action from the table."""
    table = _load_table(file)
    table.remove_action(name)
    _save_table(table, file)


@cli.group()
def rule():
    """Manage rules."""
    pass


@rule.command("add")
@click.argument("file")
@click.option("--conditions", "-c", required=True, help="Condition entries: 'A=T,B=F'")
@click.option("--actions", "-a", required=True, help="Action entries: 'X1=X,X2='")
@click.option("--priority", "-p", default=0, help="Rule priority (higher wins)")
@click.option("--else-rule", is_flag=True, help="Mark as else (catch-all) rule")
def rule_add(file: str, conditions: str, actions: str, priority: int, else_rule: bool):
    """Add a rule to the table."""
    table = _load_table(file)

    cond_entries = {}
    for pair in conditions.split(","):
        key, _, val = pair.partition("=")
        cond_entries[key.strip()] = val.strip()

    action_entries = {}
    for pair in actions.split(","):
        key, _, val = pair.partition("=")
        action_entries[key.strip()] = val.strip()

    table.add_rule(Rule(
        condition_entries=cond_entries, action_entries=action_entries,
        priority=priority, is_else=else_rule,
    ))
    _save_table(table, file)


@rule.command("remove")
@click.argument("file")
@click.argument("index", type=int)
def rule_remove(file: str, index: int):
    """Remove a rule by index (0-based)."""
    table = _load_table(file)
    table.remove_rule(index)
    _save_table(table, file)


@rule.command("duplicate")
@click.argument("file")
@click.argument("index", type=int)
def rule_duplicate(file: str, index: int):
    """Duplicate a rule."""
    table = _load_table(file)
    table.duplicate_rule(index)
    _save_table(table, file)


@rule.command("move")
@click.argument("file")
@click.argument("from_idx", type=int)
@click.argument("to_idx", type=int)
def rule_move(file: str, from_idx: int, to_idx: int):
    """Move a rule from one position to another."""
    table = _load_table(file)
    table.move_rule(from_idx, to_idx)
    _save_table(table, file)


@cli.group()
def constraint():
    """Manage constraints."""
    pass


@constraint.command("add")
@click.argument("file")
@click.option("--type", "ctype", type=click.Choice(["exclusion", "implication", "impossible"]),
              required=True, help="Constraint type")
@click.option("--conditions", "-c", required=True, help="Condition entries: 'A=T,B=F'")
@click.option("--description", "-d", default="", help="Description")
def constraint_add(file: str, ctype: str, conditions: str, description: str):
    """Add a constraint."""
    table = _load_table(file)
    cond_entries = {}
    for pair in conditions.split(","):
        key, _, val = pair.partition("=")
        cond_entries[key.strip()] = val.strip()
    table.add_constraint(Constraint(
        constraint_type=ConstraintType(ctype),
        conditions=cond_entries,
        description=description,
    ))
    _save_table(table, file)


@constraint.command("remove")
@click.argument("file")
@click.argument("index", type=int)
def constraint_remove(file: str, index: int):
    """Remove a constraint by index."""
    table = _load_table(file)
    table.remove_constraint(index)
    _save_table(table, file)


@constraint.command("list")
@click.argument("file")
def constraint_list(file: str):
    """List all constraints."""
    table = _load_table(file)
    if not table.constraints:
        console.print("No constraints defined.")
        return
    for i, c in enumerate(table.constraints):
        console.print(f"  {i}: \\[{c.constraint_type.value}] {c.conditions} - {c.description}")


@cli.command()
@click.argument("file")
@click.option("--check", type=click.Choice([
    "completeness", "redundancy", "contradiction", "consistency", "constraints", "all"
]), default="all", help="Which check to run")
def validate(file: str, check: str):
    """Validate a decision table."""
    table = _load_table(file)

    checks = {
        "consistency": check_consistency,
        "completeness": check_completeness,
        "redundancy": check_redundancy,
        "contradiction": check_contradiction,
        "constraints": check_constraints,
        "all": validate_all,
    }
    result = checks[check](table)

    for msg in result.messages:
        if msg.severity == Severity.ERROR:
            console.print(f"  [red]ERROR[/red] [{msg.check}] {msg.message}")
        elif msg.severity == Severity.WARNING:
            console.print(f"  [yellow]WARN[/yellow]  [{msg.check}] {msg.message}")
        else:
            console.print(f"  [green]OK[/green]    [{msg.check}] {msg.message}")

    if result.is_valid:
        console.print("\n[green]Validation passed.[/green]")
    else:
        console.print("\n[red]Validation failed with errors.[/red]")


@cli.command()
@click.argument("file")
@click.option("--method", type=click.Choice([
    "qm", "petrick", "merge", "espresso", "prr", "vpr", "clustering", "incremental", "all",
]), default="qm", help="Reduction method")
@click.option("--steps", is_flag=True, help="Show step-by-step details")
@click.option("-o", "--output", default=None, help="Save reduced table to file")
def reduce(file: str, method: str, steps: bool, output: str | None):
    """Reduce a decision table using logic minimization."""
    table = _load_table(file)

    methods = {
        "qm": quine_mccluskey,
        "petrick": petricks_method,
        "merge": rule_merging,
        "espresso": espresso,
        "prr": positive_region_reduction,
        "vpr": variable_precision_reduction,
        "clustering": clustering_reduction,
        "incremental": incremental_reduction,
    }

    if method == "all":
        comparison = compare_reductions(table)
        for res in [comparison.qm_result, comparison.petrick_result,
                    comparison.rule_merging_result, comparison.espresso_result]:
            if res:
                _show_reduction(res, steps)
                console.print()
    else:
        result = methods[method](table)
        _show_reduction(result, steps)
        if output:
            reduced_table = DecisionTable(
                name=f"{table.name} (reduced)",
                conditions=list(table.conditions),
                actions=list(table.actions),
                rules=result.reduced_rules,
                constraints=list(table.constraints),
                table_type=table.table_type,
            )
            _save_table(reduced_table, output)


def _show_reduction(result, steps: bool):
    console.print(f"\n[bold]{result.method}[/bold]")
    console.print(f"  Original rules: {len(result.original_rules)}")
    console.print(f"  Reduced rules:  {len(result.reduced_rules)}")
    console.print(f"  Reduction:      {result.reduction_count} rules ({result.reduction_percentage:.1f}%)")

    if steps:
        console.print("\n[bold]Steps:[/bold]")
        for i, step in enumerate(result.steps, 1):
            console.print(f"  {i}. {step.description}")
            if step.details:
                for key, value in step.details.items():
                    console.print(f"     {key}: {value}")


@cli.command()
@click.argument("file")
def compare(file: str):
    """Compare reduction methods side by side."""
    table = _load_table(file)
    comparison = compare_reductions(table)

    rt = RichTable(title="Reduction Comparison", show_lines=True)
    rt.add_column("Metric")
    rt.add_column("Quine-McCluskey", justify="center")
    rt.add_column("Petrick's", justify="center")
    rt.add_column("Rule Merging", justify="center")
    rt.add_column("Espresso", justify="center")
    rt.add_column("PRR (RST)", justify="center")
    rt.add_column("VPR (RST)", justify="center")
    rt.add_column("Clustering", justify="center")

    results = [comparison.qm_result, comparison.petrick_result,
               comparison.rule_merging_result, comparison.espresso_result,
               comparison.prr_result, comparison.vpr_result,
               comparison.clustering_result]
    rt.add_row("Original rules", *[str(len(r.original_rules)) for r in results])
    rt.add_row("Reduced rules", *[str(len(r.reduced_rules)) for r in results])
    rt.add_row("Reduction", *[f"{r.reduction_percentage:.1f}%" for r in results])

    console.print(rt)


@cli.command()
@click.argument("input_file")
@click.option("-o", "--output", required=True, help="Output file (format by extension)")
def convert(input_file: str, output: str):
    """Convert a decision table between formats (JSON, CSV, Excel)."""
    table = _load_table(input_file)
    _save_table(table, output)


# ── Test case commands ──

@cli.group()
def test():
    """Generate and manage test cases."""
    pass


@test.command("generate")
@click.argument("file")
@click.option("--type", "test_type", type=click.Choice(["normal", "boundary", "pairwise", "all"]),
              default="all", help="Type of test cases to generate")
@click.option("-o", "--output", default=None, help="Export test cases to CSV")
def test_generate(file: str, test_type: str, output: str | None):
    """Generate test cases from a decision table."""
    table = _load_table(file)

    generators = {
        "normal": generate_test_cases,
        "boundary": generate_boundary_tests,
        "pairwise": generate_pairwise_tests,
        "all": generate_all_tests,
    }
    test_cases = generators[test_type](table)

    # Display
    rt = RichTable(title=f"Test Cases ({test_type})", show_lines=True)
    rt.add_column("#", justify="right")
    rt.add_column("Type")
    for c in table.conditions:
        rt.add_column(c.name, justify="center")
    for a in table.actions:
        rt.add_column(a.name, justify="center", style="green")
    rt.add_column("Rules")

    for i, tc in enumerate(test_cases, 1):
        row = [str(i), tc.test_type]
        row.extend(tc.inputs.get(c.name, "") for c in table.conditions)
        row.extend(tc.expected_outputs.get(a.name, "") for a in table.actions)
        row.append(", ".join(f"R{r+1}" for r in tc.covering_rules))
        rt.add_row(*row)

    console.print(rt)
    console.print(f"  {len(test_cases)} test cases generated")

    # Coverage
    coverage = calculate_coverage(table, test_cases)
    console.print(f"\n[bold]Coverage:[/bold]")
    console.print(f"  {coverage.summary()}")

    if output:
        export_test_cases_csv(test_cases, table, output)
        console.print(f"\n[green]Test cases exported to {output}[/green]")


@test.command("coverage")
@click.argument("file")
def test_coverage(file: str):
    """Show coverage report for all test types."""
    table = _load_table(file)
    test_cases = generate_all_tests(table)
    coverage = calculate_coverage(table, test_cases)
    console.print(f"[bold]Coverage Report[/bold]")
    console.print(coverage.summary())


if __name__ == "__main__":
    cli()
