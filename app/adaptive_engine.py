"""Adaptive synchronization policy.
The Random Forest is trained from historical sync outcomes when enough labelled
observations exist. Until then, a transparent rule-based fallback is used. The
model predicts whether current conditions are suitable for a sync attempt; the
policy then considers queue size, battery, and data budget.
"""

from pathlib import Path
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

MODEL_PATH = Path("models/random_forest_sync.joblib")
FEATURES = ["signal_strength", "bandwidth_kbps", "latency_ms", "battery_percent", "queue_size", "is_wifi"]

def _features(context: dict) -> pd.DataFrame:
    network = context.get("network_type", "unknown")
    row = {
        "signal_strength": context.get("signal_strength") if context.get("signal_strength") is not None else 50,
        "bandwidth_kbps": context.get("bandwidth_kbps") if context.get("bandwidth_kbps") is not None else 500,
        "latency_ms": context.get("latency_ms") if context.get("latency_ms") is not None else 250,
        "battery_percent": context.get("battery_percent") if context.get("battery_percent") is not None else 50,
        "queue_size": context.get("queue_size", 0),
        "is_wifi": 1 if network == "wifi" else 0,
    }
    return pd.DataFrame([row], columns=FEATURES)

def train_model(observations: list[dict]) -> dict:
    """Train from observations with boolean sync_success labels. Returns counts/status."""
    rows = []
    for item in observations:
        if item.get("sync_success") is None:
            continue
        row = {
            "signal_strength": item.get("signal_strength") if item.get("signal_strength") is not None else 50,
            "bandwidth_kbps": item.get("bandwidth_kbps") if item.get("bandwidth_kbps") is not None else 500,
            "latency_ms": item.get("latency_ms") if item.get("latency_ms") is not None else 250,
            "battery_percent": item.get("battery_percent") if item.get("battery_percent") is not None else 50,
            "queue_size": item.get("queue_size", 1),
            "is_wifi": 1 if item.get("network_type") == "wifi" else 0,
            "target": 1 if item["sync_success"] else 0,
        }
        rows.append(row)
    if len(rows) < 20 or len({r["target"] for r in rows}) < 2:
        return {"trained": False, "samples": len(rows), "message": "Need at least 20 labelled observations containing both successful and failed syncs."}
    df = pd.DataFrame(rows)
    model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight="balanced")
    model.fit(df[FEATURES], df["target"])
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    return {"trained": True, "samples": len(rows), "message": "Random Forest model trained and saved."}

def recommend_sync(context: dict) -> dict:
    queue_size = int(context.get("queue_size", 0))
    if queue_size <= 0:
        return {"strategy": "immediate", "should_sync": False, "reason": "No pending records.", "confidence": None}

    features = _features(context)
    confidence = None
    suitable = None
    if MODEL_PATH.exists():
        model = joblib.load(MODEL_PATH)
        probabilities = model.predict_proba(features)[0]
        positive_index = list(model.classes_).index(1)
        confidence = float(probabilities[positive_index])
        suitable = confidence >= 0.55

    # Safe, explainable fallback if training data is not available.
    signal = context.get("signal_strength")
    bandwidth = context.get("bandwidth_kbps")
    latency = context.get("latency_ms")
    battery = context.get("battery_percent")
    budget = context.get("data_budget_kb")
    wifi = context.get("network_type") == "wifi"

    if suitable is None:
        suitable = (
            (signal is None or signal >= 35)
            and (bandwidth is None or bandwidth >= 128)
            and (latency is None or latency <= 1200)
            and (battery is None or battery >= 15)
        )

    if battery is not None and battery < 10:
        return {"strategy": "delayed", "should_sync": False, "reason": "Battery is critically low; wait for charging or a better battery level.", "confidence": confidence}
    if not suitable:
        return {"strategy": "delayed", "should_sync": False, "reason": "Network conditions are not currently suitable; retry later.", "confidence": confidence}

    if budget is not None and budget < 64 and not wifi:
        return {"strategy": "partial", "should_sync": True, "max_records": min(queue_size, 5), "reason": "Limited data budget; synchronize a small batch.", "confidence": confidence}
    if not wifi and queue_size > 50:
        return {"strategy": "partial", "should_sync": True, "max_records": 25, "reason": "Large queue on cellular data; send a bounded batch.", "confidence": confidence}
    return {"strategy": "immediate", "should_sync": True, "max_records": queue_size, "reason": "Current conditions are suitable for synchronization.", "confidence": confidence}
