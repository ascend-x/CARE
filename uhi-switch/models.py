from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timezone

Base = declarative_base()


class Hospital(Base):
    """Registered hospital in the UHI network."""
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(String, unique=True, index=True)
    name = Column(String, nullable=False)
    endpoint_url = Column(String, nullable=False)  # Base URL for FHIR API
    public_key = Column(Text, nullable=True)  # RSA public key for encrypted communication
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    registered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    last_heartbeat = Column(DateTime, nullable=True)
    status_message = Column(String, nullable=True)


class ConsentArtifact(Base):
    """DEPA-compliant consent artifact for data sharing."""
    __tablename__ = "consent_artifacts"

    id = Column(Integer, primary_key=True, index=True)
    consent_id = Column(String, unique=True, index=True)
    consent_token = Column(String, unique=True, index=True)  # Short-lived access token
    patient_abha_id = Column(String, index=True)
    doctor_id = Column(String)
    hospital_id = Column(String, index=True)  # Requesting hospital
    source_hospital_id = Column(String, nullable=True)  # Hospital that holds the data
    status = Column(String, default="GRANTED")  # GRANTED, REVOKED, EXPIRED, USED
    purpose = Column(String, default="diagnosis")
    permissions = Column(JSON)  # e.g. ["Observation", "Condition", "DiagnosticReport"]
    granted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime)
    revoked_at = Column(DateTime, nullable=True)
    is_emergency = Column(Boolean, default=False)


class EncryptedBundleRef(Base):
    """
    Pointer to an encrypted FHIR bundle at a source hospital.
    UHI-SWITCH NEVER stores the actual data — only the reference and encryption key.
    The encrypted bundle itself stays at the source hospital.
    """
    __tablename__ = "encrypted_bundle_refs"

    id = Column(Integer, primary_key=True, index=True)
    bundle_ref_id = Column(String, unique=True, index=True)
    patient_abha_id = Column(String, index=True)
    source_hospital_id = Column(String, index=True)  # Hospital that created the bundle
    encryption_key = Column(Text)  # AES-256 key (base64) — held temporarily
    bundle_location = Column(String)  # URL where encrypted bundle is stored at source hospital
    resource_count = Column(Integer, default=0)
    resource_types = Column(JSON)  # ["Patient", "Observation", "Condition", ...]
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime)  # Keys are auto-purged after expiry


class KeyShareRecord(Base):
    """Tracks which encryption keys were shared with which hospital after consent validation."""
    __tablename__ = "key_share_records"

    id = Column(Integer, primary_key=True, index=True)
    bundle_ref_id = Column(String, index=True)
    consent_id = Column(String, index=True)
    requesting_hospital_id = Column(String, index=True)
    patient_abha_id = Column(String, index=True)
    shared_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    accessed = Column(Boolean, default=False)  # Whether the key was actually used to decrypt


class AuditLog(Base):
    """Cryptographically chained, immutable audit trail."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(String, default=lambda: datetime.now(timezone.utc).isoformat())
    actor = Column(String)  # Who made the request (ABHA ID, hospital ID, doctor ID)
    action = Column(String)  # What action: GRANT_CONSENT, REVOKE_CONSENT, SHARE_KEY, READ_BUNDLE, EMERGENCY_ACCESS
    resource = Column(String)  # Resource accessed: ConsentArtifact/xxx, Bundle/xxx
    consent_id = Column(String, nullable=True)
    hospital_id = Column(String, nullable=True)
    patient_abha_id = Column(String, nullable=True)
    previous_hash = Column(String)  # Hash of previous entry (chain)
    current_hash = Column(String)  # SHA-256 hash of this entry
    details = Column(JSON, nullable=True)  # Additional metadata


class StorageBucket(Base):
    """
    S3-like encrypted storage bucket (mock).
    In production: maps to AWS S3 / MinIO presigned buckets.
    For demo: stores encrypted data in SQLite with auto-expiry.

    Flow:
    1. Hospital A encrypts FHIR bundle
    2. Hospital A uploads to S3 bucket via UHI-SWITCH → POST /storage/upload
    3. Switch stores encrypted blob + generates presigned URL
    4. After consent, Switch shares presigned URL + decryption key with Hospital B
    5. Hospital B downloads from presigned URL + decrypts
    6. Bucket auto-expires after TTL (set by Hospital A or patient)
    """
    __tablename__ = "storage_buckets"

    id = Column(Integer, primary_key=True, index=True)
    bucket_id = Column(String, unique=True, index=True)
    patient_abha_id = Column(String, index=True)
    source_hospital_id = Column(String, index=True)
    encrypted_data = Column(Text)  # Base64 encrypted FHIR bundle
    encryption_key = Column(Text)  # AES-256 key (kept by Switch, shared after consent)
    data_hash = Column(String)  # SHA-256 hash of encrypted data (for integrity)
    resource_count = Column(Integer, default=0)
    resource_types = Column(JSON)
    presigned_token = Column(String, unique=True, index=True)  # Access token (like S3 presigned URL)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime)
    accessed_count = Column(Integer, default=0)
    max_access_count = Column(Integer, default=5)  # Max downloads before token invalidation
    is_deleted = Column(Boolean, default=False)

