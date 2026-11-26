import pandas as pd

from anomaly import isolation_forest, seasonal_baseline
from generate_data import generate
from rules import RULE_TYPES, evaluate_rules


def main():
    configs, runs, start, end = generate()

    # Notification rules are configured for half of the integrations with an SLA.
    with_sla = configs[configs["sla_min"].notna()]["integration_id"]
    monitored = with_sla.sample(frac=0.5, random_state=1)
    rules = pd.DataFrame(
        [(integration_id, rule_type)
         for integration_id in monitored
         for rule_type in RULE_TYPES],
        columns=["integration_id", "rule_type"],
    )

    notifications = evaluate_rules(configs, runs, rules, start, end)
    seasonal = seasonal_baseline(runs)
    forest = isolation_forest(runs)

    print(
        f"Integrations: {len(configs)} | with SLA: {len(with_sla)} | "
        f"with notification rules: {len(monitored)}"
    )
    print("Notifications by type:")
    print(notifications["rule_type"].value_counts().to_string())
    print(f"Seasonal-baseline anomalies: {len(seasonal)}")
    print(f"Isolation-forest anomalies: {len(forest)}")

    notifications.to_csv("notifications.csv", index=False)


if __name__ == "__main__":
    main()
