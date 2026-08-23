from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema

from care.uhi.api.serializers import UHIConsentWebhookSerializer
from care.uhi.models import UHIConsent


class UHIConsentWebhookView(APIView):
    permission_classes = [AllowAny]
    
    @extend_schema(request=UHIConsentWebhookSerializer)
    def post(self, request, *args, **kwargs):
        consent_id = request.data.get("consent_id")
        if not consent_id:
            return Response({"error": "consent_id required"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            consent = UHIConsent.objects.get(consent_id=consent_id)
            serializer = UHIConsentWebhookSerializer(consent, data=request.data, partial=True)
        except UHIConsent.DoesNotExist:
            serializer = UHIConsentWebhookSerializer(data=request.data)
            
        if serializer.is_valid():
            serializer.save()
            return Response({"status": "success"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
