"""
Lightweight FHIR R5 bundle generation utilities.
Ported from care_medgemma/fhir_utils.py — stripped of all Django dependencies.
Generates FHIR R5 Patient bundles with hardcoded Devaganesh S data.
"""

import uuid
from datetime import datetime, timezone
import os
import glob


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def create_sample_bundle(abha_id: str, patient_name: str = "Demo Patient") -> dict:
    """Generate a FHIR R5 Bundle for a given patient."""
    bundle_id = str(uuid.uuid4())

    patient_resource = {
        "resourceType": "Patient",
        "id": f"patient-{abha_id}",
        "identifier": [
            {
                "system": "https://healthid.abdm.gov.in",
                "value": abha_id,
            }
        ],
        "name": [{"use": "official", "text": patient_name}],
        "gender": "male",
        "birthDate": "1998-03-15",
    }

    # Hardcoded clinical entries for Devaganesh S
    entries = [
        {"fullUrl": f"urn:uuid:{uuid.uuid4()}", "resource": patient_resource},
    ]

    if abha_id == "91-1234-5678-9012":
        hospital_id = os.environ.get("HOSPITAL_ID", "HOSP-CITYCARE-A")

        if hospital_id == "HOSP-CITYCARE-A":
            conditions = [
                ("Pre-Diabetes (IFG + IGT)", "R73.03", "2025-08-15"),
                ("Dyslipidemia", "E78.5", "2025-11-20"),
            ]
            observations = [
                ("Fasting Blood Sugar", "1558-6", "118", "mg/dL"),
                ("HbA1c", "4548-4", "6.1", "%"),
                ("Hemoglobin", "718-7", "12.8", "g/dL"),
            ]
            medications = [
                ("Metformin 500mg", "BD"),
                ("Vitamin E 400IU", "OD"),
            ]
        else: # HOSP-METRO-B or others
            conditions = [
                ("Non-Alcoholic Fatty Liver Disease", "K76.0", "2025-11-20"),
            ]
            observations = [
                ("ALT (SGPT)", "1742-6", "92", "U/L"),
                ("AST (SGOT)", "1920-8", "78", "U/L"),
                ("GGT", "2324-2", "68", "U/L"),
                ("LDL Cholesterol", "2089-1", "148", "mg/dL"),
                ("HDL Cholesterol", "2085-9", "38", "mg/dL"),
                ("Triglycerides", "2571-8", "210", "mg/dL"),
                ("Total Cholesterol", "2093-3", "228", "mg/dL"),
                ("Creatinine", "2160-0", "0.9", "mg/dL"),
            ]
            medications = [
                ("Atorvastatin 10mg", "OD at night"),
                ("Pantoprazole 40mg", "OD before breakfast"),
                ("Ursodeoxycholic Acid 300mg", "BD"),
            ]

        for name, icd, onset in conditions:
            entries.append({
                "fullUrl": f"urn:uuid:{uuid.uuid4()}",
                "resource": {
                    "resourceType": "Condition",
                    "id": str(uuid.uuid4()),
                    "subject": {"reference": f"Patient/patient-{abha_id}"},
                    "code": {
                        "coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": icd, "display": name}],
                        "text": name,
                    },
                    "onsetDateTime": onset,
                    "clinicalStatus": {
                        "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]
                    },
                },
            })

        for display, loinc, value, unit in observations:
            entries.append({
                "fullUrl": f"urn:uuid:{uuid.uuid4()}",
                "resource": {
                    "resourceType": "Observation",
                    "id": str(uuid.uuid4()),
                    "status": "final",
                    "code": {
                        "coding": [{"system": "http://loinc.org", "code": loinc, "display": display}],
                        "text": display,
                    },
                    "subject": {"reference": f"Patient/patient-{abha_id}"},
                    "effectiveDateTime": "2026-02-28",
                    "valueQuantity": {"value": float(value), "unit": unit, "system": "http://unitsofmeasure.org"},
                },
            })

        for med_name, dosage in medications:
            entries.append({
                "fullUrl": f"urn:uuid:{uuid.uuid4()}",
                "resource": {
                    "resourceType": "MedicationRequest",
                    "id": str(uuid.uuid4()),
                    "status": "active",
                    "intent": "order",
                    "subject": {"reference": f"Patient/patient-{abha_id}"},
                    "medicationCodeableConcept": {"text": med_name},
                    "dosageInstruction": [{"text": dosage}],
                },
            })

        # Add document references for uploaded PDFs
        doc_refs = get_document_references(abha_id)
        for doc in doc_refs:
            entries.append({
                "fullUrl": f"urn:uuid:{uuid.uuid4()}",
                "resource": doc,
            })

    bundle = {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "collection",
        "timestamp": _now_iso(),
        "total": len(entries),
        "entry": entries,
    }
    return bundle


def get_document_references(abha_id: str) -> list:
    """
    Get DocumentReference resources for a patient's uploaded files.
    Scans the uploads/ directory for PDFs.
    """
    doc_refs = []
    uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")

    if not os.path.isdir(uploads_dir):
        return doc_refs

    files = sorted(glob.glob(os.path.join(uploads_dir, "*")))
    for filepath in files:
        filename = os.path.basename(filepath)
        if not filename.lower().endswith((".pdf", ".jpg", ".jpeg", ".png")):
            continue

        hospital_id = os.environ.get("HOSPITAL_ID", "HOSP-CITYCARE-A")
        
        # Hospital A gets Progress Reports and Months 1-2
        if hospital_id == "HOSP-CITYCARE-A":
            if "Progress_Report" not in filename and "Month1" not in filename and "Month2" not in filename:
                continue
                
        # Hospital B gets Radiology (CT/XRay) from Months 3-8
        if hospital_id == "HOSP-METRO-B":
            if "CT_Scan" not in filename and "XRay" not in filename:
                continue
            if "Month1" in filename or "Month2" in filename:
                continue

        mime = "application/pdf" if filename.lower().endswith(".pdf") else "image/jpeg"
        doc_refs.append({
            "resourceType": "DocumentReference",
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, filename)),
            "status": "current",
            "type": {
                "coding": [{"system": "http://loinc.org", "code": "11502-2", "display": "Laboratory report"}],
                "text": "Clinical Report",
            },
            "subject": {"reference": f"Patient/patient-{abha_id}"},
            "date": _now_iso(),
            "content": [
                {
                    "attachment": {
                        "contentType": mime,
                        "url": f"/uploads/{filename}",
                        "title": filename,
                        "size": os.path.getsize(filepath),
                    }
                }
            ],
        })

    return doc_refs


def filter_bundle_by_scope(bundle: dict, scope: list, exclude: list) -> dict:
    """Filter FHIR bundle entries by consent scope."""
    if not scope and not exclude:
        return bundle

    filtered_entries = []
    for entry in bundle.get("entry", []):
        resource_type = entry.get("resource", {}).get("resourceType", "")
        if scope and resource_type not in scope:
            continue
        if exclude and resource_type in exclude:
            continue
        filtered_entries.append(entry)

    return {
        **bundle,
        "entry": filtered_entries,
        "total": len(filtered_entries),
    }
