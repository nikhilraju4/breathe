from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import Tenant, TenantMembership
from ingest.services import ingest_file

User = get_user_model()
SAMPLE_DIR = Path(__file__).resolve().parents[4] / "sample_data"


class Command(BaseCommand):
    help = "Seed demo tenant, analyst user, and sample ingestions"

    def handle(self, *args, **options):
        tenant, _ = Tenant.objects.get_or_create(
            slug="acme-corp",
            defaults={"name": "Acme Corporation (Demo)"},
        )
        user, created = User.objects.get_or_create(
            username="analyst",
            defaults={"email": "analyst@acme.demo", "first_name": "Jordan", "last_name": "Lee"},
        )
        if created:
            user.set_password("demo1234")
            user.save()
            self.stdout.write("Created analyst / demo1234")
        TenantMembership.objects.get_or_create(user=user, tenant=tenant, defaults={"role": "analyst"})

        if tenant.batches.exists():
            self.stdout.write(self.style.WARNING("Demo data already loaded — skipping ingest."))
            self.stdout.write(self.style.SUCCESS("Login: analyst / demo1234"))
            return

        files = [
            ("sap", "sap_fuel_procurement_export.csv"),
            ("utility", "utility_portal_electricity.csv"),
            ("travel", "concur_travel_export.csv"),
        ]
        for source, filename in files:
            path = SAMPLE_DIR / filename
            if not path.exists():
                self.stderr.write(f"Missing {path}")
                continue
            content = path.read_text(encoding="utf-8")
            batch = ingest_file(tenant, source, content, filename, user)
            self.stdout.write(f"Ingested {filename}: {batch.success_count} rows, status={batch.status}")

        self.stdout.write(self.style.SUCCESS("Demo data ready. Login: analyst / demo1234"))
