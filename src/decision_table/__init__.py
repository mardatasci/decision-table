"""Decision table editor with validation, logic reduction, and test generation."""

__version__ = "0.2.0"

from .model import (
    DONT_CARE,
    Action,
    Condition,
    ConditionType,
    Constraint,
    ConstraintType,
    DecisionTable,
    Range,
    Rule,
    TableType,
    make_boolean_condition,
    make_enum_condition,
    make_numeric_condition,
    parse_range,
)
from .validation import (
    Severity,
    ValidationMessage,
    ValidationResult,
    check_completeness,
    check_consistency,
    check_constraints,
    check_contradiction,
    check_redundancy,
    validate_all,
)
from .reduction import (
    ComparisonResult,
    ReductionResult,
    ReductionStep,
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
from .testing import (
    CoverageReport,
    TestCase,
    calculate_coverage,
    export_test_cases_csv,
    generate_all_tests,
    generate_boundary_tests,
    generate_pairwise_tests,
    generate_test_cases,
)
from .serialization import (
    load_csv,
    load_excel,
    load_file,
    load_json,
    save_csv,
    save_excel,
    save_file,
    save_json,
    save_test_cases_csv,
    save_test_cases_excel,
)
