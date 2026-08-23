"""
Management command to load CARE-specific fixtures:
  - Dr. Shivani (Doctor role)
  - Patient Devaganesh S with ABHA ID 91-1234-5678-9012
  - All patient reports uploaded to MinIO

Run AFTER `load_fixtures`:
    python manage.py load_care_fixtures
"""

import os
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction

from care.emr.models import Organization, Patient
from care.emr.models.encounter import Encounter
from care.emr.models.file_upload import FileUpload
from care.emr.models.organization import FacilityOrganizationUser, OrganizationUser
from care.emr.resources.encounter.constants import (
    ClassChoices,
    EncounterPriorityChoices,
    StatusChoices,
)
from care.emr.resources.organization.spec import OrganizationTypeChoices
from care.emr.resources.patient.spec import BloodGroupChoices, GenderChoices
from care.security.models import RoleModel
from care.users.models import User
from care.utils.csp.config import BucketType

# Paths to patient report directories (relative to CARE project root)
CARE_ROOT = Path(settings.BASE_DIR).parent.parent  # /app → project root
REPORT_DIRS = [
    "/app/devaganesh-reports-hospital-1",
    "/app/devaganesh-reports-hospital-2",
]

# Patient details
PATIENT_NAME = "Devaganesh S"
PATIENT_ABHA = "91-1234-5678-9012"
PATIENT_DOB = "1998-03-15"
PATIENT_GENDER = GenderChoices.male
PATIENT_BLOOD_GROUP = BloodGroupChoices.O_positive

# Doctor details
DOCTOR_USERNAME = "dr-shivani"
DOCTOR_PASSWORD = "Coronasafe@123"
DOCTOR_FIRST_NAME = "Shivani"
DOCTOR_LAST_NAME = "Bhowmik"


class Command(BaseCommand):
    help = "Load CARE-specific fixtures: Dr. Shivani, patient Devaganesh, and reports"

    def handle(self, *args, **options):
        if not settings.DEBUG:
            self.stdout.write(
                self.style.ERROR("This command should not be run in production.")
            )
            return

        try:
            with transaction.atomic():
                self._load_fixtures()
                self.stdout.write(
                    self.style.SUCCESS("CARE fixtures loaded successfully!")
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            raise

    def _load_fixtures(self):
        # Get prerequisite objects
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stdout.write(
                self.style.ERROR("No superuser found. Run load_fixtures first.")
            )
            return

        geo_org = Organization.objects.filter(
            org_type=OrganizationTypeChoices.govt
        ).first()
        if not geo_org:
            self.stdout.write(
                self.style.ERROR(
                    "No geo organization found. Run load_fixtures first."
                )
            )
            return

        from care.emr.models.organization import FacilityOrganization

        facility_org = FacilityOrganization.objects.first()
        if not facility_org:
            self.stdout.write(
                self.style.ERROR(
                    "No facility organization found. Run load_fixtures first."
                )
            )
            return

        facility = facility_org.facility

        # ── 1. Create Doctor: Dr. Shivani ──────────────────────────
        doctor = self._create_doctor(admin, geo_org, facility_org)

        # ── 2. Create Patient: Devaganesh S ────────────────────────
        patient = self._create_patient(admin, geo_org)

        # ── 3. Create Encounter ────────────────────────────────────
        encounter = self._create_encounter(admin, patient, facility, facility_org)

        # ── 4. Upload reports to MinIO ─────────────────────────────
        self._upload_reports(admin, patient)

        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write("CARE FIXTURES SUMMARY")
        self.stdout.write("=" * 60)
        self.stdout.write(
            f"Doctor:    Dr. {DOCTOR_FIRST_NAME} {DOCTOR_LAST_NAME}"
        )
        self.stdout.write(f"Username:  {DOCTOR_USERNAME}")
        self.stdout.write(f"Password:  {DOCTOR_PASSWORD}")
        self.stdout.write(f"Patient:   {PATIENT_NAME}")
        self.stdout.write(f"ABHA ID:   {PATIENT_ABHA}")
        self.stdout.write(f"Patient UUID: {patient.external_id}")
        self.stdout.write(f"Encounter: {encounter.external_id}")
        self.stdout.write("=" * 60)

    def _create_doctor(self, admin, geo_org, facility_org):
        """Create Dr. Shivani with Doctor role."""
        doctor, created = User.objects.get_or_create(
            username=DOCTOR_USERNAME,
            defaults={
                "first_name": DOCTOR_FIRST_NAME,
                "last_name": DOCTOR_LAST_NAME,
                "user_type": "doctor",
                "phone_number": "+919876543210",
                "email": "dr.shivani@care.local",
                "gender": GenderChoices.female.value,
                "geo_organization": geo_org,
                "created_by": admin,
            },
        )

        if created:
            doctor.set_password(DOCTOR_PASSWORD)
            doctor.save()
            self.stdout.write(f"Created doctor: Dr. {DOCTOR_FIRST_NAME}")

            # Attach Doctor role
            try:
                doctor_role = RoleModel.objects.get(name="Doctor")

                # Attach to facility organization
                FacilityOrganizationUser.objects.get_or_create(
                    organization=facility_org,
                    user=doctor,
                    defaults={"role": doctor_role},
                )

                # Attach to geo organization
                OrganizationUser.objects.get_or_create(
                    organization=geo_org,
                    user=doctor,
                    defaults={"role": doctor_role},
                )

                # Attach to Doctor role organization
                role_org = Organization.objects.filter(
                    name="Doctor", org_type=OrganizationTypeChoices.role
                ).first()
                if role_org:
                    OrganizationUser.objects.get_or_create(
                        organization=role_org,
                        user=doctor,
                        defaults={"role": doctor_role},
                    )

                self.stdout.write("  → Attached Doctor role")
            except RoleModel.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING("  → Doctor role not found, skipping")
                )
        else:
            self.stdout.write(f"Doctor {DOCTOR_USERNAME} already exists")

        return doctor

    def _create_patient(self, admin, geo_org):
        """Create patient Devaganesh S with ABHA ID."""
        import datetime

        patient = Patient.objects.filter(name=PATIENT_NAME).first()
        if patient:
            self.stdout.write(f"Patient {PATIENT_NAME} already exists")
            # Store ABHA in meta if not already there
            if not patient.meta.get("abha_id"):
                patient.meta["abha_id"] = PATIENT_ABHA
                patient.save(update_fields=["meta"])
            return patient

        patient = Patient(
            name=PATIENT_NAME,
            gender=PATIENT_GENDER.value,
            phone_number="+919123456789",
            emergency_phone_number="+919987654321",
            address="123, Medical College Road, Chennai, Tamil Nadu",
            permanent_address="123, Medical College Road, Chennai, Tamil Nadu",
            pincode=600001,
            blood_group=PATIENT_BLOOD_GROUP.value,
            date_of_birth=datetime.date(1998, 3, 15),
            year_of_birth=1998,
            geo_organization=geo_org,
            created_by=admin,
        )
        patient.meta["abha_id"] = PATIENT_ABHA
        patient.save()

        self.stdout.write(f"Created patient: {PATIENT_NAME}")
        self.stdout.write(f"  → ABHA ID: {PATIENT_ABHA}")
        self.stdout.write(f"  → UUID: {patient.external_id}")
        return patient

    def _create_encounter(self, admin, patient, facility, facility_org):
        """Create an encounter for the patient."""
        from care.emr.models import EncounterOrganization

        existing = Encounter.objects.filter(patient=patient, facility=facility).first()
        if existing:
            self.stdout.write(f"Encounter already exists: {existing.external_id}")
            return existing

        encounter = Encounter(
            status=StatusChoices.in_progress.value,
            encounter_class=ClassChoices.imp.value,
            patient=patient,
            facility=facility,
            priority=EncounterPriorityChoices.routine.value,
            created_by=admin,
        )
        encounter.save()

        EncounterOrganization.objects.create(
            encounter=encounter, organization=facility_org
        )

        self.stdout.write(f"Created encounter: {encounter.external_id}")
        return encounter

    def _upload_reports(self, admin, patient):
        """Upload all patient reports from disk to MinIO."""
        from care.emr.utils.file_manager import S3FilesManager

        files_manager = S3FilesManager(BucketType.PATIENT)
        uploaded_count = 0
        skipped_count = 0

        # Mime type mapping
        mime_map = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
            ".txt": "text/plain",
            ".csv": "text/csv",
            ".doc": "application/msword",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }

        # File category mapping
        category_map = {
            "xray": "xray",
            "ct_scan": "xray",
            "progress_report": "discharge_summary",
            "final_report": "discharge_summary",
        }

        for report_dir in REPORT_DIRS:
            dir_path = Path(report_dir)
            if not dir_path.exists():
                self.stdout.write(
                    self.style.WARNING(f"Report dir not found: {report_dir}")
                )
                continue

            hospital_name = dir_path.name  # e.g., "devaganesh-reports-hospital-1"

            for file_path in sorted(dir_path.iterdir()):
                if not file_path.is_file():
                    continue

                # Check if already uploaded
                if FileUpload.objects.filter(
                    name=file_path.name,
                    associating_id=str(patient.external_id),
                ).exists():
                    skipped_count += 1
                    continue

                # Determine mime type
                ext = file_path.suffix.lower()
                mime_type = mime_map.get(ext, "application/octet-stream")

                # Determine category from filename
                fname_lower = file_path.name.lower()
                if "xray" in fname_lower or "x_ray" in fname_lower:
                    file_category = "xray"
                elif "ct_scan" in fname_lower or "ct scan" in fname_lower:
                    file_category = "xray"  # medical imaging
                else:
                    file_category = "unspecified"

                # Create FileUpload record
                file_upload = FileUpload(
                    name=file_path.name,
                    file_type="patient",
                    file_category=file_category,
                    associating_id=str(patient.external_id),
                    upload_completed=True,
                    created_by=admin,
                )
                file_upload.meta["mime_type"] = mime_type
                file_upload.meta["hospital_source"] = hospital_name
                file_upload.meta["original_path"] = str(file_path)
                file_upload.save()

                # Upload to MinIO
                try:
                    with open(file_path, "rb") as f:
                        files_manager.put_object(
                            file_upload,
                            f.read(),
                            ContentType=mime_type,
                        )
                    uploaded_count += 1
                    self.stdout.write(
                        f"  ✓ Uploaded: {file_path.name} ({hospital_name})"
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ✗ Failed to upload {file_path.name}: {e}"
                        )
                    )
                    # Mark as not completed if upload failed
                    file_upload.upload_completed = False
                    file_upload.save(update_fields=["upload_completed"])

        self.stdout.write(f"\nUploaded {uploaded_count} files, skipped {skipped_count}")
