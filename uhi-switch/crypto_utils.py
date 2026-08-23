"""
Cryptographic utilities for UHI-SWITCH Server.
Handles AES-256 encryption for FHIR bundles, SHA-256 hash chaining for audit logs,
and key management for consent-gated sharing.
"""

import hashlib
import json
import os
import secrets
import base64
from datetime import datetime, timezone


def generate_bundle_key() -> str:
    """Generate a random AES-256 key (32 bytes), returned as base64."""
    key = secrets.token_bytes(32)
    return base64.b64encode(key).decode("utf-8")


def encrypt_bundle(bundle_json: str, key_b64: str) -> str:
    """
    Encrypt a FHIR bundle JSON string using XOR-based encryption (demo).
    In production, use AES-256-GCM via the `cryptography` library.
    For hackathon: simple XOR with the key, base64 encoded.
    """
    key_bytes = base64.b64decode(key_b64)
    data_bytes = bundle_json.encode("utf-8")

    # Extend key to match data length
    extended_key = (key_bytes * (len(data_bytes) // len(key_bytes) + 1))[:len(data_bytes)]

    # XOR encrypt
    encrypted = bytes(a ^ b for a, b in zip(data_bytes, extended_key))
    return base64.b64encode(encrypted).decode("utf-8")


def decrypt_bundle(encrypted_b64: str, key_b64: str) -> str:
    """
    Decrypt a FHIR bundle using the same XOR-based scheme.
    """
    key_bytes = base64.b64decode(key_b64)
    encrypted_bytes = base64.b64decode(encrypted_b64)

    # Extend key to match data length
    extended_key = (key_bytes * (len(encrypted_bytes) // len(key_bytes) + 1))[:len(encrypted_bytes)]

    # XOR decrypt (same as encrypt)
    decrypted = bytes(a ^ b for a, b in zip(encrypted_bytes, extended_key))
    return decrypted.decode("utf-8")


def hash_chain_entry(previous_hash: str, actor: str, action: str, resource: str, timestamp: str) -> str:
    """
    Create a SHA-256 hash for an audit log entry, chained to the previous entry.
    This creates an immutable, tamper-evident audit trail.
    """
    data = f"{previous_hash}|{actor}|{action}|{resource}|{timestamp}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def generate_consent_token() -> str:
    """Generate a cryptographically secure consent token."""
    return secrets.token_urlsafe(32)


def verify_hash_chain(entries: list) -> dict:
    """
    Verify the integrity of an audit log hash chain.
    Returns verification result with details.
    """
    if not entries:
        return {"valid": True, "verified_count": 0, "message": "Empty chain"}

    for i, entry in enumerate(entries):
        if i == 0:
            expected_prev = "genesis"
        else:
            expected_prev = entries[i - 1]["current_hash"]

        if entry["previous_hash"] != expected_prev:
            return {
                "valid": False,
                "verified_count": i,
                "broken_at": i,
                "message": f"Chain broken at entry {i}: expected prev_hash={expected_prev}, got={entry['previous_hash']}",
            }

        # Verify the current hash
        expected_hash = hash_chain_entry(
            entry["previous_hash"],
            entry["actor"],
            entry["action"],
            entry["resource"],
            entry["timestamp"],
        )
        if entry["current_hash"] != expected_hash:
            return {
                "valid": False,
                "verified_count": i,
                "broken_at": i,
                "message": f"Hash mismatch at entry {i}: expected={expected_hash}, got={entry['current_hash']}",
            }

    return {
        "valid": True,
        "verified_count": len(entries),
        "message": f"All {len(entries)} entries verified successfully",
    }
