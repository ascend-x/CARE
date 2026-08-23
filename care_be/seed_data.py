"""
Seed data for the lightweight CARE prototype.
Contains all hardcoded users, patients, facilities, and organizations
matching the original CARE EMR demo setup.
"""

import uuid

# ─── Users ─────────────────────────────────────────────
# Same credentials as the original care_be fixtures

USERS = {
    "admin": {
        "id": 1,
        "external_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "admin")),
        "username": "admin",
        "password": "admin",
        "first_name": "Admin",
        "last_name": "User",
        "email": "admin@care.ohc.network",
        "user_type": "DistrictAdmin",
        "is_superuser": True,
        "phone_number": "+919876543210",
        "gender": "male",
        "permissions": [
            "can_read_patient",
            "can_write_patient",
            "can_read_encounter",
            "can_write_encounter",
            "can_read_facility",
            "can_write_facility",
            "can_read_user",
            "can_write_user",
            "can_read_organization",
            "can_write_organization",
        ],
    },
    "dr-shivani": {
        "id": 2,
        "external_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "dr-shivani")),
        "username": "dr-shivani",
        "password": "Coronasafe@123",
        "first_name": "Dr. Shivani",
        "last_name": "Kapoor",
        "email": "shivani@care.ohc.network",
        "user_type": "Doctor",
        "is_superuser": False,
        "phone_number": "+919876543211",
        "gender": "female",
        "permissions": [
            "can_read_patient",
            "can_write_patient",
            "can_read_encounter",
            "can_write_encounter",
            "can_read_facility",
        ],
    },
    "devdistrictadmin": {
        "id": 3,
        "external_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "devdistrictadmin")),
        "username": "devdistrictadmin",
        "password": "Coronasafe@123",
        "first_name": "Dev",
        "last_name": "District Admin",
        "email": "devadmin@care.ohc.network",
        "user_type": "DistrictAdmin",
        "is_superuser": False,
        "phone_number": "+919876543212",
        "gender": "male",
        "permissions": [
            "can_read_patient",
            "can_write_patient",
            "can_read_encounter",
            "can_write_encounter",
            "can_read_facility",
            "can_write_facility",
            "can_read_user",
        ],
    },
    "doctor_a": {
        "id": 4,
        "external_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "doctor_a")),
        "username": "doctor_a",
        "password": "doctor_a",
        "first_name": "Dr. Anand",
        "last_name": "Sharma",
        "email": "doctor_a@cityCare.hospital",
        "user_type": "Doctor",
        "is_superuser": False,
        "phone_number": "+919876543213",
        "gender": "male",
        "permissions": [
            "can_read_patient",
            "can_write_patient",
            "can_read_encounter",
            "can_write_encounter",
        ],
    },
    "doctor_b": {
        "id": 5,
        "external_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "doctor_b")),
        "username": "doctor_b",
        "password": "doctor_b",
        "first_name": "Dr. Priya",
        "last_name": "Menon",
        "email": "doctor_b@metro.radiology",
        "user_type": "Doctor",
        "is_superuser": False,
        "phone_number": "+919876543214",
        "gender": "female",
        "permissions": [
            "can_read_patient",
            "can_write_patient",
            "can_read_encounter",
            "can_write_encounter",
        ],
    },
}


# ─── Patients ─────────────────────────────────────────────

PATIENTS = [
    {
        "id": 1,
        "external_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "devaganesh")),
        "name": "Devaganesh S",
        "gender": "male",
        "blood_group": "O+",
        "date_of_birth": "1998-03-15",
        "phone_number": "+919876543210",
        "address": "42, Anna Nagar, Chennai, Tamil Nadu 600040",
        "meta": {
            "abha_id": "91-1234-5678-9012",
        },
        "created_date": "2025-08-15T10:00:00Z",
    },
]


# ─── Facilities ─────────────────────────────────────────────

FACILITIES = [
    {
        "id": 1,
        "external_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "facility-demo")),
        "name": "CARE Demo Hospital",
        "facility_type": "hospital",
        "address": "Trivandrum, Kerala",
        "phone_number": "+914712345678",
        "state": "Kerala",
        "district": "Trivandrum",
        "local_body": "Trivandrum Corporation",
        "ward": "Ward 1",
        "pincode": "695001",
        "latitude": 8.5241,
        "longitude": 76.9366,
        "features": [],
        "created_date": "2025-01-01T00:00:00Z",
    },
    {
        "id": 2,
        "external_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "facility-citycare")),
        "name": "CityCare Multispeciality Hospital",
        "facility_type": "hospital",
        "address": "Chennai, Tamil Nadu",
        "phone_number": "+914412345678",
        "state": "Tamil Nadu",
        "district": "Chennai",
        "local_body": "Chennai Corporation",
        "ward": "Ward 5",
        "pincode": "600001",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "features": [],
        "created_date": "2025-01-01T00:00:00Z",
    },
    {
        "id": 3,
        "external_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "facility-metro")),
        "name": "Metro Radiology & Diagnostics",
        "facility_type": "hospital",
        "address": "Chennai, Tamil Nadu",
        "phone_number": "+914412345679",
        "state": "Tamil Nadu",
        "district": "Chennai",
        "local_body": "Chennai Corporation",
        "ward": "Ward 8",
        "pincode": "600002",
        "latitude": 13.0600,
        "longitude": 80.2500,
        "features": [],
        "created_date": "2025-01-01T00:00:00Z",
    },
]


# ─── Organizations ─────────────────────────────────────────────

ORGANIZATIONS = [
    {
        "id": 1,
        "external_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "org-demo")),
        "name": "Demo District Health Authority",
        "org_type": "govt",
        "description": "Demo district for CARE prototype",
        "created_date": "2025-01-01T00:00:00Z",
    },
]
