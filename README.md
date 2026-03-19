# Decision Table Editor

A tool for creation, editing, management, and optimization of decision tables. Designed for software development students learning requirements management, development, and testing.

> **Disclaimer:** This software is provided for research and educational purposes only. It is provided "as is" without warranty of any kind, express or implied. The authors and contributors assume no responsibility or liability for any errors, omissions, or damages arising from the use of this software. Use at your own risk.

## Features

### Core
- **Condition types**: Boolean (T/F), Enum (custom values), Numeric ranges (`<18`, `18-64`, `>=65`) with automatic boundary value extraction
- **Constraints**: Exclusion, implication, and impossible-combination constraints between conditions
- **Else rules**: Catch-all default rules for unspecified input combinations
- **Rule priority**: Higher-priority rules win when overlapping (single-hit tables)
- **Table types**: Single-hit (one rule fires) or multi-hit (multiple rules fire)
- **Don't-care entries**: Use `-` to match any value for a condition

### Validation
- **Completeness**: Finds uncovered input combinations
- **Redundancy**: Detects duplicate rules with same inputs and outputs
- **Contradiction**: Finds rules with same inputs but different outputs
- **Consistency**: Validates structure, references, and constraint definitions
- **Constraint check**: Reports which combinations are excluded by constraints
- All checks are constraint-aware (skip impossible combinations)

### Logic Reduction (8 algorithms)

#### Row Reduction (merge/eliminate rules)
- **Quine-McCluskey**: Systematic prime implicant identification and greedy minimal cover
- **Petrick's Method**: Guaranteed optimal minimal cover via product-of-sums expansion
- **Rule Merging**: Intuitive pairwise merging of rules differing in one condition -- best for learning
- **Espresso**: Industry-standard heuristic (UC Berkeley) using expand/irredundant/reduce iterations -- best for large tables

#### Column Reduction (remove dispensable conditions)
- **Positive Region Reduction (RST)**: Rough Set Theory method that finds the minimal set of conditions preserving the positive region -- identifies and removes conditions that don't affect decision-making
- **Variable Precision Reduction (RST)**: Extends PRR with a configurable accuracy threshold (0.0-1.0) for tolerating noise -- ranks conditions by conditional entropy and removes the least significant ones
- **Clustering-Based Reduction**: Groups correlated conditions using Partitioning Around Medoids (PAM), selects the most representative condition from each cluster, and verifies decision logic is preserved

#### Dynamic Reduction
- **Incremental Reduction**: Updates a previous reduction when rules change, only re-reducing affected action profiles -- wraps any base method (QM, Petrick, Merge, Espresso) with automatic fallback to full reduction when needed

#### Shared Features
- **Multi-valued support**: Post-processing collapses expanded rules back into don't-cares
- **Compare All**: Run all 7 methods side by side to compare results
- **Equivalence check**: Verify original and reduced tables produce identical outputs
- **Undo Reduce**: Restore original rules after reduction

### Test Generation
- **Per-rule test cases**: One test per rule for full rule coverage
- **Boundary value analysis**: Auto-generated tests at numeric range boundaries
- **Pairwise (all-pairs)**: Minimal test set covering all 2-way value combinations
- **Coverage metrics**: Rule coverage, condition value coverage, action value coverage
- **Export**: Test cases to CSV

### File Formats
- **JSON**: Full-fidelity format with constraints, priorities, condition types, and metadata
- **CSV**: Human-readable with metadata rows for constraints and priorities
- **Excel**: Color-coded with formatting (condition rows blue, action rows green, else rows highlighted)
- Full roundtrip support for all features across all formats

### Interfaces
- **CLI** (`dt`): Full-featured command-line interface
- **GUI** (`dt-gui`): Single-window Tkinter application with professional styling
- **Web UI** (`dt-web`): Browser-based Dash application with dark theme, tabbed analysis panels, and full editing capabilities
- **Python API**: Import and use programmatically

### Editing
- **Undo/Redo**: Full undo/redo for all edits (50-level stack), Ctrl+Z / Ctrl+Y
- **Multi-select removal**: Select and remove multiple conditions, actions, or rules at once
- **Duplicate rules**: Copy an existing rule to modify
- **Move rules**: Reorder rules left/right
- **Click-to-cycle**: Click any cell in the grid to cycle through values
- **Table rename**: Rename the table from the File menu

## Installation

### Prerequisites

- Python 3.10 or higher
- Tkinter (required for GUI only)

#### Installing Tkinter

**macOS (Homebrew):**
```bash
brew install python-tk@3.12
```
Replace `3.12` with your Python version.

**Windows:**
Tkinter is included with the standard Python installer from [python.org](https://www.python.org/downloads/). If missing, re-run the installer, click "Modify", and check "tcl/tk and IDLE".

**Ubuntu/Debian:**
```bash
sudo apt install python3-tk
```

**Fedora:**
```bash
sudo dnf install python3-tkinter
```

**Arch Linux:**
```bash
sudo pacman -S tk
```

### Install the package

```bash
# Create and activate a virtual environment
python -m venv venv

# macOS/Linux
source venv/bin/activate

# Windows (Command Prompt)
venv\Scripts\activate.bat

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Install with dependencies
pip install -e ".[dev]"

# Install with web UI support
pip install -e ".[web]"

# Install everything
pip install -e ".[dev,web]"

# Or install from requirements.txt
pip install -r requirements.txt
```

## Usage

### Web UI

```bash
dt-web
# or
python -m decision_table.web.run

# Options
dt-web --port 8055          # custom port (default: 8050)
dt-web --debug              # enable hot-reload for development
dt-web --host 0.0.0.0       # bind to all interfaces
```

Open your browser to `http://127.0.0.1:8050` (or the port you specified).

The web UI provides a single-page editor with everything in one view:

- **Toolbar**: New, Open (upload JSON/CSV/Excel), Save (download), Undo, Redo, format selector
- **Status bar**: Condition/action/rule/constraint counts and hit policy at a glance
- **Add cards**: Inline forms to add conditions (boolean/enum/numeric), actions, and rules (regular, else, copy last)
- **Remove dropdown**: Select and remove any condition, action, or rule
- **Grid editor**: Click any cell to cycle through its values (conditions cycle through values + don't-care, actions cycle through values)
- **Analysis tabs** (below the grid):
  - **Validation**: Run all 5 checks or individual checks, styled error/warning/info messages with rule references
  - **Reduction**: Choose from 8 algorithms (4 row, 3 column, 1 incremental), view reduced table, compare all methods side-by-side, apply results
  - **Testing**: Generate per-rule, boundary value, or pairwise tests, view coverage metrics, export to CSV
  - **Constraints**: Add/remove impossible, exclusion, or implication constraints with dynamic forms
- **Settings page**: Rename table, change hit policy (single/multi-hit), view table details

### Desktop GUI

```bash
dt-gui
# or
python -m decision_table.gui.app
```

The desktop GUI provides:
- **Toolbar**: New, Open, Save, Undo, Redo, Add/Copy/Remove Rule, Validate, Reduce, Tests
- **Add bar**: Inline forms to add conditions (boolean/enum/numeric) and actions
- **Remove bar**: Multi-select listboxes to remove conditions, actions, or rules (Cmd/Ctrl+click for multiple)
- **Grid editor**: Click cells to cycle values, condition/action type labels shown
- **Reduction**: Method selector (Quine-McCluskey or Petrick), Undo Reduce button
- **Output panel**: Light-themed panel at bottom showing validation, reduction, and test results
- **Menus**: File, Edit, Analysis, Testing, Constraints, Help
- **Help menu**: Quick Start Guide, Keyboard Shortcuts, Condition Types, Constraint Types, Reduction Algorithms, Test Generation, About
- **Keyboard shortcuts**: Ctrl+N/O/S, Ctrl+Z/Y, F5 (validate), F6 (tests), Ctrl+Q (quit)
- **Visual cues**: Else rules highlighted in gold, condition types labeled [numeric]/[enum], priorities shown in headers

### CLI

The `dt` command is available after installation.

#### Create a table

```bash
dt create "My Table" -o table.json
dt create "Multi-Hit Table" -o table.json --type multi_hit
```

#### Add conditions

```bash
# Boolean (default)
dt condition add table.json "Has License"

# Enum
dt condition add table.json "Color" --values "Red,Green,Blue" --type enum

# Numeric ranges
dt condition add table.json "Age" --values "<18,18-64,>=65" --type numeric
```

#### Add actions

```bash
dt action add table.json "Approve" --values "X,"
dt action add table.json "Risk" --values "Low,Medium,High,"
```

#### Add rules

```bash
dt rule add table.json -c "Age=18-64,Has License=T" -a "Approve=X"
dt rule add table.json -c "Age=<18,Has License=-" -a "Approve=" --else-rule
dt rule add table.json -c "Age=>=65,Has License=T" -a "Approve=X" -p 10  # priority
```

#### Rule management

```bash
dt rule duplicate table.json 0    # copy rule 0
dt rule move table.json 0 3       # move rule 0 to position 3
dt rule remove table.json 2       # remove rule 2
```

#### Constraints

```bash
# Add constraints
dt constraint add table.json --type impossible -c "Age=<18,Coverage=Premium" -d "Minors can't get Premium"
dt constraint add table.json --type implication -c "Age=<18,Smoker=F" -d "Minors assumed non-smoker"
dt constraint add table.json --type exclusion -c "A=T,B=T" -d "A and B are mutually exclusive"

# List and remove
dt constraint list table.json
dt constraint remove table.json 0
```

#### Display

```bash
dt show table.json
```

#### Validate

```bash
dt validate table.json                          # all checks
dt validate table.json --check completeness     # specific check
dt validate table.json --check constraints      # see excluded combos
```

Available checks: `completeness`, `redundancy`, `contradiction`, `consistency`, `constraints`, `all`

#### Reduce

```bash
dt reduce table.json                          # Quine-McCluskey (default)
dt reduce table.json --method petrick         # Petrick's Method
dt reduce table.json --method merge           # Rule Merging
dt reduce table.json --method espresso        # Espresso
dt reduce table.json --method prr             # Positive Region Reduction (RST)
dt reduce table.json --method vpr             # Variable Precision Reduction (RST)
dt reduce table.json --method clustering      # Clustering-Based Reduction
dt reduce table.json --method incremental     # Incremental Reduction
dt reduce table.json --method all             # run all methods
dt reduce table.json --steps                  # show step-by-step
dt reduce table.json -o reduced.json          # save reduced table
```

#### Compare reduction methods

```bash
dt compare table.json
```

#### Convert between formats

```bash
dt convert table.json -o table.csv
dt convert table.json -o table.xlsx
dt convert table.csv -o table.json
```

#### Test case generation

```bash
# Generate test cases
dt test generate table.json                          # all types
dt test generate table.json --type normal            # one per rule
dt test generate table.json --type boundary          # boundary values (numeric)
dt test generate table.json --type pairwise          # pairwise combinatorial
dt test generate table.json -o tests.csv             # export to CSV

# Coverage report
dt test coverage table.json
```

### Python API

```python
from decision_table import (
    DecisionTable, Condition, Action, Rule, Constraint,
    ConstraintType, make_numeric_condition, make_boolean_condition,
    validate_all, quine_mccluskey, generate_all_tests, calculate_coverage,
    save_file, load_file,
)

# Build a table
table = DecisionTable(name="Example")
table.add_condition(make_numeric_condition("Age", ["<18", "18-64", ">=65"]))
table.add_condition(make_boolean_condition("Member"))
table.add_action(Action(name="Discount", possible_values=["10%", "20%", ""]))

table.add_rule(Rule(
    condition_entries={"Age": ">=65", "Member": "-"},
    action_entries={"Discount": "10%"},
))

# Add constraint
table.add_constraint(Constraint(
    constraint_type=ConstraintType.IMPOSSIBLE,
    conditions={"Age": "<18", "Member": "T"},
    description="Minors can't be members",
))

# Validate
result = validate_all(table)
print(f"Valid: {result.is_valid}")

# Reduce (row reduction)
reduced = quine_mccluskey(table)
print(f"Reduced from {len(reduced.original_rules)} to {len(reduced.reduced_rules)} rules")

# Column reduction (remove dispensable conditions)
from decision_table import positive_region_reduction, variable_precision_reduction
prr = positive_region_reduction(table)
vpr = variable_precision_reduction(table, threshold=0.9)  # allow 10% noise

# Incremental reduction (reuse previous result after edits)
from decision_table import incremental_reduction
first = quine_mccluskey(table)
# ... modify table ...
updated = incremental_reduction(table, previous_result=first, method="qm")

# Generate tests
tests = generate_all_tests(table)
coverage = calculate_coverage(table, tests)
print(coverage.summary())

# Undo/redo
table.undo()  # undo last change
table.redo()  # redo

# Save/load (format auto-detected by extension)
save_file(table, "example.json")
save_file(table, "example.csv")
save_file(table, "example.xlsx")
loaded = load_file("example.json")
```

## Examples

Sample decision tables are provided in the `samples/` and `examples/` directories:

| File | Features showcased |
|------|-------------------|
| `samples/insurance_full_featured.json` | Numeric ranges, enum, boolean, constraints, else rule, priority |
| `samples/insurance_full_featured.csv` | Same table in CSV format with metadata rows |
| `samples/shipping_discount.csv` | Basic boolean table, reducible (8 to 5 rules) |
| `samples/login_validation.csv` | Don't-care entries |
| `samples/grade_assignment.csv` | Multi-action table |
| `samples/insurance_risk.csv` | Risk assessment |
| `samples/traffic_light.csv` | Don't-cares, 50% reduction |
| `examples/shipping_discount.json` | Shipping discount in JSON |
| `examples/login_validation.json` | Login validation in JSON |

```bash
# View a sample
dt show samples/insurance_full_featured.json

# Validate
dt validate samples/insurance_full_featured.json

# Reduce (see reduction in action)
dt reduce samples/shipping_discount.csv

# Generate tests with coverage
dt test generate samples/insurance_full_featured.json

# Convert formats
dt convert samples/insurance_full_featured.json -o table.xlsx
```

## Running Tests

```bash
# Run all 153 tests
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=decision_table

# Generate coverage XML (for CI)
pytest tests/ --cov=decision_table --cov-report=xml
```

## Project Structure

```
decision_table/
├── pyproject.toml          # Package config, entry points (dt, dt-gui, dt-web)
├── requirements.txt        # Pinned dependencies
├── LICENSE                 # MIT License
├── README.md
├── src/decision_table/
│   ├── __init__.py         # Public API (all exports)
│   ├── model.py            # Core: Condition, Action, Rule, Constraint, DecisionTable
│   ├── validation.py       # 5 checks: completeness, redundancy, contradiction, consistency, constraints
│   ├── reduction.py        # 8 algorithms: QM, Petrick, Rule Merging, Espresso, PRR, VPR, Clustering, Incremental
│   ├── testing.py          # Test case generation, BVA, pairwise, coverage metrics
│   ├── serialization.py    # JSON, CSV, Excel I/O + test case export
│   ├── cli.py              # Click-based CLI (dt command)
│   ├── gui/
│   │   └── app.py          # Single-window Tkinter GUI (dt-gui command)
│   └── web/
│       ├── __init__.py
│       ├── app.py           # Dash application, layout, toolbar, sidebar, file I/O
│       ├── run.py           # Entry point (dt-web command)
│       ├── state.py         # State management: serialize/deserialize for dcc.Store + undo/redo
│       ├── components.py    # Reusable UI components (grid builder, metric cards, status bar)
│       ├── assets/
│       │   └── style.css    # Dark theme CSS (DARKLY + custom grid/validation styles)
│       └── pages/
│           ├── editor.py    # Main editor: grid, add/remove, validation/reduction/testing/constraints tabs
│           └── settings.py  # Table metadata and configuration
├── tests/                  # 153 tests
│   ├── conftest.py         # Shared fixtures
│   ├── test_model.py       # Model tests (conditions, rules, constraints, undo/redo)
│   ├── test_validation.py  # Validation tests (all 5 checks)
│   ├── test_reduction.py   # Reduction tests (all 8 algorithms + comparison)
│   ├── test_serialization.py # I/O roundtrip tests (JSON, CSV, Excel)
│   ├── test_cli.py         # CLI command tests
│   └── test_testing.py     # Test generation tests (normal, BVA, pairwise, coverage)
├── samples/                # Sample tables (CSV, JSON) showcasing all features
└── examples/               # Additional example tables (JSON)
```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| click | >= 8.0 | CLI framework |
| openpyxl | >= 3.1 | Excel file support |
| rich | >= 13.0 | Pretty CLI table output |
| tkinter | (stdlib) | Desktop GUI - ships with Python |
| dash | >= 2.14 | Web UI framework (optional, `pip install -e ".[web]"`) |
| dash-bootstrap-components | >= 1.5 | Web UI Bootstrap components (optional) |
| pytest | >= 8.0 | Testing (dev) |
| pytest-cov | >= 5.0 | Coverage reporting (dev) |

## Disclaimer

This software is provided for **research and educational purposes only**. It is provided "as is" without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement.

In no event shall the authors or contributors be liable for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the software or the use or other dealings in the software.

**Use at your own risk.** No guarantee is made regarding the correctness, completeness, or reliability of any output produced by this tool.

## Acknowledgments

Built with assistance from [Claude](https://claude.ai) by Anthropic.

## License

MIT License. See [LICENSE](LICENSE) for details.
