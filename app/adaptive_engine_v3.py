from pathlib import Path
from typing import Optional, Dict, Any, List
import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

MODEL_PATH = Path("models/adaptive_data_sync_model_v1.joblib")
FEATURES = ["signal_strength", "bandwidth_kbps", "latency_ms", "battery_percent", "queue_size", "is_wifi"]

# Global cache for the loaded model to prevent disk read per request
_CACHED_MODEL: Optional[HistGradientBoostingClassifier] = None
_CACHED_MODEL_MTIME: float = 0.0


def _get_model() -> Optional[HistGradientBoostingClassifier]:
    """Retrieves the model from cache, re-loading from disk only if updated."""
    global _CACHED_MODEL, _CACHED_MODEL_MTIME
    if not MODEL_PATH.exists():
        return None

    current_mtime = MODEL_PATH.stat().st_mtime
    if _CACHED_MODEL is None or current_mtime > _CACHED_MODEL_MTIME:
        _CACHED_MODEL = joblib.load(MODEL_PATH)
        _CACHED_MODEL_MTIME = current_mtime

    return _CACHED_MODEL


def _extract_single_row(context: Dict[str, Any], default_queue: int = 0) -> Dict[str, Any]:
    """Helper to extract normalized feature values across key variants."""
    signal = context.get("signal_strength", context.get("SignalStrengthPercent"))
    bandwidth = context.get("bandwidth_kbps", context.get("BandwidthKbps"))
    latency = context.get("latency_ms", context.get("LatencyMs", context.get("LatencyM")))
    battery = context.get("battery_percent", context.get("BatteryPercent"))
    network = context.get("network_type", context.get("NetworkT", "unknown"))
    queue_size = context.get("queue_size", context.get("QueueSize", default_queue))

    is_wifi_val = 1 if str(network).lower().replace("-", "") == "wifi" else 0

    return {
        "signal_strength": float(signal) if signal is not None else 50.0,
        "bandwidth_kbps": float(bandwidth) if bandwidth is not None else 500.0,
        "latency_ms": float(latency) if latency is not None else 250.0,
        "battery_percent": float(battery) if battery is not None else 50.0,
        "queue_size": int(queue_size),
        "is_wifi": is_wifi_val,
    }


def _features(context: Dict[str, Any]) -> pd.DataFrame:
    row = _extract_single_row(context, default_queue=0)
    return pd.DataFrame([row], columns=FEATURES)


def train_model(observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Train from observations using HistGradientBoostingClassifier."""
    global _CACHED_MODEL, _CACHED_MODEL_MTIME
    rows = []
    for item in observations:
        target_val = item.get("sync_success", item.get("SyncSuccess"))
        if target_val is None:
            continue

        row = _extract_single_row(item, default_queue=1)
        row["target"] = 1 if bool(target_val) else 0
        rows.append(row)

    if len(rows) < 20 or len({r["target"] for r in rows}) < 2:
        return {
            "trained": False,
            "samples": len(rows),
            "message": "Need at least 20 labelled observations containing both successful and failed syncs.",
        }

    df = pd.DataFrame(rows)
    model = HistGradientBoostingClassifier(random_state=42, class_weight="balanced")
    model.fit(df[FEATURES], df["target"])

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    # Invalidate cache so local memory picks up the new model immediately
    _CACHED_MODEL = model
    _CACHED_MODEL_MTIME = MODEL_PATH.stat().st_mtime

    return {"trained": True, "samples": len(rows), "message": "HistGradientBoosting model trained and saved."}


def recommend_sync(context: Dict[str, Any]) -> Dict[str, Any]:
    queue_size = int(context.get("queue_size", context.get("QueueSize", 0)))
    if queue_size <= 0:
        return {
            "strategy": "immediate",
            "should_sync": False,
            "reason": "No pending records.",
            "confidence": None,
        }

    features = _features(context)
    confidence = None
    suitable = None

    model = _get_model()
    if model is not None:
        probabilities = model.predict_proba(features)[0]
        if 1 in model.classes_:
            positive_index = list(model.classes_).index(1)
            confidence = float(probabilities[positive_index])
            suitable = confidence >= 0.55
        else:
            confidence = 0.0
            suitable = False

    # Heuristic Rule Fallback if model doesn't exist yet
    signal = context.get("signal_strength", context.get("SignalStrengthPercent"))
    bandwidth = context.get("bandwidth_kbps", context.get("BandwidthKbps"))
    latency = context.get("latency_ms", context.get("LatencyMs", context.get("LatencyM")))
    battery = context.get("battery_percent", context.get("BatteryPercent"))
    budget = context.get("data_budget_kb")
    network = context.get("network_type", context.get("NetworkT"))
    wifi = str(network).lower().replace("-", "") == "wifi" if network else False

    if suitable is None:
        suitable = (
            (signal is None or float(signal) >= 35.0)
            and (bandwidth is None or float(bandwidth) >= 128.0)
            and (latency is None or float(latency) <= 1200.0)
            and (battery is None or float(battery) >= 15.0)
        )

    # Safety Guardrails
    if battery is not None and float(battery) < 10.0:
        return {
            "strategy": "delayed",
            "should_sync": False,
            "reason": "Battery is critically low; wait for charging or a better battery level.",
            "confidence": confidence,
        }
    if not suitable:
        return {
            "strategy": "delayed",
            "should_sync": False,
            "reason": "Network conditions are not currently suitable; retry later.",
            "confidence": confidence,
        }

    if budget is not None and float(budget) < 64.0 and not wifi:
        return {
            "strategy": "partial",
            "should_sync": True,
            "max_records": min(queue_size, 5),
            "reason": "Limited data budget; synchronize a small batch.",
            "confidence": confidence,
        }
    if not wifi and queue_size > 50:
        return {
            "strategy": "partial",
            "should_sync": True,
            "max_records": 25,
            "reason": "Large queue on cellular data; send a bounded batch.",
            "confidence": confidence,
        }
    return {
        "strategy": "immediate",
        "should_sync": True,
        "max_records": queue_size,
        "reason": "Current conditions are suitable for synchronization.",
        "confidence": confidence,
    }