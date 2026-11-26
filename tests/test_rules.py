import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rules import evaluate_rules  # noqa: E402


def test_detects_error_sla_breach_and_skip():
    start, end = datetime(2026, 1, 1, 0, 0), datetime(2026, 1, 1, 1, 0)
    configs = pd.DataFrame([{
        "integration_id": "INT-001",
        "interval_min": 15,
        "base_duration_min": 5,
        "sla_min": 10,
    }])
    runs = pd.DataFrame([
        {
            "integration_id": "INT-001",
            "scheduled_at": datetime(2026, 1, 1, 0, 0),
            "duration_min": 5,
            "status": "success",
        },
        {
            "integration_id": "INT-001",
            "scheduled_at": datetime(2026, 1, 1, 0, 15),
            "duration_min": 12,
            "status": "success",
        },
        {
            "integration_id": "INT-001",
            "scheduled_at": datetime(2026, 1, 1, 0, 30),
            "duration_min": 5,
            "status": "error",
        },
    ])
    rules = pd.DataFrame(
        [("INT-001", rule_type) for rule_type in ("skipped", "sla_breach", "error")],
        columns=["integration_id", "rule_type"],
    )

    result = evaluate_rules(configs, runs, rules, start, end)
    assert set(result["rule_type"]) == {"skipped", "sla_breach", "error"}
    assert len(result) == 3
