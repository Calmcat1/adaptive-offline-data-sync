# """Adaptive synchronization policy engine.
# Integrates ML-based prediction models (Random Forest / HistGradientBoosting)
# with real-time safety guardrails for adaptive offline data synchronization.
# """
# from pathlib import Path
# from typing import Any, Dict, List, Optional, Tuple
# import joblib
# import numpy as np
# import pandas as pd
# from sklearn.ensemble import HistGradientBoostingClassifier
# MODEL_PATH = Path("models/adaptive_sync_hgbc.joblib")
# FEATURES = [
#     "signal_strength",
#     "bandwidth_kbps",
#     "latency_ms",
#     "battery_percent",
#     "queue_size",
#     "is_wifi",
#     "bandwidth_per_latency",
#     "signal_battery_prod",
# ]
# # Cache loaded model artifact in memory to optimize API response times
# _CACHED_PAYLOAD: Optional[Dict[str, Any]] = None
# def normalize_telemetry(context: Dict[str, Any]) -> Dict[str, Any]:
#     """Standardize field names across SDK and dataset column variants."""
#     key_map = {
#         "SignalStrengthPercent": "signal_strength",
#         "BandwidthKbps": "bandwidth_kbps",
#         "LatencyMs": "latency_ms",
#         "LatencyM": "latency_ms",
#         "BatteryPercent": "battery_percent",
#         "NetworkType": "network_type",
#         "NetworkT": "network_type",
#         "QueueSize": "queue_size",
#         "DataBudgetKb": "data_budget_kb",
#     }
#     normalized = {}
#     for k, v in context.items():
#         standard_key = key_map.get(k, k.lower() if isinstance(k, str) else k)
#         normalized[standard_key] = v
#     return normalized
# def extract_features(context: Dict[str, Any]) -> pd.DataFrame:
#     """Extract base metrics and engineer interaction feature vectors."""
#     ctx = normalize_telemetry(context)
#     signal = float(ctx.get("signal_strength") if ctx.get("signal_strength") is not None else 50.0)
#     bandwidth = float(ctx.get("bandwidth_kbps") if ctx.get("bandwidth_kbps") is not None else 500.0)
#     latency = float(ctx.get("latency_ms") if ctx.get("latency_ms") is not None else 250.0)
#     battery = float(ctx.get("battery_percent") if ctx.get("battery_percent") is not None else 50.0)
#     queue_size = int(ctx.get("queue_size", 0))
#     net_type = str(ctx.get("network_type", "")).lower().strip().replace("-", "")
#     is_wifi = 1 if net_type in ("wifi", "wi-fi") else 0
#     # Interaction feature engineering
#     bandwidth_per_latency = bandwidth / (latency + 1.0)
#     signal_battery_prod = (signal / 100.0) * (battery / 100.0)
#     row = {
#         "signal_strength": signal,
#         "bandwidth_kbps": bandwidth,
#         "latency_ms": latency,
#         "battery_percent": battery,
#         "queue_size": queue_size,
#         "is_wifi": is_wifi,
#         "bandwidth_per_latency": bandwidth_per_latency,
#         "signal_battery_prod": signal_battery_prod,
#     }
#     return pd.DataFrame([row], columns=FEATURES)
# def _load_model() -> Optional[Dict[str, Any]]:
#     """Load model artifact from disk into memory cache."""
#     global _CACHED_PAYLOAD
#     if _CACHED_PAYLOAD is None and MODEL_PATH.exists():
#         try:
#             payload = joblib.load(MODEL_PATH)
#             if not isinstance(payload, dict):
#                 payload = {"model": payload, "threshold": 0.55}
#             _CACHED_PAYLOAD = payload
#         except Exception:
#             _CACHED_PAYLOAD = None
#     return _CACHED_PAYLOAD
# def train_model(observations: List[Dict[str, Any]]) -> Dict[str, Any]:
#     """Train the model from historical observations containing sync_success labels."""
#     global _CACHED_PAYLOAD
#     rows = []
#     for item in observations:
#         if item.get("sync_success") is None:
#             continue
#         feat_df = extract_features(item)
#         row = feat_df.iloc[0].to_dict()
#         row["target"] = 1 if item["sync_success"] else 0
#         rows.append(row)
#     if len(rows) < 20 or len({r["target"] for r in rows}) < 2:
#         return {
#             "trained": False,
#             "samples": len(rows),
#             "message": "Need at least 20 labelled observations with both positive and negative outcomes.",
#         }
#     df = pd.DataFrame(rows)
#     X = df[FEATURES]
#     y = df["target"]
#     model = HistGradientBoostingClassifier(
#         max_iter=150,
#         learning_rate=0.05,
#         max_leaf_nodes=31,
#         min_samples_leaf=5,
#         class_weight="balanced",
#         random_state=42,
#     )
#     model.fit(X, y)
#     MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
#     payload = {"model": model, "threshold": 0.50, "features": FEATURES}
#     joblib.dump(payload, MODEL_PATH)
#     _CACHED_PAYLOAD = payload
#     return {"trained": True, "samples": len(rows), "message": "Adaptive sync model trained and cached successfully."}
# def recommend_sync(context: Dict[str, Any]) -> Dict[str, Any]:
#     """Evaluate telemetry and return an actionable sync strategy decision."""
#     ctx = normalize_telemetry(context)
#     queue_size = int(ctx.get("queue_size", 0))
#     if queue_size <= 0:
#         return {
#             "strategy": "immediate",
#             "should_sync": False,
#             "reason": "No pending records.",
#             "confidence": None,
#         }
#     features_df = extract_features(ctx)
#     confidence = None
#     suitable = None
#     # Step 1: Model Prediction
#     model_payload = _load_model()
#     if model_payload and "model" in model_payload:
#         model = model_payload["model"]
#         threshold = model_payload.get("threshold", 0.50)
#         probs = model.predict_proba(features_df)[0]
#         pos_idx = list(model.classes_).index(1) if 1 in model.classes_ else 1
#         confidence = float(probs[pos_idx])
#         suitable = confidence >= threshold
#     # Step 2: Rule-Based Fallback if model uninitialized
#     signal = ctx.get("signal_strength")
#     bandwidth = ctx.get("bandwidth_kbps")
#     latency = ctx.get("latency_ms")
#     battery = ctx.get("battery_percent")
#     budget = ctx.get("data_budget_kb")
#     net_type = str(ctx.get("network_type", "")).lower().strip().replace("-", "")
#     wifi = net_type in ("wifi", "wi-fi")
#     if suitable is None:
#         suitable = (
#             (signal is None or float(signal) >= 35.0)
#             and (bandwidth is None or float(bandwidth) >= 128.0)
#             and (latency is None or float(latency) <= 1200.0)
#             and (battery is None or float(battery) >= 15.0)
#         )
#     # Step 3: Policy Guardrails
#     if battery is not None and float(battery) < 10.0:
#         return {
#             "strategy": "delayed",
#             "should_sync": False,
#             "reason": "Battery is critically low (<10%); waiting for charging.",
#             "confidence": confidence,
#         }
#     if not suitable:
#         return {
#             "strategy": "delayed",
#             "should_sync": False,
#             "reason": "Network conditions are not currently suitable; retry later.",
#             "confidence": confidence,
#         }
#     if budget is not None and float(budget) < 64.0 and not wifi:
#         return {
#             "strategy": "partial",
#             "should_sync": True,
#             "max_records": min(queue_size, 5),
#             "reason": "Limited data budget; synchronize a small batch.",
#             "confidence": confidence,
#         }
#     if not wifi and queue_size > 50:
#         return {
#             "strategy": "partial",
#             "should_sync": True,
#             "max_records": 25,
#             "reason": "Large queue on cellular network; send a bounded batch.",
#             "confidence": confidence,
#         }
#     return {
#         "strategy": "immediate",
#         "should_sync": True,
#         "max_records": queue_size,
#         "reason": "Current conditions are suitable for synchronization.",
#         "confidence": confidence,
#     }