import httpx
import json

client = httpx.Client(base_url="http://localhost:9000")

# 1. Login as doctor
login_res = client.post("/api/v1/auth/login/", json={
    "username": "doctor_alice",
    "password": "password123"
})
print("Login:", login_res.json())
token = login_res.json()["access_token"]
client.headers["Authorization"] = f"Bearer {token}"

# 2. Create an Encounter for the demo patient
encounter_res = client.post("/api/v1/encounter/", json={
    "patient_id": "91-1234-5678-9012",
    "encounter_type": "inpatient",
    "chief_complaint": "LIVE SYNC TEST: Sudden chest pain",
    "vitals": {"bp": "120/80"},
    "examination": "Normal",
    "diagnosis": [],
    "plan": "Observation",
    "notes": "Testing Live Sync WebSocket Webhooks"
})
print("Encounter created:", encounter_res.json())

# 3. Create a Diagnostic Report for the demo patient
report_res = client.post("/api/v1/diagnostic_report/", json={
    "encounter_id": encounter_res.json().get("external_id", ""),
    "patient_id": "91-1234-5678-9012",
    "report_type": "imaging",
    "title": "LIVE SYNC TEST: Chest X-Ray",
    "category": "Cardiology",
    "findings": "Clear lungs, no cardiomegaly.",
    "impression": "Normal chest X-Ray.",
    "recommendations": "No further imaging needed.",
    "icd_codes": []
})
print("Report created:", report_res.json())
