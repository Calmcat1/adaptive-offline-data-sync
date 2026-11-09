# Adaptive Data Synchronization Backend

FastAPI + MongoDB + scikit-learn backend for the IS Project II.

## Features
- JWT-based registration and login
- Authenticated field-record storage and retrieval
- Idempotent record submissions using `client_record_id`
- Adaptive synchronization recommendation: `immediate`, `partial`, or `delayed`
- Sync execution endpoint with bounded batches
- Conflict detection and explicit resolution (`server_wins` / `client_wins`)
- Synchronization history and summary statistics
- Network-condition observations
- Random Forest training from recorded outcomes, with rule-based fallback until sufficient training data exists
- Ensemble ML Pipeline: Histogram-based Gradient Boosting (HistGradientBoostingClassifier) / Random Forest training from recorded outcomes with 5-Fold Stratified Cross-Validation, dynamic threshold optimization, and rule-based fallback

## Architecture
Android (Kotlin, Jetpack Compose, Room/SQLite, WorkManager) -> FastAPI REST API -> adaptive decision engine (Python/Pandas/scikit-learn) -> MongoDB.

The Android app should continue saving field records locally while offline. It should call `/sync/decision` when it has queued records, then `/sync/execute` when the returned decision says to synchronize. The server cannot send data while the device is disconnected; WorkManager should retry when connectivity returns.

## Requirements
- Python 3.11+
- MongoDB Community Server or a MongoDB Atlas database
- pip

## Run locally
1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # macOS/Linux:
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and set `MONGODB_URI` and a strong `JWT_SECRET_KEY`.
4. Start MongoDB locally, or use your MongoDB Atlas URI.
5. Start the API:
   ```bash
   uvicorn app.main:app --reload
   ```
6. Open `http://127.0.0.1:8000/docs` to test the API.

## Authentication
Register at `POST /api/v1/auth/register`, then log in at `POST /api/v1/auth/login` using form fields:
- `username`: the account email
- `password`: account password

Copy the returned `access_token` into Swagger's **Authorize** dialog as a bearer token.

## Main endpoints
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Obtain JWT |
| GET | `/api/v1/auth/me` | Current user |
| POST | `/api/v1/records` | Store one field record |
| GET | `/api/v1/records` | List own records |
| GET | `/api/v1/records/{record_id}` | Fetch one record |
| POST | `/api/v1/records/{record_id}/resolve` | Resolve a conflict |
| POST | `/api/v1/sync/decision` | Recommend sync strategy |
| POST | `/api/v1/sync/execute` | Submit a queued batch |
| GET | `/api/v1/sync/history` | Sync attempt history |
| GET | `/api/v1/sync/stats` | Sync metrics |
| POST | `/api/v1/sync/train-model` | Train Random Forest from collected outcomes |
| POST | `/api/v1/network/observations` | Save a network observation |
| GET | `/api/v1/network/observations` | Read observations |

## Example sync request
```json
{
  "records": [
    {
      "client_record_id": "field-record-0001",
      "data": {
        "site": "Farm A",
        "observation": "Sample collected",
        "notes": "Captured while offline"
      },
      "version": 1
    }
  ],
  "network_type": "cellular",
  "signal_strength": 72,
  "bandwidth_kbps": 850,
  "latency_ms": 180,
  "battery_percent": 68,
  "data_budget_kb": 500
}
```

## Model behaviour and evaluation
The machine learning model is not assumed to be trained in advance. Initially, the backend uses a transparent rule-based fallback. As the system records real outcomes, call /api/v1/sync/train-model; training requires at least 20 labelled observations containing both successful and failed outcomes.

The pipeline uses HistGradientBoostingClassifier with in-memory payload caching, interaction feature extraction (bandwidth_per_latency, signal_battery_prod), field key normalization across client variants, and Stratified K-Fold Cross-Validation. Dynamic thresholding optimizes probability decision boundaries based on precision-recall metrics. Evaluate on held-out data before reporting final model accuracy, precision, recall, or F1 scores in project reports.

## Important prototype notes
Configure HTTPS and a strong secret before deployment.
Restrict model-training to an administrator before production use.
Add project-specific validation to the generic data field.
For production-grade conflict handling, use explicit record versions / ETags and transactions where supported.
sync/execute is a prototype API: it simulates the server-side decision and batch acceptance, not a guarantee that a mobile device is continuously reachable.
Use a stable UUID for each client_record_id on Android. Retrying the same ID and same payload is safe; changed payloads under the same ID are treated as conflicts.
For real-world deployments, add automated tests, rate limiting, audit logging, database backups, and stricter role-based authorization.
