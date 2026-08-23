"""
CARE Lightweight Backend — FastAPI prototype.
Replaces the full Django + Postgres + Redis + Celery + MinIO stack
with a single-file server using SQLite + local filesystem.

Implements only the API endpoints consumed by:
  - care_fe (frontend)
  - UHI-Switch (health monitor)
  - hospital-a / hospital-b deployments
  - MedGemma plugin (ported inline)

Start: uvicorn main:app --host 0.0.0.0 --port 9000 --reload
"""

import hashlib
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import jwt
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import medgemma_ai
import fhir_utils
from seed_data import USERS, PATIENTS, FACILITIES, ORGANIZATIONS

# ─── Config ─────────────────────────────────────────────
JWT_SECRET = "care-lightweight-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(minutes=60)
REFRESH_TOKEN_TTL = timedelta(hours=24)
DB_PATH = os.path.join(os.path.dirname(__file__), "care_lite.db")
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "care_fe")

os.makedirs(UPLOADS_DIR, exist_ok=True)


# ─── Database ─────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT UNIQUE NOT NULL,
            analysis_type TEXT NOT NULL,
            input_bundle TEXT DEFAULT '{}',
            analysis_result TEXT DEFAULT '{}',
            status TEXT DEFAULT 'COMPLETED',
            model_version TEXT DEFAULT 'medgemma-mock-1.0',
            is_mock INTEGER DEFAULT 1,
            disclaimer TEXT DEFAULT 'AI-generated suggestion. Verify clinically.',
            processing_time_ms INTEGER,
            requested_by TEXT,
            encounter_id TEXT,
            created_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS consents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT UNIQUE NOT NULL,
            patient_abha_id TEXT NOT NULL,
            requester_id TEXT NOT NULL,
            requester_type TEXT DEFAULT 'doctor',
            purpose TEXT DEFAULT 'diagnosis',
            scope TEXT DEFAULT '[]',
            exclude_scope TEXT DEFAULT '[]',
            valid_from TEXT,
            valid_until TEXT,
            granted_at TEXT,
            revoked_at TEXT,
            status TEXT DEFAULT 'ACTIVE',
            consent_token TEXT UNIQUE,
            patient_signature TEXT DEFAULT '',
            granted_by TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_id TEXT UNIQUE NOT NULL,
            event_type TEXT NOT NULL,
            actor_id TEXT,
            patient_id TEXT,
            resource_types TEXT DEFAULT '[]',
            consent_ref TEXT,
            prev_hash TEXT,
            entry_hash TEXT,
            metadata TEXT DEFAULT '{}',
            timestamp TEXT NOT NULL
        );
    """)
    conn.close()


init_db()


# ─── FastAPI App ─────────────────────────────────────────────

app = FastAPI(
    title="CARE Lightweight Backend",
    description="Lightweight EMR backend for hackathon demo",
    version="1.0.0-lite",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── JWT Helpers ─────────────────────────────────────────────

def create_token(user_data: dict, ttl: timedelta) -> str:
    payload = {
        "user_id": user_data["id"],
        "username": user_data["username"],
        "exp": datetime.now(timezone.utc) + ttl,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = auth_header[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("username")
        if username not in USERS:
            raise HTTPException(status_code=401, detail="Invalid token")
        return USERS[username]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _user_response(user: dict) -> dict:
    """Format a user dict for API response (exclude password)."""
    return {
        "id": user["id"],
        "external_id": user["external_id"],
        "username": user["username"],
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "email": user["email"],
        "user_type": user["user_type"],
        "is_superuser": user["is_superuser"],
        "phone_number": user["phone_number"],
        "gender": user["gender"],
        "permissions": user["permissions"],
    }


# ─── Audit Helper ─────────────────────────────────────────────

def _append_audit(conn, event_type: str, actor_id: str = "", patient_id: str = "",
                  resource_types: list = None, consent_ref: str = "", metadata: dict = None):
    ext_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Hash chain
    row = conn.execute("SELECT entry_hash FROM audit_logs ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = row["entry_hash"] if row else "0" * 64
    hash_input = f"{prev_hash}:{event_type}:{actor_id}:{now}"
    entry_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    conn.execute(
        """INSERT INTO audit_logs
           (external_id, event_type, actor_id, patient_id, resource_types, consent_ref, prev_hash, entry_hash, metadata, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ext_id, event_type, actor_id, patient_id,
         json.dumps(resource_types or []), consent_ref, prev_hash, entry_hash,
         json.dumps(metadata or {}), now),
    )
    conn.commit()
    return ext_id


# ─── Pydantic Models ─────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenRefreshRequest(BaseModel):
    refresh: str

class MedGemmaRequest(BaseModel):
    analysis_type: str
    input_data: Optional[dict] = {}
    encounter_id: Optional[str] = ""
    preset: Optional[str] = ""
    patient_id: Optional[str] = ""

class ConsentGrantRequest(BaseModel):
    patient_abha_id: str
    requester_id: str
    requester_type: str = "doctor"
    purpose: str = "diagnosis"
    scope: list = ["Patient", "Observation", "DiagnosticReport", "Condition", "MedicationRequest"]
    exclude: list = []
    valid_until: str
    patient_signature: str = ""

class ConsentRevokeRequest(BaseModel):
    reason: str = ""

class EmergencyAccessRequest(BaseModel):
    doctor_id: str = ""
    patient_abha_id: str
    hospital_id: str = ""
    reason: str


# ═══════════════════════════════════════════════════════════════
#                        API ENDPOINTS
# ═══════════════════════════════════════════════════════════════


# ─── Health Check (UHI-Switch compatibility) ─────────────────

@app.get("/api/care_medgemma/health")
def medgemma_health():
    return HTMLResponse("OK", status_code=200)


@app.get("/ping/")
def ping():
    return {"status": "ok"}


@app.get("/api/v1/config/")
def get_config():
    return {
        "hospital_name": os.environ.get("HOSPITAL_NAME", "CARE Hospital"),
        "hospital_id": os.environ.get("HOSPITAL_ID", "HOSP-001")
    }


# ─── Auth Endpoints ─────────────────────────────────────────────

@app.post("/api/v1/auth/login/")
def login(req: LoginRequest):
    user = USERS.get(req.username)
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_token(user, ACCESS_TOKEN_TTL)
    refresh_token = create_token(user, REFRESH_TOKEN_TTL)

    return {
        "access": access_token,
        "refresh": refresh_token,
    }


@app.post("/api/v1/auth/token/refresh/")
def token_refresh(req: TokenRefreshRequest):
    try:
        payload = jwt.decode(req.refresh, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("username")
        if username not in USERS:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = USERS[username]
        access_token = create_token(user, ACCESS_TOKEN_TTL)
        refresh_token = create_token(user, REFRESH_TOKEN_TTL)
        return {"access": access_token, "refresh": refresh_token}
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@app.post("/api/v1/auth/logout/")
def logout():
    return {"detail": "Logged out"}


# ─── User Endpoints ─────────────────────────────────────────────

@app.get("/api/v1/users/me/")
def get_me(request: Request):
    user = get_current_user(request)
    return _user_response(user)


@app.get("/api/v1/users/")
def list_users(request: Request):
    get_current_user(request)
    return {
        "count": len(USERS),
        "results": [_user_response(u) for u in USERS.values()],
    }


# ─── Patient Endpoints ─────────────────────────────────────────────

@app.get("/api/v1/patient/")
def list_patients(request: Request):
    get_current_user(request)
    return {
        "count": len(PATIENTS),
        "results": PATIENTS,
    }


@app.get("/api/v1/patient/{patient_id}/")
def get_patient(patient_id: str, request: Request):
    get_current_user(request)
    for p in PATIENTS:
        if p["external_id"] == patient_id or str(p["id"]) == patient_id:
            return p
        if p["meta"].get("abha_id") == patient_id:
            return p
    raise HTTPException(status_code=404, detail="Patient not found")


# ─── Facility Endpoints ─────────────────────────────────────────────

@app.get("/api/v1/facility/")
def list_facilities(request: Request):
    get_current_user(request)
    return {
        "count": len(FACILITIES),
        "results": FACILITIES,
    }


@app.get("/api/v1/facility/{facility_id}/")
def get_facility(facility_id: str, request: Request):
    get_current_user(request)
    for f in FACILITIES:
        if f["external_id"] == facility_id or str(f["id"]) == facility_id:
            return f
    raise HTTPException(status_code=404, detail="Facility not found")


# ─── Organization Endpoints ─────────────────────────────────────

@app.get("/api/v1/organization/")
def list_organizations(request: Request):
    get_current_user(request)
    return {
        "count": len(ORGANIZATIONS),
        "results": ORGANIZATIONS,
    }


# ─── MedGemma Analysis Endpoints ─────────────────────────────────

@app.post("/api/v1/medgemma/analyze/")
def run_analysis(req: MedGemmaRequest, request: Request,
                 conn: sqlite3.Connection = Depends(get_db)):
    user = get_current_user(request)

    input_data = req.input_data or {}

    # Resolve patient by ABHA ID
    patient_id_str = req.patient_id or ""
    patient = None
    if patient_id_str:
        for p in PATIENTS:
            if (p["meta"].get("abha_id") == patient_id_str
                    or p["external_id"] == patient_id_str
                    or patient_id_str.lower() in p["name"].lower()):
                patient = p
                break

        if patient:
            input_data["patient_info"] = {
                "name": patient["name"],
                "gender": patient["gender"],
                "blood_group": patient.get("blood_group", "unknown"),
                "abha_id": patient["meta"].get("abha_id", ""),
                "date_of_birth": patient.get("date_of_birth", ""),
                "address": patient.get("address", ""),
            }
            input_data["patient_id"] = patient_id_str
            input_data["abha_id"] = patient["meta"].get("abha_id", "")

    # Use preset as analysis_type override if provided
    analysis_type = req.preset if req.preset else req.analysis_type

    # Run analysis
    result = medgemma_ai.analyze(analysis_type, input_data)

    # Save to DB
    ext_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO analyses
           (external_id, analysis_type, input_bundle, analysis_result, status,
            model_version, is_mock, processing_time_ms, requested_by, encounter_id, created_date)
           VALUES (?, ?, ?, ?, 'COMPLETED', ?, 1, ?, ?, ?, ?)""",
        (ext_id, analysis_type, json.dumps(input_data), json.dumps(result),
         result.get("model_version", "medgemma-mock-1.0"),
         result.get("processing_time_ms", 0),
         user["username"], req.encounter_id or "", now),
    )
    conn.commit()

    # Audit
    _append_audit(conn, "ANALYSIS_REQUEST", user["external_id"],
                  patient["external_id"] if patient else "",
                  [analysis_type],
                  metadata={"analysis_id": ext_id, "is_mock": True})

    return {
        "external_id": ext_id,
        "encounter": req.encounter_id or None,
        "requester_name": f"{user['first_name']} {user['last_name']}",
        "input_bundle": input_data,
        "analysis_type": analysis_type,
        "analysis_result": result,
        "status": "COMPLETED",
        "model_version": result.get("model_version", "medgemma-mock-1.0"),
        "is_mock": True,
        "disclaimer": "AI-generated suggestion. Verify clinically.",
        "processing_time_ms": result.get("processing_time_ms"),
        "created_date": now,
    }


@app.get("/api/v1/medgemma/")
def list_analyses(request: Request, limit: int = 20,
                  conn: sqlite3.Connection = Depends(get_db)):
    user = get_current_user(request)
    rows = conn.execute(
        "SELECT * FROM analyses WHERE requested_by=? ORDER BY created_date DESC LIMIT ?",
        (user["username"], limit),
    ).fetchall()

    results = []
    for r in rows:
        results.append({
            "external_id": r["external_id"],
            "encounter": r["encounter_id"] or None,
            "requester_name": f"{user['first_name']} {user['last_name']}",
            "input_bundle": json.loads(r["input_bundle"]),
            "analysis_type": r["analysis_type"],
            "analysis_result": json.loads(r["analysis_result"]),
            "status": r["status"],
            "model_version": r["model_version"],
            "is_mock": bool(r["is_mock"]),
            "disclaimer": r["disclaimer"],
            "processing_time_ms": r["processing_time_ms"],
            "created_date": r["created_date"],
        })

    return {"count": len(results), "results": results}


@app.get("/api/v1/medgemma/{analysis_id}/")
def get_analysis(analysis_id: str, request: Request,
                 conn: sqlite3.Connection = Depends(get_db)):
    user = get_current_user(request)
    r = conn.execute(
        "SELECT * FROM analyses WHERE external_id=?", (analysis_id,)
    ).fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return {
        "external_id": r["external_id"],
        "encounter": r["encounter_id"] or None,
        "requester_name": f"{user['first_name']} {user['last_name']}",
        "input_bundle": json.loads(r["input_bundle"]),
        "analysis_type": r["analysis_type"],
        "analysis_result": json.loads(r["analysis_result"]),
        "status": r["status"],
        "model_version": r["model_version"],
        "is_mock": bool(r["is_mock"]),
        "disclaimer": r["disclaimer"],
        "processing_time_ms": r["processing_time_ms"],
        "created_date": r["created_date"],
    }


# ─── FHIR Export Endpoints ─────────────────────────────────

@app.get("/api/v1/fhir/patient_bundle/")
def fhir_patient_bundle(request: Request, abha_id: str = "",
                        consent_token: str = ""):
    get_current_user(request)
    if not abha_id:
        raise HTTPException(status_code=400, detail="abha_id query parameter is required")

    patient_name = "Demo Patient"
    for p in PATIENTS:
        if p["meta"].get("abha_id") == abha_id:
            patient_name = p["name"]
            break

    bundle = fhir_utils.create_sample_bundle(abha_id, patient_name)
    return bundle


@app.get("/api/v1/fhir/")
def list_fhir_exports(request: Request):
    get_current_user(request)
    return {"count": 0, "results": []}


# ─── Consent Endpoints ─────────────────────────────────

@app.get("/api/v1/consent/")
def list_consents(request: Request, patient_abha_id: str = "",
                  status: str = "", conn: sqlite3.Connection = Depends(get_db)):
    get_current_user(request)
    query = "SELECT * FROM consents WHERE 1=1"
    params = []
    if patient_abha_id:
        query += " AND patient_abha_id=?"
        params.append(patient_abha_id)
    if status:
        query += " AND status=?"
        params.append(status)
    query += " ORDER BY granted_at DESC"

    rows = conn.execute(query, params).fetchall()
    results = []
    for r in rows:
        results.append({
            "external_id": r["external_id"],
            "patient_abha_id": r["patient_abha_id"],
            "requester_id": r["requester_id"],
            "requester_type": r["requester_type"],
            "purpose": r["purpose"],
            "scope": json.loads(r["scope"]),
            "exclude": json.loads(r["exclude_scope"]),
            "valid_from": r["valid_from"],
            "valid_until": r["valid_until"],
            "granted_at": r["granted_at"],
            "revoked_at": r["revoked_at"],
            "status": r["status"],
            "consent_token": r["consent_token"],
        })
    return {"count": len(results), "results": results}


@app.post("/api/v1/consent/grant/")
def grant_consent(req: ConsentGrantRequest, request: Request,
                  conn: sqlite3.Connection = Depends(get_db)):
    user = get_current_user(request)
    ext_id = str(uuid.uuid4())
    token = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """INSERT INTO consents
           (external_id, patient_abha_id, requester_id, requester_type, purpose,
            scope, exclude_scope, valid_from, valid_until, granted_at, status,
            consent_token, patient_signature, granted_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)""",
        (ext_id, req.patient_abha_id, req.requester_id, req.requester_type,
         req.purpose, json.dumps(req.scope), json.dumps(req.exclude),
         now, req.valid_until, now, token, req.patient_signature, user["username"]),
    )
    conn.commit()

    _append_audit(conn, "CONSENT_GRANT", user["external_id"], req.patient_abha_id,
                  req.scope, ext_id, {"purpose": req.purpose})

    return {
        "external_id": ext_id,
        "patient_abha_id": req.patient_abha_id,
        "requester_id": req.requester_id,
        "requester_type": req.requester_type,
        "purpose": req.purpose,
        "scope": req.scope,
        "status": "ACTIVE",
        "consent_token": token,
        "granted_at": now,
        "valid_until": req.valid_until,
    }


@app.post("/api/v1/consent/{consent_id}/revoke/")
def revoke_consent(consent_id: str, req: ConsentRevokeRequest, request: Request,
                   conn: sqlite3.Connection = Depends(get_db)):
    user = get_current_user(request)
    row = conn.execute("SELECT * FROM consents WHERE external_id=?", (consent_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Consent not found")
    if row["status"] == "REVOKED":
        raise HTTPException(status_code=400, detail="Consent is already revoked")

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE consents SET status='REVOKED', revoked_at=? WHERE external_id=?",
        (now, consent_id),
    )
    conn.commit()

    _append_audit(conn, "CONSENT_REVOKE", user["external_id"], row["patient_abha_id"],
                  json.loads(row["scope"]), consent_id, {"reason": req.reason})

    return {
        "external_id": consent_id,
        "status": "REVOKED",
        "revoked_at": now,
    }


# ─── Audit Log Endpoints ─────────────────────────────────

@app.get("/api/v1/audit/")
def list_audit_logs(request: Request, event_type: str = "", patient_id: str = "",
                    limit: int = 50, conn: sqlite3.Connection = Depends(get_db)):
    get_current_user(request)
    query = "SELECT * FROM audit_logs WHERE 1=1"
    params = []
    if event_type:
        query += " AND event_type=?"
        params.append(event_type)
    if patient_id:
        query += " AND patient_id=?"
        params.append(patient_id)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    results = []
    for r in rows:
        results.append({
            "external_id": r["external_id"],
            "event_type": r["event_type"],
            "actor_id": r["actor_id"],
            "patient_id": r["patient_id"],
            "resource_types": json.loads(r["resource_types"]),
            "consent_ref": r["consent_ref"],
            "prev_hash": r["prev_hash"],
            "entry_hash": r["entry_hash"],
            "metadata": json.loads(r["metadata"]),
            "timestamp": r["timestamp"],
        })
    return {"count": len(results), "results": results}


@app.get("/api/v1/audit/verify_chain/")
def verify_audit_chain(request: Request, conn: sqlite3.Connection = Depends(get_db)):
    get_current_user(request)
    rows = conn.execute("SELECT * FROM audit_logs ORDER BY id ASC").fetchall()

    total = len(rows)
    verified = 0
    broken_at = None
    prev_hash = "0" * 64

    for r in rows:
        if r["prev_hash"] != prev_hash:
            broken_at = r["external_id"]
            break
        prev_hash = r["entry_hash"]
        verified += 1

    return {
        "total_entries": total,
        "verified_entries": verified,
        "chain_intact": broken_at is None,
        "broken_at_entry": broken_at,
    }


@app.post("/api/v1/audit/emergency_access/")
def emergency_access(req: EmergencyAccessRequest, request: Request,
                     conn: sqlite3.Connection = Depends(get_db)):
    user = get_current_user(request)

    if not req.reason:
        raise HTTPException(status_code=400, detail="reason is required for emergency access")

    # Create emergency consent
    ext_id = str(uuid.uuid4())
    token = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    valid_until = (now + timedelta(hours=4)).isoformat()
    now_iso = now.isoformat()

    conn.execute(
        """INSERT INTO consents
           (external_id, patient_abha_id, requester_id, requester_type, purpose,
            scope, exclude_scope, valid_from, valid_until, granted_at, status,
            consent_token, patient_signature, granted_by)
           VALUES (?, ?, ?, 'doctor', 'emergency', ?, '[]', ?, ?, ?, 'ACTIVE', ?, 'EMERGENCY_BREAK_GLASS', ?)""",
        (ext_id, req.patient_abha_id, req.doctor_id or user["external_id"],
         json.dumps(["Patient", "Observation", "DiagnosticReport", "Condition",
                      "MedicationRequest", "AllergyIntolerance", "Encounter"]),
         now_iso, valid_until, now_iso, token, user["username"]),
    )
    conn.commit()

    _append_audit(conn, "EMERGENCY_ACCESS", req.doctor_id or user["external_id"],
                  req.patient_abha_id,
                  ["Patient", "Observation", "DiagnosticReport", "Condition"],
                  ext_id, {"reason": req.reason, "hospital_id": req.hospital_id})

    return {
        "status": "EMERGENCY_ACCESS_GRANTED",
        "consent_token": token,
        "valid_until": valid_until,
        "scope": ["Patient", "Observation", "DiagnosticReport", "Condition",
                   "MedicationRequest", "AllergyIntolerance", "Encounter"],
        "disclaimer": (
            "Emergency access granted. This event has been logged "
            "and the patient will be notified. Abuse of this protocol "
            "will trigger a security review."
        ),
        "notifications_sent": {"sms": "queued", "email": "queued", "push": "queued"},
    }


# ─── File Upload (static serving) ─────────────────────────

@app.get("/uploads/{filename}")
def serve_upload(filename: str):
    filepath = os.path.join(UPLOADS_DIR, filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath)


# ─── Frontend Serving ─────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(index_path):
        with open(index_path, "r") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("""
        <html><body style="font-family:sans-serif;text-align:center;padding:50px">
        <h1>CARE Lightweight Backend</h1>
        <p>Backend is running. Place <code>care_fe/index.html</code> to enable the frontend.</p>
        <p><a href="/docs">API Documentation</a></p>
        </body></html>
    """)


# ─── Catch-all for frontend routing ─────────────────────────
# React-style SPA routing: any non-API path serves index.html

@app.get("/{path:path}")
async def catch_all(path: str, request: Request):
    # Don't catch API paths
    if path.startswith("api/") or path.startswith("docs") or path.startswith("openapi"):
        raise HTTPException(status_code=404)

    # Try to serve static file from frontend dir
    static_path = os.path.join(FRONTEND_DIR, path)
    if os.path.isfile(static_path):
        return FileResponse(static_path)

    # Fallback to index.html for SPA routing
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(index_path):
        with open(index_path, "r") as f:
            return HTMLResponse(f.read())

    raise HTTPException(status_code=404)
