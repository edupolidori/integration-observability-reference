"""Generates synthetic integration execution data. No real or proprietary data is used."""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def generate(n_integrations=20, days=30, seed=42):
    """Generate integration configurations and scheduled execution records."""
    rng = np.random.default_rng(seed)
    start = datetime(2026, 1, 1)
    end = start + timedelta(days=days)

    configs = []
    for i in range(n_integrations):
        base = float(rng.uniform(2, 20))
        configs.append({
            "integration_id": f"INT-{i + 1:03d}",
            "interval_min": int(rng.choice([15, 30, 60])),
            "base_duration_min": round(base, 2),
            # About 60% of integrations have an SLA threshold.
            "sla_min": round(base * 2, 1) if rng.random() < 0.6 else np.nan,
        })

    runs = []
    for cfg in configs:
        t = start
        while t < end:
            business_hours = 8 <= t.hour < 18
            factor = 1.3 if business_hours else 1.0
            duration = max(
                0.5,
                rng.normal(
                    cfg["base_duration_min"] * factor,
                    cfg["base_duration_min"] * 0.1,
                ),
            )
            status = "success"
            r = rng.random()
            if r < 0.01:
                t += timedelta(minutes=cfg["interval_min"])
                continue
            if r < 0.02:
                status = "error"
            elif r < 0.03:
                duration *= rng.uniform(3, 6)
            runs.append({
                "integration_id": cfg["integration_id"],
                "scheduled_at": t,
                "duration_min": round(duration, 2),
                "status": status,
            })
            t += timedelta(minutes=cfg["interval_min"])

    return pd.DataFrame(configs), pd.DataFrame(runs), start, end
