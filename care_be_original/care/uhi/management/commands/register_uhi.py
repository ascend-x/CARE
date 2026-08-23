import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from care.facility.models import Facility


class Command(BaseCommand):
    help = "Registers the primary facility with the UHI Switch Server"

    def handle(self, *args, **options):
        uhi_url = getattr(settings, "UHI_SWITCH_URL", None)
        if not uhi_url:
            self.stdout.write(self.style.ERROR("UHI_SWITCH_URL not set in settings."))
            return

        # Attempt to find the main facility to register
        facility = Facility.objects.first()
        if not facility:
            self.stdout.write(self.style.ERROR("No facilities found to register. Please load fixtures first."))
            return

        payload = {
            "name": facility.name,
            "endpoint_url": "http://10.0.2.2:9000",  # Android emulator localhost wrapper, or the domain of care_be
            "city": facility.district.name if hasattr(facility, "district") and facility.district else "Unknown City",
            "state": facility.state.name if hasattr(facility, "state") and facility.state else "Unknown State",
        }

        self.stdout.write(f"Registering facility '{facility.name}' with UHI Switch at {uhi_url}/hospital/register ...")
        
        try:
            response = requests.post(f"{uhi_url}/hospital/register", json=payload, timeout=10)
            if response.status_code == 200:
                self.stdout.write(self.style.SUCCESS(f"Successfully registered hospital: {response.json()}"))
            else:
                self.stdout.write(self.style.ERROR(f"Failed to register. Status: {response.status_code}, Response: {response.text}"))
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f"Error communicating with UHI Switch: {e}"))
