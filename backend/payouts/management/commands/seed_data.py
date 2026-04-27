"""
Seed script to populate the database with test merchants, bank accounts,
and credit history for development and demonstration.

Usage: python manage.py seed_data
"""

import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from payouts.models import Merchant, BankAccount, LedgerEntry


class Command(BaseCommand):
    help = 'Seed the database with test merchants, bank accounts, and credit history'

    def handle(self, *args, **options):
        self.stdout.write('Seeding database...\n')

        # Clear existing data (idempotent re-seeding)
        LedgerEntry.objects.all().delete()
        from payouts.models import Payout, IdempotencyRecord
        Payout.objects.all().delete()
        IdempotencyRecord.objects.all().delete()
        BankAccount.objects.all().delete()
        Merchant.objects.all().delete()

        now = timezone.now()

        # ─── Merchant 1: Priya's Design Studio ───
        m1 = Merchant.objects.create(
            name="Priya's Design Studio",
            email="priya@designstudio.in",
        )
        b1 = BankAccount.objects.create(
            merchant=m1,
            account_number="1234567890123456",
            ifsc_code="HDFC0001234",
            account_holder_name="Priya Sharma",
        )
        # Credit history: 5 payments over the last 2 weeks
        credits_m1 = [
            (5000_00, "Payment from Acme Corp (Invoice #1001)", now - timedelta(days=14)),
            (3500_00, "Payment from GlobalTech (Invoice #1002)", now - timedelta(days=10)),
            (7500_00, "Payment from StartupXYZ (Invoice #1003)", now - timedelta(days=7)),
            (2000_00, "Payment from DesignCo (Invoice #1004)", now - timedelta(days=3)),
            (4500_00, "Payment from WebAgency (Invoice #1005)", now - timedelta(days=1)),
        ]
        for amount, desc, ts in credits_m1:
            entry = LedgerEntry.objects.create(
                merchant=m1,
                entry_type='CREDIT',
                amount_paise=amount,
                description=desc,
                reference_id=uuid.uuid4(),
            )
            # Manually set created_at for realistic history
            LedgerEntry.objects.filter(id=entry.id).update(created_at=ts)

        self.stdout.write(
            self.style.SUCCESS(
                f"  ✓ {m1.name}: ₹{sum(c[0] for c in credits_m1)/100:,.2f} "
                f"across {len(credits_m1)} credits"
            )
        )

        # ─── Merchant 2: Raj's Software Solutions ───
        m2 = Merchant.objects.create(
            name="Raj's Software Solutions",
            email="raj@rajsoft.in",
        )
        b2 = BankAccount.objects.create(
            merchant=m2,
            account_number="9876543210987654",
            ifsc_code="ICIC0005678",
            account_holder_name="Raj Patel",
        )
        credits_m2 = [
            (15000_00, "Payment from Enterprise Inc (Project Alpha)", now - timedelta(days=20)),
            (8000_00, "Payment from TechStartup (API Integration)", now - timedelta(days=12)),
            (12000_00, "Payment from DataFlow Corp (Dashboard Build)", now - timedelta(days=5)),
            (6500_00, "Payment from CloudNine (Backend Module)", now - timedelta(days=2)),
        ]
        for amount, desc, ts in credits_m2:
            entry = LedgerEntry.objects.create(
                merchant=m2,
                entry_type='CREDIT',
                amount_paise=amount,
                description=desc,
                reference_id=uuid.uuid4(),
            )
            LedgerEntry.objects.filter(id=entry.id).update(created_at=ts)

        self.stdout.write(
            self.style.SUCCESS(
                f"  ✓ {m2.name}: ₹{sum(c[0] for c in credits_m2)/100:,.2f} "
                f"across {len(credits_m2)} credits"
            )
        )

        # ─── Merchant 3: Ananya Freelance Writing ───
        m3 = Merchant.objects.create(
            name="Ananya Freelance Writing",
            email="ananya@freelancewrite.in",
        )
        b3 = BankAccount.objects.create(
            merchant=m3,
            account_number="5555666677778888",
            ifsc_code="SBIN0009012",
            account_holder_name="Ananya Iyer",
        )
        b3_alt = BankAccount.objects.create(
            merchant=m3,
            account_number="1111222233334444",
            ifsc_code="AXIS0003456",
            account_holder_name="Ananya Iyer",
        )
        credits_m3 = [
            (1500_00, "Payment from BlogMedia (Article Batch #1)", now - timedelta(days=30)),
            (2200_00, "Payment from ContentKing (SEO Articles)", now - timedelta(days=18)),
            (3000_00, "Payment from NewsDaily (Feature Story)", now - timedelta(days=8)),
        ]
        for amount, desc, ts in credits_m3:
            entry = LedgerEntry.objects.create(
                merchant=m3,
                entry_type='CREDIT',
                amount_paise=amount,
                description=desc,
                reference_id=uuid.uuid4(),
            )
            LedgerEntry.objects.filter(id=entry.id).update(created_at=ts)

        self.stdout.write(
            self.style.SUCCESS(
                f"  ✓ {m3.name}: ₹{sum(c[0] for c in credits_m3)/100:,.2f} "
                f"across {len(credits_m3)} credits"
            )
        )

        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Seeded {Merchant.objects.count()} merchants, "
            f"{BankAccount.objects.count()} bank accounts, "
            f"{LedgerEntry.objects.count()} ledger entries."
        ))
