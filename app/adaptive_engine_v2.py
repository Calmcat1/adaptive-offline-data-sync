# from pathlib import Path
# import joblib
# import pandas as pd
# from sklearn.ensemble import HistGradientBoostingClassifier
# MODEL_PATH = Path("models/adaptive_data_sync_model_v1.joblib")
# FEATURES = ["signal_strength", "bandwidth_kbps", "latency_ms", "battery_percent", "queue_size", "is_wifi"]
# def _features(context: dict) -> pd.DataFrame:
#     # Accept standard snake_case, PascalCase, or common dataset variants
#     signal = context.get("signal_strength", context.get("SignalStrengthPercent"))
#     bandwidth = context.get("bandwidth_kbps", context.get("BandwidthKbps"))
#     latency = context.get("latency_ms", context.get("LatencyMs", context.get("LatencyM")))
#     battery = context.get("battery_percent", context.get("BatteryPercent"))
#     network = context.get("network_type", context.get("NetworkT", "unknown"))
#     queue_size = context.get("queue_size", context.get("QueueSize", 0))
#     is_wifi_val = 1 if str(network).lower().replace("-", "") == "wifi" else 0
#     row = {
#         "signal_strength": signal if signal is not None else 50,
#         "bandwidth_kbps": bandwidth if bandwidth is not None else 500,
#         "latency_ms": latency if latency is not None else 250,
#         "battery_percent": battery if battery is not None else 50,
#         "queue_size": queue_size,
#         "is_wifi": is_wifi_val,
#     }
#     return pd.DataFrame([row], columns=FEATURES)
# def train_model(observations: list[dict]) -> dict:
#     """Train from observations using HistGradientBoostingClassifier. Returns counts/status."""
#     rows = []
#     for item in observations:
#         target_val = item.get("sync_success", item.get("SyncSuccess"))
#         if target_val is None:
#             continue  
#         signal = item.get("signal_strength", item.get("SignalStrengthPercent"))
#         bandwidth = item.get("bandwidth_kbps", item.get("BandwidthKbps"))
#         latency = item.get("latency_ms", item.get("LatencyMs", item.get("LatencyM")))
#         battery = item.get("battery_percent", item.get("BatteryPercent"))
#         network = item.get("network_type", item.get("NetworkT", "unknown"))
#         queue_size = item.get("queue_size", item.get("QueueSize", 1))
#         is_wifi_val = 1 if str(network).lower().replace("-", "") == "wifi" else 0
#         row = {
#             "signal_strength": signal if signal is not None else 50,
#             "bandwidth_kbps": bandwidth if bandwidth is not None else 500,
#             "latency_ms": latency if latency is not None else 250,
#             "battery_percent": battery if battery is not None else 50,
#             "queue_size": queue_size,
#             "is_wifi": is_wifi_val,
#             "target": 1 if bool(target_val) else 0,
#         }
#         rows.append(row)       
#     if len(rows) < 20 or len({r["target"] for r in rows}) < 2:
#         return {
#             "trained": False, 
#             "samples": len(rows), 
#             "message": "Need at least 20 labelled observations containing both successful and failed syncs."
#         }   
#     df = pd.DataFrame(rows)  
#     # Initialize HistGradientBoostingClassifier with balanced class weights
#     model = HistGradientBoostingClassifier(random_state=42, class_weight="balanced")
#     model.fit(df[FEATURES], df["target"])
#     MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
#     joblib.dump(model, MODEL_PATH)
#     return {"trained": True, "samples": len(rows), "message": "HistGradientBoosting model trained and saved."}
# def recommend_sync(context: dict) -> dict:
#     queue_size = int(context.get("queue_size", context.get("QueueSize", 0)))
#     if queue_size <= 0:
#         return {
#             "strategy": "immediate", 
#             "should_sync": False, 
#             "reason": "No pending records.", 
#             "confidence": None
#         }
#     features = _features(context)
#     confidence = None
#     suitable = None
#     if MODEL_PATH.exists():
#         model = joblib.load(MODEL_PATH)
#         probabilities = model.predict_proba(features)[0]
#         if 1 in model.classes_:
#             positive_index = list(model.classes_).index(1)
#             confidence = float(probabilities[positive_index])
#             suitable = confidence >= 0.55
#         else:
#             confidence = 0.0
#             suitable = False
#     # Heuristic Rule Fallback if model doesn't exist yet
#     signal = context.get("signal_strength", context.get("SignalStrengthPercent"))
#     bandwidth = context.get("bandwidth_kbps", context.get("BandwidthKbps"))
#     latency = context.get("latency_ms", context.get("LatencyMs", context.get("LatencyM")))
#     battery = context.get("battery_percent", context.get("BatteryPercent"))
#     budget = context.get("data_budget_kb")
#     network = context.get("network_type", context.get("NetworkT"))
#     wifi = str(network).lower().replace("-", "") == "wifi" if network else False
#     if suitable is None:
#         suitable = (
#             (signal is None or float(signal) >= 35)
#             and (bandwidth is None or float(bandwidth) >= 128)
#             and (latency is None or float(latency) <= 1200)
#             and (battery is None or float(battery) >= 15)
#         )
#     # Safety Guardrails
#     if battery is not None and float(battery) < 10:
#         return {
#             "strategy": "delayed", 
#             "should_sync": False, 
#             "reason": "Battery is critically low; wait for charging or a better battery level.", 
#             "confidence": confidence
#         }
#     if not suitable:
#         return {
#             "strategy": "delayed", 
#             "should_sync": False, 
#             "reason": "Network conditions are not currently suitable; retry later.", 
#             "confidence": confidence
#         }
#     if budget is not None and float(budget) < 64 and not wifi:
#         return {
#             "strategy": "partial", 
#             "should_sync": True, 
#             "max_records": min(queue_size, 5), 
#             "reason": "Limited data budget; synchronize a small batch.", 
#             "confidence": confidence
#         }
#     if not wifi and queue_size > 50:
#         return {
#             "strategy": "partial", 
#             "should_sync": True, 
#             "max_records": 25, 
#             "reason": "Large queue on cellular data; send a bounded batch.", 
#             "confidence": confidence
#         }
#     return {
#         "strategy": "immediate", 
#         "should_sync": True, 
#         "max_records": queue_size, 
#         "reason": "Current conditions are suitable for synchronization.", 
#         "confidence": confidence
#     }