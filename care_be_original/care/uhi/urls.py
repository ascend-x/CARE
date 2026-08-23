from django.urls import path
from care.uhi.api.viewsets.webhook import UHIConsentWebhookView

app_name = "uhi"

urlpatterns = [
    path("webhook/consent/", UHIConsentWebhookView.as_view(), name="uhi_consent_webhook"),
]
