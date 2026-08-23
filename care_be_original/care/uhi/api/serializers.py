from rest_framework import serializers
from care.uhi.models import UHIConsent


class UHIConsentWebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = UHIConsent
        fields = [
            "consent_id",
            "patient_abha_id",
            "hospital_id",
            "status",
            "purpose",
            "permissions",
            "granted_at",
            "expires_at",
            "is_emergency",
        ]
