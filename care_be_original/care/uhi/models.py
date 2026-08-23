import uuid
from django.db import models
from care.utils.models.base import BaseModel


class UHIConsent(BaseModel):
    class Status(models.TextChoices):
        GRANTED = "GRANTED"
        REVOKED = "REVOKED"
        EXPIRED = "EXPIRED"

    consent_id = models.CharField(max_length=255, unique=True, db_index=True)
    patient_abha_id = models.CharField(max_length=255, db_index=True)
    hospital_id = models.CharField(max_length=255, db_index=True)
    status = models.CharField(max_length=50, choices=Status.choices, default=Status.GRANTED)
    purpose = models.CharField(max_length=255, null=True, blank=True)
    permissions = models.JSONField(default=list)
    granted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_emergency = models.BooleanField(default=False)

    class Meta:
        verbose_name = "UHI Consent"
        verbose_name_plural = "UHI Consents"

    def __str__(self):
        return f"{self.patient_abha_id} - {self.hospital_id} ({self.status})"
