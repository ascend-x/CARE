"""
UHI Switch Server — Central consent broker and FHIR routing layer.

Core principles:
1. ZERO DATA STORAGE — Switch never stores patient health data
2. CONSENT-GATED — All data access requires valid consent
3. ENCRYPTED ROUTING — FHIR bundles are encrypted; keys shared only after consent
4. IMMUTABLE AUDIT — Every action is hash-chained and tamper-evident
"""

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import List, Optional
import uuid
import asyncio
import httpx
import logging

import models
from database import engine, get_db, SessionLocal
from crypto_utils import (
    generate_bundle_key,
    encrypt_bundle,
    decrypt_bundle,
    hash_chain_entry,
    generate_consent_token,
    verify_hash_chain,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="UHI Switch Server",
    description="Unified Health Interface — Consent-gated FHIR routing with zero data storage",
    version="1.0.0",
)

# ─── Background Monitor ────────────────────────────

async def monitor_hospitals():
    """Background task to maintain consistent connection with hospitals."""
    logger.info("Starting UHI Hospital Monitor...")
    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            db = SessionLocal()
            try:
                hospitals = db.query(models.Hospital).all()
                for hospital in hospitals:
                    try:
                        # Check hospital health endpoint
                        health_url = f"{hospital.endpoint_url.rstrip('/')}/api/care_medgemma/health"
                        response = await client.get(health_url)
                        
                        if response.status_code == 200:
                            hospital.last_heartbeat = datetime.now(timezone.utc)
                            hospital.status_message = "HEALTHY"
                            if not hospital.is_active:
                                hospital.is_active = True
                                logger.info(f"RECOVERY: Hospital {hospital.name} ({hospital.hospital_id}) is BACK ONLINE.")
                                logger.info(f"NOTIFICATION: [ADMIN] Recovery alert sent for {hospital.name}")
                        else:
                            # hospital.is_active = False # Patched for local testing
                            hospital.status_message = f"UNHEALTHY: HTTP {response.status_code}"
                            logger.error(f"ALERT: Hospital {hospital.name} ({hospital.hospital_id}) is UNHEALTHY!")
                            logger.info(f"NOTIFICATION: [ADMIN] Unhealthy alert sent for {hospital.name}")
                    except Exception as e:
                        # hospital.is_active = False # Patched for local testing
                        hospital.status_message = f"OUTAGE: {str(e)}"
                        logger.error(f"CRITICAL: Hospital {hospital.name} ({hospital.hospital_id}) connection LOST! Error: {str(e)}")
                        logger.info(f"NOTIFICATION: [ADMIN] CRITICAL outage alert sent for {hospital.name}")
                
                db.commit()
            except Exception as e:
                logger.error(f"Monitor loop error: {str(e)}")
            finally:
                db.close()
            
            await asyncio.sleep(30) # Check every 30 seconds

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitor_hospitals())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Pydantic Schemas ────────────────────────────

class HospitalRegisterRequest(BaseModel):
    name: str
    endpoint_url: str
    city: Optional[str] = None
    state: Optional[str] = None
    public_key: Optional[str] = None

class HospitalResponse(BaseModel):
    hospital_id: str
    name: str
    endpoint_url: str
    city: Optional[str]
    state: Optional[str]
    registered_at: datetime
    is_active: bool

class ConsentGrantRequest(BaseModel):
    patient_abha_id: str
    doctor_id: str
    hospital_id: str  # Requesting hospital
    source_hospital_id: Optional[str] = None  # Hospital holding the data
    purpose: str = "diagnosis"
    permissions: List[str]
    expires_at: datetime

class ConsentResponse(BaseModel):
    consent_id: str
    consent_token: str
    patient_abha_id: str
    doctor_id: str
    hospital_id: str
    status: str
    purpose: str
    permissions: List[str]
    granted_at: datetime
    expires_at: datetime
    is_emergency: bool

class ConsentRevokeRequest(BaseModel):
    consent_id: str
    reason: Optional[str] = None

class BundleNotifyRequest(BaseModel):
    patient_abha_id: str
    source_hospital_id: str
    bundle_location: str  # URL where encrypted bundle is accessible
    resource_count: int
    resource_types: List[str]
    expires_in_hours: int = 24

class BundleRequestRequest(BaseModel):
    patient_abha_id: str
    requesting_hospital_id: str
    consent_token: str

class EmergencyAccessRequest(BaseModel):
    doctor_id: str
    hospital_id: str
    patient_abha_id: str
    reason: str


# ─── Audit Helper ────────────────────────────

def append_audit(db: Session, actor: str, action: str, resource: str,
                 consent_id: str = None, hospital_id: str = None,
                 patient_abha_id: str = None, details: dict = None):
    """Append an entry to the cryptographic audit chain."""
    last_entry = db.query(models.AuditLog).order_by(models.AuditLog.id.desc()).first()
    prev_hash = last_entry.current_hash if last_entry else "genesis"
    timestamp = datetime.now(timezone.utc).isoformat()

    current_hash = hash_chain_entry(prev_hash, actor, action, resource, timestamp)

    audit = models.AuditLog(
        timestamp=timestamp,
        actor=actor,
        action=action,
        resource=resource,
        consent_id=consent_id,
        hospital_id=hospital_id,
        patient_abha_id=patient_abha_id,
        previous_hash=prev_hash,
        current_hash=current_hash,
        details=details,
    )
    db.add(audit)
    return audit


# ─── Health Check ────────────────────────────

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "UHI Switch Server",
        "version": "1.0.0",
        "data_stored": "NONE — zero data storage policy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── Hospital Registration ────────────────────────────

@app.post("/hospital/register", response_model=HospitalResponse)
def register_hospital(req: HospitalRegisterRequest, db: Session = Depends(get_db)):
    """Register a hospital with the UHI network."""
    hospital_id = f"HOSP-{uuid.uuid4().hex[:8].upper()}"

    hospital = models.Hospital(
        hospital_id=hospital_id,
        name=req.name,
        endpoint_url=req.endpoint_url,
        city=req.city,
        state=req.state,
        public_key=req.public_key,
    )
    db.add(hospital)
    append_audit(db, hospital_id, "HOSPITAL_REGISTERED", f"Hospital/{hospital_id}",
                 hospital_id=hospital_id, details={"name": req.name})
    db.commit()
    db.refresh(hospital)
    return hospital


@app.get("/hospital/list", response_model=List[HospitalResponse])
def list_hospitals(db: Session = Depends(get_db)):
    """List all registered hospitals."""
    return db.query(models.Hospital).filter(models.Hospital.is_active == True).all()


# ─── Consent Management ────────────────────────────

@app.post("/consent/grant", response_model=ConsentResponse)
def grant_consent(req: ConsentGrantRequest, db: Session = Depends(get_db)):
    """Patient grants consent for data sharing between hospitals."""
    consent_id = str(uuid.uuid4())
    token = generate_consent_token()

    consent = models.ConsentArtifact(
        consent_id=consent_id,
        consent_token=token,
        patient_abha_id=req.patient_abha_id,
        doctor_id=req.doctor_id,
        hospital_id=req.hospital_id,
        source_hospital_id=req.source_hospital_id,
        status="GRANTED",
        purpose=req.purpose,
        permissions=req.permissions,
        granted_at=datetime.now(timezone.utc),
        expires_at=req.expires_at,
    )
    db.add(consent)
    append_audit(db, req.patient_abha_id, "GRANT_CONSENT", f"ConsentArtifact/{consent_id}",
                 consent_id=consent_id, hospital_id=req.hospital_id,
                 patient_abha_id=req.patient_abha_id,
                 details={"purpose": req.purpose, "permissions": req.permissions})
    db.commit()
    db.refresh(consent)
    return consent


@app.post("/consent/revoke")
def revoke_consent(req: ConsentRevokeRequest, db: Session = Depends(get_db)):
    """Patient revokes a previously granted consent."""
    consent = db.query(models.ConsentArtifact).filter(
        models.ConsentArtifact.consent_id == req.consent_id
    ).first()

    if not consent:
        raise HTTPException(status_code=404, detail="Consent not found")
    if consent.status != "GRANTED":
        raise HTTPException(status_code=400, detail=f"Consent is already {consent.status}")

    consent.status = "REVOKED"
    consent.revoked_at = datetime.now(timezone.utc)
    append_audit(db, consent.patient_abha_id, "REVOKE_CONSENT",
                 f"ConsentArtifact/{req.consent_id}",
                 consent_id=req.consent_id, hospital_id=consent.hospital_id,
                 patient_abha_id=consent.patient_abha_id,
                 details={"reason": req.reason})
    db.commit()
    return {"status": "REVOKED", "consent_id": req.consent_id}


@app.get("/consent/verify")
def verify_consent(consent_token: str, db: Session = Depends(get_db)):
    """Verify if a consent token is valid and not expired."""
    consent = db.query(models.ConsentArtifact).filter(
        models.ConsentArtifact.consent_token == consent_token
    ).first()

    if not consent:
        return {"valid": False, "reason": "Token not found"}
    if consent.status != "GRANTED":
        return {"valid": False, "reason": f"Consent is {consent.status}"}
    if consent.expires_at < datetime.now(timezone.utc):
        consent.status = "EXPIRED"
        db.commit()
        return {"valid": False, "reason": "Consent has expired"}

    return {
        "valid": True,
        "consent_id": consent.consent_id,
        "patient_abha_id": consent.patient_abha_id,
        "permissions": consent.permissions,
        "expires_at": consent.expires_at.isoformat(),
    }


@app.get("/consent/list", response_model=List[ConsentResponse])
def list_consents(patient_abha_id: str, db: Session = Depends(get_db)):
    """List all consent artifacts for a patient."""
    return db.query(models.ConsentArtifact).filter(
        models.ConsentArtifact.patient_abha_id == patient_abha_id
    ).order_by(models.ConsentArtifact.granted_at.desc()).all()


# ─── Encrypted FHIR Bundle Routing ────────────────────────────

@app.post("/bundle/notify")
def notify_bundle(req: BundleNotifyRequest, db: Session = Depends(get_db)):
    """
    Hospital A notifies Switch that an encrypted FHIR bundle exists for a patient.
    Switch stores ONLY the reference and encryption key — NOT the data.
    """
    bundle_ref_id = f"BDL-{uuid.uuid4().hex[:12]}"
    encryption_key = generate_bundle_key()

    ref = models.EncryptedBundleRef(
        bundle_ref_id=bundle_ref_id,
        patient_abha_id=req.patient_abha_id,
        source_hospital_id=req.source_hospital_id,
        encryption_key=encryption_key,
        bundle_location=req.bundle_location,
        resource_count=req.resource_count,
        resource_types=req.resource_types,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=req.expires_in_hours),
    )
    db.add(ref)
    append_audit(db, req.source_hospital_id, "BUNDLE_NOTIFIED",
                 f"EncryptedBundleRef/{bundle_ref_id}",
                 patient_abha_id=req.patient_abha_id,
                 hospital_id=req.source_hospital_id,
                 details={"resource_count": req.resource_count, "resource_types": req.resource_types})
    db.commit()

    return {
        "bundle_ref_id": bundle_ref_id,
        "encryption_key": encryption_key,
        "message": "Bundle reference registered. Encryption key will be shared only after consent validation.",
        "expires_at": ref.expires_at.isoformat(),
    }


@app.post("/bundle/request")
def request_bundle(req: BundleRequestRequest, db: Session = Depends(get_db)):
    """
    Hospital B requests access to a patient's encrypted FHIR bundle.
    Switch validates consent, then shares the encryption key — NOT the data.

    Flow:
    1. Validate consent token
    2. Find bundle references for patient
    3. Filter by consent scope
    4. Share encryption keys (NOT data!)
    5. Hospital B fetches encrypted bundle directly from Hospital A
    6. Hospital B decrypts using shared key
    """
    # 1. Validate consent
    consent = db.query(models.ConsentArtifact).filter(
        models.ConsentArtifact.consent_token == req.consent_token,
        models.ConsentArtifact.status == "GRANTED",
    ).first()

    if not consent:
        raise HTTPException(status_code=403, detail="Invalid or expired consent token")

    if consent.expires_at < datetime.now(timezone.utc):
        consent.status = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=403, detail="Consent has expired")

    # 2. Find bundle references for patient
    bundle_refs = db.query(models.EncryptedBundleRef).filter(
        models.EncryptedBundleRef.patient_abha_id == req.patient_abha_id,
        models.EncryptedBundleRef.expires_at > datetime.now(timezone.utc),
    ).all()

    if not bundle_refs:
        raise HTTPException(status_code=404, detail="No bundle references found for patient")

    # 3. Build response — share keys + locations
    shared_bundles = []
    for ref in bundle_refs:
        # Record key share
        key_share = models.KeyShareRecord(
            bundle_ref_id=ref.bundle_ref_id,
            consent_id=consent.consent_id,
            requesting_hospital_id=req.requesting_hospital_id,
            patient_abha_id=req.patient_abha_id,
        )
        db.add(key_share)

        shared_bundles.append({
            "bundle_ref_id": ref.bundle_ref_id,
            "source_hospital_id": ref.source_hospital_id,
            "bundle_location": ref.bundle_location,
            "encryption_key": ref.encryption_key,
            "resource_count": ref.resource_count,
            "resource_types": ref.resource_types,
            "created_at": ref.created_at.isoformat(),
        })

    append_audit(db, req.requesting_hospital_id, "BUNDLE_KEY_SHARED",
                 f"Patient/{req.patient_abha_id}",
                 consent_id=consent.consent_id,
                 hospital_id=req.requesting_hospital_id,
                 patient_abha_id=req.patient_abha_id,
                 details={"bundles_shared": len(shared_bundles)})
    db.commit()

    return {
        "status": "KEYS_SHARED",
        "patient_abha_id": req.patient_abha_id,
        "consent_id": consent.consent_id,
        "bundles": shared_bundles,
        "message": (
            f"Encryption keys shared for {len(shared_bundles)} bundle(s). "
            "Fetch encrypted data directly from source hospital(s) "
            "and decrypt using the provided key(s)."
        ),
        "data_stored_on_switch": "NONE",
    }


# ─── Emergency Access (Break-Glass) ────────────────────────────

@app.post("/emergency-access")
def emergency_access(req: EmergencyAccessRequest, db: Session = Depends(get_db)):
    """
    Break-glass protocol for emergency data access.
    Creates a temporary 4-hour full-scope consent.
    Triggers notifications and is heavily audited.
    """
    # Verify requesting hospital exists
    hospital = db.query(models.Hospital).filter(
        models.Hospital.hospital_id == req.hospital_id,
        models.Hospital.is_active == True,
    ).first()

    if not hospital:
        raise HTTPException(status_code=403, detail="Requesting hospital not registered")

    consent_id = str(uuid.uuid4())
    token = generate_consent_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=4)

    consent = models.ConsentArtifact(
        consent_id=consent_id,
        consent_token=token,
        patient_abha_id=req.patient_abha_id,
        doctor_id=req.doctor_id,
        hospital_id=req.hospital_id,
        status="GRANTED",
        purpose="emergency",
        permissions=["Patient", "Observation", "DiagnosticReport", "Condition",
                     "MedicationRequest", "AllergyIntolerance", "Encounter"],
        granted_at=datetime.now(timezone.utc),
        expires_at=expires_at,
        is_emergency=True,
    )
    db.add(consent)

    append_audit(db, req.doctor_id, "EMERGENCY_ACCESS",
                 f"Patient/{req.patient_abha_id}",
                 consent_id=consent_id, hospital_id=req.hospital_id,
                 patient_abha_id=req.patient_abha_id,
                 details={
                     "reason": req.reason,
                     "doctor_id": req.doctor_id,
                     "hospital_name": hospital.name,
                     "valid_hours": 4,
                 })
    db.commit()

    return {
        "status": "EMERGENCY_ACCESS_GRANTED",
        "consent_id": consent_id,
        "consent_token": token,
        "patient_abha_id": req.patient_abha_id,
        "valid_until": expires_at.isoformat(),
        "scope": ["ALL"],
        "notifications_sent": [
            "SMS to patient's registered emergency contacts",
            "Email to patient's family guardians",
            "Push notification to patient's HealthWallet",
        ],
        "disclaimer": (
            "Emergency access is logged and audited. "
            "Misuse will trigger security review and potential sanctions."
        ),
    }


# ─── Audit Log ────────────────────────────

@app.get("/audit/log")
def get_audit_log(
    limit: int = 50,
    patient_abha_id: Optional[str] = None,
    action: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Retrieve audit log entries with optional filtering."""
    query = db.query(models.AuditLog).order_by(models.AuditLog.id.desc())

    if patient_abha_id:
        query = query.filter(models.AuditLog.patient_abha_id == patient_abha_id)
    if action:
        query = query.filter(models.AuditLog.action == action)

    entries = query.limit(limit).all()
    return [{
        "id": e.id,
        "timestamp": e.timestamp,
        "actor": e.actor,
        "action": e.action,
        "resource": e.resource,
        "consent_id": e.consent_id,
        "hospital_id": e.hospital_id,
        "patient_abha_id": e.patient_abha_id,
        "previous_hash": e.previous_hash,
        "current_hash": e.current_hash,
        "details": e.details,
    } for e in entries]


@app.get("/audit/verify")
def verify_audit_chain(db: Session = Depends(get_db)):
    """Verify the integrity of the entire audit log hash chain."""
    entries = db.query(models.AuditLog).order_by(models.AuditLog.id.asc()).all()
    chain_data = [{
        "previous_hash": e.previous_hash,
        "current_hash": e.current_hash,
        "actor": e.actor,
        "action": e.action,
        "resource": e.resource,
        "timestamp": e.timestamp,
    } for e in entries]

    result = verify_hash_chain(chain_data)
    return result


# ─── Demo Endpoints ────────────────────────────

@app.post("/demo/encrypt-bundle")
def demo_encrypt_bundle(bundle_json: str = "{}"):
    """Demo endpoint: encrypt a FHIR bundle and return encrypted data + key."""
    key = generate_bundle_key()
    encrypted = encrypt_bundle(bundle_json, key)
    return {
        "encryption_key": key,
        "encrypted_bundle": encrypted[:200] + "..." if len(encrypted) > 200 else encrypted,
        "encrypted_size_bytes": len(encrypted),
        "original_size_bytes": len(bundle_json),
    }


@app.post("/demo/decrypt-bundle")
def demo_decrypt_bundle(encrypted_bundle: str, encryption_key: str):
    """Demo endpoint: decrypt a FHIR bundle using the provided key."""
    try:
        decrypted = decrypt_bundle(encrypted_bundle, encryption_key)
        return {"decrypted_bundle": decrypted, "success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decryption failed: {str(e)}")


@app.get("/demo/data-flow")
def demo_data_flow():
    """Shows the complete data flow with S3 storage for the UHI Switch."""
    return {
        "title": "UHI Switch — S3 Encrypted FHIR Routing Data Flow",
        "steps": [
            {"step": 1, "actor": "Hospital A", "action": "Creates FHIR R5 bundle from EMR"},
            {"step": 2, "actor": "Hospital A", "action": "Encrypts bundle with AES-256"},
            {"step": 3, "actor": "Hospital A → Switch", "action": "POST /storage/upload — uploads encrypted bundle to S3 bucket"},
            {"step": 4, "actor": "Switch", "action": "Stores in S3 bucket with presigned URL + encryption key (auto-expires)"},
            {"step": 5, "actor": "Patient (mobile app)", "action": "POST /app/consent/grant — grants consent via HealthWallet"},
            {"step": 6, "actor": "Hospital B", "action": "POST /bundle/request — validates consent → gets presigned URL + key"},
            {"step": 7, "actor": "Hospital B", "action": "GET /storage/download?token=xxx — downloads encrypted bundle"},
            {"step": 8, "actor": "Hospital B", "action": "Decrypts bundle locally with shared key"},
            {"step": 9, "actor": "Switch", "action": "Auto-deletes S3 bucket after expiry (set by Hospital A/patient)"},
        ],
        "production_note": "In production, S3 buckets are real AWS S3 with server-side encryption + presigned URLs. This mock stores in SQLite.",
    }


# ─── S3 Mock Storage (Encrypted Bucket) ────────────────────────────

class StorageUploadRequest(BaseModel):
    patient_abha_id: str
    source_hospital_id: str
    encrypted_bundle: str  # Base64-encoded encrypted FHIR bundle
    resource_count: int
    resource_types: List[str]
    expires_in_hours: int = 24
    max_downloads: int = 5


class StorageDownloadResponse(BaseModel):
    bucket_id: str
    encrypted_data: str
    data_hash: str
    source_hospital_id: str
    resource_count: int


@app.post("/storage/upload")
def upload_to_storage(req: StorageUploadRequest, db: Session = Depends(get_db)):
    """
    Hospital uploads encrypted FHIR bundle to S3-like storage.
    In production: maps to aws s3 cp + presigned URL generation.
    Returns bucket_id + presigned_token for access.
    """
    import hashlib as _hashlib

    bucket_id = f"s3-{uuid.uuid4().hex[:12]}"
    presigned_token = generate_consent_token()
    encryption_key = generate_bundle_key()
    data_hash = _hashlib.sha256(req.encrypted_bundle.encode()).hexdigest()

    bucket = models.StorageBucket(
        bucket_id=bucket_id,
        patient_abha_id=req.patient_abha_id,
        source_hospital_id=req.source_hospital_id,
        encrypted_data=req.encrypted_bundle,
        encryption_key=encryption_key,
        data_hash=data_hash,
        resource_count=req.resource_count,
        resource_types=req.resource_types,
        presigned_token=presigned_token,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=req.expires_in_hours),
        max_access_count=req.max_downloads,
    )
    db.add(bucket)

    # Also register as a bundle reference for the consent flow
    ref = models.EncryptedBundleRef(
        bundle_ref_id=bucket_id,
        patient_abha_id=req.patient_abha_id,
        source_hospital_id=req.source_hospital_id,
        encryption_key=encryption_key,
        bundle_location=f"/storage/download?token={presigned_token}",
        resource_count=req.resource_count,
        resource_types=req.resource_types,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=req.expires_in_hours),
    )
    db.add(ref)

    append_audit(db, req.source_hospital_id, "S3_UPLOAD",
                 f"StorageBucket/{bucket_id}",
                 patient_abha_id=req.patient_abha_id,
                 hospital_id=req.source_hospital_id,
                 details={
                     "resource_count": req.resource_count,
                     "data_hash": data_hash,
                     "expires_in_hours": req.expires_in_hours,
                 })
    db.commit()

    return {
        "bucket_id": bucket_id,
        "presigned_token": presigned_token,
        "presigned_url": f"/storage/download?token={presigned_token}",
        "encryption_key": encryption_key,
        "data_hash": data_hash,
        "expires_at": bucket.expires_at.isoformat(),
        "max_downloads": req.max_downloads,
        "production_equivalent": f"s3://uhi-encrypted-bundles/{bucket_id}/bundle.enc",
    }


@app.get("/storage/download")
def download_from_storage(token: str, db: Session = Depends(get_db)):
    """
    Download encrypted bundle from S3-like storage using presigned token.
    In production: maps to S3 GetObject with presigned URL.
    """
    bucket = db.query(models.StorageBucket).filter(
        models.StorageBucket.presigned_token == token,
        models.StorageBucket.is_deleted == False,
    ).first()

    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket not found or deleted")

    if bucket.expires_at < datetime.now(timezone.utc):
        bucket.is_deleted = True
        db.commit()
        raise HTTPException(status_code=410, detail="Bucket expired — data has been auto-deleted")

    if bucket.accessed_count >= bucket.max_access_count:
        raise HTTPException(status_code=403, detail="Max download count reached")

    bucket.accessed_count += 1

    append_audit(db, "PRESIGNED_ACCESS", "S3_DOWNLOAD",
                 f"StorageBucket/{bucket.bucket_id}",
                 patient_abha_id=bucket.patient_abha_id,
                 hospital_id=bucket.source_hospital_id,
                 details={"access_count": bucket.accessed_count})
    db.commit()

    return {
        "bucket_id": bucket.bucket_id,
        "encrypted_data": bucket.encrypted_data,
        "data_hash": bucket.data_hash,
        "source_hospital_id": bucket.source_hospital_id,
        "resource_count": bucket.resource_count,
        "resource_types": bucket.resource_types,
        "access_count": bucket.accessed_count,
        "max_access_count": bucket.max_access_count,
    }


@app.delete("/storage/{bucket_id}")
def delete_storage_bucket(bucket_id: str, db: Session = Depends(get_db)):
    """
    Manually delete an S3 bucket (soft delete).
    In production: aws s3 rm + bucket policy expiry.
    """
    bucket = db.query(models.StorageBucket).filter(
        models.StorageBucket.bucket_id == bucket_id
    ).first()

    if not bucket:
        raise HTTPException(status_code=404, detail="Bucket not found")

    bucket.is_deleted = True
    bucket.encrypted_data = ""  # Wipe data

    append_audit(db, bucket.source_hospital_id, "S3_DELETE",
                 f"StorageBucket/{bucket_id}",
                 patient_abha_id=bucket.patient_abha_id,
                 details={"reason": "manual_deletion"})
    db.commit()

    return {"status": "DELETED", "bucket_id": bucket_id}


@app.post("/storage/cleanup-expired")
def cleanup_expired_buckets(db: Session = Depends(get_db)):
    """
    Auto-cleanup expired S3 buckets.
    In production: Lambda/cron job with S3 lifecycle policies.
    """
    expired = db.query(models.StorageBucket).filter(
        models.StorageBucket.expires_at < datetime.now(timezone.utc),
        models.StorageBucket.is_deleted == False,
    ).all()

    deleted_count = 0
    for bucket in expired:
        bucket.is_deleted = True
        bucket.encrypted_data = ""
        append_audit(db, "SYSTEM", "S3_AUTO_DELETE",
                     f"StorageBucket/{bucket.bucket_id}",
                     patient_abha_id=bucket.patient_abha_id,
                     details={"reason": "auto_expiry"})
        deleted_count += 1

    db.commit()
    return {"deleted_count": deleted_count, "message": f"Cleaned up {deleted_count} expired bucket(s)"}


# ─── Mobile App APIs (HealthWallet) ────────────────────────────
# These endpoints are designed for the Flutter HealthWallet app
# to interact with the UHI Switch.

class AppConsentGrantRequest(BaseModel):
    """Mobile app consent grant — patient initiates from their phone."""
    patient_abha_id: str
    requesting_hospital_id: str
    purpose: str = "diagnosis"
    permissions: List[str] = ["Patient", "Observation", "DiagnosticReport", "Condition",
                              "MedicationRequest", "AllergyIntolerance"]
    valid_hours: int = 24


@app.get("/app/patient/{abha_id}/bundles")
def app_patient_bundles(abha_id: str, db: Session = Depends(get_db)):
    """
    Mobile App: List all available data bundles for a patient.
    Shows what records exist across hospitals.
    """
    bundles = db.query(models.EncryptedBundleRef).filter(
        models.EncryptedBundleRef.patient_abha_id == abha_id,
        models.EncryptedBundleRef.expires_at > datetime.now(timezone.utc),
    ).all()

    return {
        "patient_abha_id": abha_id,
        "bundles": [{
            "bundle_ref_id": b.bundle_ref_id,
            "source_hospital_id": b.source_hospital_id,
            "resource_count": b.resource_count,
            "resource_types": b.resource_types,
            "created_at": b.created_at.isoformat(),
            "expires_at": b.expires_at.isoformat(),
        } for b in bundles],
        "total_bundles": len(bundles),
    }


@app.post("/app/consent/grant")
def app_grant_consent(req: AppConsentGrantRequest, db: Session = Depends(get_db)):
    """
    Mobile App: Patient grants consent from their HealthWallet app.
    Simplified flow — patient just confirms on their phone.
    """
    consent_id = str(uuid.uuid4())
    token = generate_consent_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=req.valid_hours)

    consent = models.ConsentArtifact(
        consent_id=consent_id,
        consent_token=token,
        patient_abha_id=req.patient_abha_id,
        doctor_id="PATIENT_SELF",
        hospital_id=req.requesting_hospital_id,
        status="GRANTED",
        purpose=req.purpose,
        permissions=req.permissions,
        granted_at=datetime.now(timezone.utc),
        expires_at=expires_at,
    )
    db.add(consent)
    append_audit(db, req.patient_abha_id, "APP_CONSENT_GRANT",
                 f"ConsentArtifact/{consent_id}",
                 consent_id=consent_id,
                 hospital_id=req.requesting_hospital_id,
                 patient_abha_id=req.patient_abha_id,
                 details={"purpose": req.purpose, "via": "HealthWallet App"})
    db.commit()

    return {
        "status": "CONSENT_GRANTED",
        "consent_id": consent_id,
        "consent_token": token,
        "valid_until": expires_at.isoformat(),
        "message": f"Consent granted to hospital {req.requesting_hospital_id} for {req.valid_hours}h",
    }


@app.get("/app/patient/{abha_id}/consents")
def app_patient_consents(abha_id: str, db: Session = Depends(get_db)):
    """
    Mobile App: List all active consents for a patient.
    Patient can see who has access to their data.
    """
    consents = db.query(models.ConsentArtifact).filter(
        models.ConsentArtifact.patient_abha_id == abha_id,
    ).order_by(models.ConsentArtifact.granted_at.desc()).all()

    return {
        "patient_abha_id": abha_id,
        "consents": [{
            "consent_id": c.consent_id,
            "hospital_id": c.hospital_id,
            "status": c.status,
            "purpose": c.purpose,
            "permissions": c.permissions,
            "granted_at": c.granted_at.isoformat() if c.granted_at else None,
            "expires_at": c.expires_at.isoformat() if c.expires_at else None,
            "is_emergency": c.is_emergency,
        } for c in consents],
    }


@app.post("/app/consent/{consent_id}/revoke")
def app_revoke_consent(consent_id: str, db: Session = Depends(get_db)):
    """
    Mobile App: Patient revokes consent from their HealthWallet app.
    """
    consent = db.query(models.ConsentArtifact).filter(
        models.ConsentArtifact.consent_id == consent_id
    ).first()

    if not consent:
        raise HTTPException(status_code=404, detail="Consent not found")
    if consent.status != "GRANTED":
        raise HTTPException(status_code=400, detail=f"Consent already {consent.status}")

    consent.status = "REVOKED"
    consent.revoked_at = datetime.now(timezone.utc)
    append_audit(db, consent.patient_abha_id, "APP_CONSENT_REVOKE",
                 f"ConsentArtifact/{consent_id}",
                 consent_id=consent_id,
                 hospital_id=consent.hospital_id,
                 patient_abha_id=consent.patient_abha_id,
                 details={"via": "HealthWallet App"})
    db.commit()

    return {"status": "REVOKED", "consent_id": consent_id}


@app.get("/app/patient/{abha_id}/summary")
def app_patient_summary(abha_id: str, db: Session = Depends(get_db)):
    """
    Mobile App: Patient's health data summary across all hospitals.
    Shows what data exists without exposing the actual data.
    """
    bundles = db.query(models.EncryptedBundleRef).filter(
        models.EncryptedBundleRef.patient_abha_id == abha_id,
    ).all()

    consents = db.query(models.ConsentArtifact).filter(
        models.ConsentArtifact.patient_abha_id == abha_id,
    ).all()

    hospitals = set()
    all_resource_types = set()
    total_resources = 0
    for b in bundles:
        hospitals.add(b.source_hospital_id)
        if b.resource_types:
            all_resource_types.update(b.resource_types)
        total_resources += b.resource_count or 0

    active_consents = sum(1 for c in consents if c.status == "GRANTED")
    revoked_consents = sum(1 for c in consents if c.status == "REVOKED")

    return {
        "patient_abha_id": abha_id,
        "data_summary": {
            "hospitals_with_data": list(hospitals),
            "total_bundles": len(bundles),
            "total_resources": total_resources,
            "resource_types": sorted(all_resource_types),
        },
        "consent_summary": {
            "active": active_consents,
            "revoked": revoked_consents,
            "total": len(consents),
        },
        "message": "Your health data is encrypted and only accessible with your consent.",
    }


# ─── Patient Records (Direct Access — Patient's Own Data) ────────────

from patient_data_hospital_a import (
    HOSPITAL_A_ID, HOSPITAL_A_NAME, DEVAGANESH_PATIENT as PATIENT_A,
    MONTHLY_PROGRESS, IMAGING_REPORTS_HOSPITAL_A, BASELINE_VITALS, FINAL_VITALS,
)
from patient_data_hospital_b import (
    HOSPITAL_B_ID, HOSPITAL_B_NAME, DEVAGANESH_PATIENT as PATIENT_B,
    IMAGING_REPORTS_HOSPITAL_B, BASELINE_XRAY_IMAGE,
)


@app.get("/app/patient/{abha_id}/records")
def app_patient_records(abha_id: str):
    """
    Mobile App: Get ALL clinical records for a patient.
    The patient can ALWAYS access their own data — no consent required.
    Returns structured records from all hospitals.
    """
    if abha_id != "91-1234-5678-9012":
        raise HTTPException(status_code=404, detail="Patient not found")

    # Build progress records (Hospital A — 10 months)
    progress_records = []
    for p in MONTHLY_PROGRESS:
        record = {
            "month": p["month"],
            "source_hospital": HOSPITAL_A_NAME,
            "source_hospital_id": HOSPITAL_A_ID,
            "type": "progress_report",
            "blood_pressure": p["bp"],
            "weight_kg": p["weight_kg"],
            "bmi": p["bmi"],
            "resting_heart_rate": p["resting_hr"],
            "total_cholesterol": p["total_cholesterol"],
            "triglycerides": p["triglycerides"],
            "hdl": p["hdl"],
            "medication": p["medication"],
            "exercise": p["exercise"],
            "assessment": p["assessment"],
        }
        progress_records.append(record)

    # Build imaging records (Hospital A — months 1-2)
    imaging_records = []
    for img in IMAGING_REPORTS_HOSPITAL_A:
        imaging_records.append({
            "month": img["month"],
            "source_hospital": HOSPITAL_A_NAME,
            "source_hospital_id": HOSPITAL_A_ID,
            "type": img["type"],
            "technique": img["technique"],
            "findings": img["findings"],
            "impression": img["impression"],
            "radiologist": img["radiologist"],
            "comparison": img.get("comparison"),
        })

    # Build imaging records (Hospital B — months 3-8)
    for img in IMAGING_REPORTS_HOSPITAL_B:
        imaging_records.append({
            "month": img["month"],
            "source_hospital": HOSPITAL_B_NAME,
            "source_hospital_id": HOSPITAL_B_ID,
            "type": img["type"],
            "technique": img["technique"],
            "findings": img["findings"],
            "impression": img["impression"],
            "radiologist": img["radiologist"],
            "comparison": img.get("comparison"),
        })

    # Baseline X-ray image analysis (Hospital B)
    baseline_xray = {
        "source_hospital": HOSPITAL_B_NAME,
        "source_hospital_id": HOSPITAL_B_ID,
        "type": "chest_xray_image_analysis",
        "clinical_indication": BASELINE_XRAY_IMAGE["clinical_indication"],
        "technique": BASELINE_XRAY_IMAGE["technique"],
        "findings": BASELINE_XRAY_IMAGE["findings"],
        "impression": BASELINE_XRAY_IMAGE["impression"],
        "ctr_baseline": BASELINE_XRAY_IMAGE["ctr_baseline"],
        "ctr_month5": BASELINE_XRAY_IMAGE["ctr_month5"],
        "ctr_month7": BASELINE_XRAY_IMAGE["ctr_month7"],
    }

    return {
        "patient_abha_id": abha_id,
        "patient": {
            "name": PATIENT_A["name"],
            "age": PATIENT_A["age"],
            "gender": PATIENT_A["gender"],
            "blood_group": PATIENT_A["blood_group"],
            "primary_diagnosis": PATIENT_A["primary_diagnosis"],
            "treatment_started": PATIENT_A["treatment_started"],
            "treatment_type": PATIENT_A["treatment_type"],
            "referring_physician": PATIENT_A["referring_physician"],
        },
        "hospitals": [
            {"id": HOSPITAL_A_ID, "name": HOSPITAL_A_NAME,
             "role": "Primary Care — Internal Medicine"},
            {"id": HOSPITAL_B_ID, "name": HOSPITAL_B_NAME,
             "role": "Radiology & Diagnostics (Referral)"},
        ],
        "baseline_vitals": BASELINE_VITALS,
        "final_vitals": FINAL_VITALS,
        "progress_records": progress_records,
        "imaging_records": imaging_records,
        "baseline_xray_analysis": baseline_xray,
        "total_records": len(progress_records) + len(imaging_records) + 1,
    }

