"""Anomaly detection on execution durations: seasonal baseline and isolation forest."""
import numpy as np
from sklearn.ensemble import IsolationForest


def seasonal_baseline(runs, threshold=3.5):
    """Detect robust z-score outliers per integration and hour of day."""
    df = runs[runs["status"] == "success"].copy()
    df["hour"] = df["scheduled_at"].dt.hour
    grouped = df.groupby(["integration_id", "hour"])["duration_min"]
    median = grouped.transform("median")
    mad = grouped.transform(lambda values: (values - values.median()).abs().median())
    df["robust_z"] = (
        0.6745 * (df["duration_min"] - median) / mad.replace(0, np.nan)
    )
    return df[df["robust_z"].abs() > threshold]


def isolation_forest(runs, contamination=0.01, seed=42):
    """Detect unsupervised outliers using hour and relative duration."""
    df = runs[runs["status"] == "success"].copy()
    df["hour"] = df["scheduled_at"].dt.hour
    df["relative_duration"] = (
        df["duration_min"]
        / df.groupby("integration_id")["duration_min"].transform("median")
    )
    features = df[["hour", "relative_duration"]]
    model = IsolationForest(
        contamination=contamination,
        random_state=seed,
    ).fit(features)
    return df[model.predict(features) == -1]
