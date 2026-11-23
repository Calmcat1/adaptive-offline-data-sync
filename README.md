Adaptive Offline Data Synchronization Backend
FastAPI + MongoDB backend for ADAS (Adaptive Offline Data Synchronization Framework), designed for intermittent network environments. It pairs an offline-first Android client with a deterministic rule-based decision engine (adaptive_decision_engine) and a static comparison engine (baseline_engine) for empirical benchmarking.
Features
JWT Authentication: User registration, login, and bearer token verification (/api/v1/auth/*).
Offline-First Record Ingestion: Authenticated field-record storage and retrieval with idempotent submissions via client-generated UUIDs (client_record_id).
Conflict Detection & Resolution: Version-aware duplicate/divergence checks with explicit conflict resolution (server_wins / client_wins).
Deterministic Adaptive Decision Engine (adaptive_decision_engine): Evaluates device and network telemetry (signal_strength, bandwidth_kbps, latency_ms, battery_percent, data_budget_kb) to recommend immediate, partial, or delayed synchronization policies.
Static Baseline Engine (baseline_engine): Non-adaptive fixed-policy comparator sharing the same decision interface for controlled A/B benchmarking.
Bounded Batch Execution & Observability: Enforces batch limits during /sync/execute and logs attempt history, network observations, and aggregated statistics to MongoDB.
Architecture
Android Client (Kotlin, Jetpack Compose, Room/SQLite, WorkManager, Retrofit)
       │
       ▼  REST / JSON (JWT Authenticated)
FastAPI Gateway (Python, Uvicorn)
       ├──► adaptive_decision_engine  (Deterministic telemetry scoring & policy selection)
       ├──► baseline_engine           (Static fixed-schedule baseline for benchmarking)
       └──► MongoDB                   (records, sync_history, network_observations)
Synchronization Workflow
Offline Capture: The Android app saves field records locally in Room (SQLite) with a stable client_record_id UUID while disconnected.
Policy Evaluation: When queued records exist and connectivity is detected, WorkManager sends current device/network telemetry to POST /api/v1/sync/decision.
Bounded Execution: Based on the returned policy (immediate, partial, or delayed), the client either defers synchronization or submits a bounded batch to POST /api/v1/sync/execute.
Telemetry Logging: The backend persists accepted records, flags any version conflicts, and logs execution outcomes to sync_history for evaluation via /api/v1/sync/stats.
Requirements
Python 3.11+
MongoDB Community Server (local) or MongoDB Atlas URI
pip
Local Setup & Execution
Create and activate a virtual environment:
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
Install dependencies:
pip install -r requirements.txt
Configure environment variables: Copy .env.example to .env and set your database connection string and JWT secret:
```env
MONGODB_URI=mongodb://localhost:27017
DATABASE_NAME=adas_sync
JWT_SECRET_KEY=replace-with-a-strong-random-secret
```
Start the FastAPI server:
uvicorn app.main:app --reload
Verify the API: Open http://127.0.0.1:8000/docs in your browser to explore the interactive Swagger UI.
Authentication Flow
Create an account via POST /api/v1/auth/register.
Obtain an access token via POST /api/v1/auth/login using form fields:
username: registered email address
password: account password
Pass the returned access_token in the Authorization: Bearer <token> header (or via Swagger's Authorize button).
API Endpoints
Method
Endpoint
Purpose
GET
/health
Service health check
POST
/api/v1/auth/register
Register a new user account
POST
/api/v1/auth/login
Authenticate and obtain a JWT
GET
/api/v1/auth/me
Retrieve current authenticated user profile
POST
/api/v1/records
Store a single field record (idempotent)
GET
/api/v1/records
List all records belonging to the user
GET
/api/v1/records/{record_id}
Fetch a specific record by ID
POST
/api/v1/records/{record_id}/resolve
Resolve a record conflict (server_wins / client_wins)
POST
/api/v1/sync/decision
Evaluate telemetry and return sync policy (immediate, partial, delayed)
POST
/api/v1/sync/execute
Submit a bounded batch of queued records
GET
/api/v1/sync/history
Retrieve chronological synchronization attempt logs
GET
/api/v1/sync/stats
Retrieve aggregated sync metrics (completion rate, latency, volume)
POST
/api/v1/network/observations
Log a standalone network condition snapshot
GET
/api/v1/network/observations
Retrieve logged network observations

Example Sync Request (POST /api/v1/sync/decision & /execute)
{
  "records": [
    {
      "client_record_id": "550e8400-e29b-41d4-a716-446655440000",
      "data": {
        "site": "Station A",
        "observation": "Telemetry sample recorded",
        "notes": "Captured during intermittent cellular coverage"
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
Decision Engines & Evaluation Design
adaptive_decision_engine: Uses deterministic rule-based thresholds and weighted telemetry scoring to balance upload throughput against connection stability and battery preservation. It avoids runtime machine learning overhead, cold-start training requirements, and unpredictable inference latency on mobile links.
baseline_engine: Implements a static, non-adaptive policy that attempts immediate full-queue synchronization whenever network connectivity is available, ignoring signal quality, latency spikes, or low battery states.
Comparative Benchmarking: Both engines share a unified input/output schema, allowing identical intermittent network traces to be replayed and compared via /api/v1/sync/history and /api/v1/sync/stats.
Prototype Scope & Limitations
Idempotency & Conflict Safety: Android clients must assign a stable UUID to client_record_id. Retrying an identical payload with the same ID is safely acknowledged; submitting modified data under an existing ID raises a conflict requiring explicit resolution.
Transport & Deployment: Built as an academic research and systems prototype. Before production deployment, enforce HTTPS/TLS termination, add rate limiting, implement role-based access control, and enable multi-document database transactions.
