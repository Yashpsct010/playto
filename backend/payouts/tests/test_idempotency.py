"""
Idempotency test for the payout engine.

Tests that:
1. Sending the same idempotency key twice returns the same response.
2. No duplicate payout is created.
3. Different keys create separate payouts.
4. Keys are scoped per merchant.
"""

import uuid
from django.test import TestCase, TransactionTestCase
from django.test.client import Client

from payouts.models import Merchant, BankAccount, LedgerEntry, Payout, IdempotencyRecord


class IdempotencyTest(TransactionTestCase):
    """
    Tests idempotency key behavior for payout requests.
    Uses TransactionTestCase for consistency with the concurrency tests.
    """

    def setUp(self):
        """Create a merchant with enough balance for multiple payouts."""
        self.merchant = Merchant.objects.create(
            name="Idempotency Test Merchant",
            email="test@idempotent.com",
        )
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_number="1234567890123456",
            ifsc_code="TEST0001234",
            account_holder_name="Test User",
        )
        # Seed 50000 paise (₹500)
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type='CREDIT',
            amount_paise=50000,
            description="Test credit for idempotency test",
        )
        self.client = Client()

    def test_duplicate_request_returns_same_response(self):
        """
        Sending the same idempotency key twice should:
        1. Return the exact same response body
        2. Return the same HTTP status code
        3. NOT create a second payout
        """
        idempotency_key = str(uuid.uuid4())
        payload = {
            'merchant_id': str(self.merchant.id),
            'amount_paise': 5000,  # 50₹
            'bank_account_id': str(self.bank_account.id),
        }

        # First request
        response_1 = self.client.post(
            '/api/v1/payouts/',
            data=payload,
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        # Second request with same key
        response_2 = self.client.post(
            '/api/v1/payouts/',
            data=payload,
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )

        # Both should return 201
        self.assertEqual(response_1.status_code, 201)
        self.assertEqual(response_2.status_code, 201)

        # Response bodies should be identical
        self.assertEqual(response_1.json(), response_2.json())

        # Only ONE payout should exist
        payout_count = Payout.objects.filter(
            merchant=self.merchant,
            idempotency_key=idempotency_key,
        ).count()
        self.assertEqual(
            payout_count, 1,
            f"Expected exactly 1 payout for this key, got {payout_count}"
        )

        # Only ONE idempotency record should exist
        record_count = IdempotencyRecord.objects.filter(
            merchant=self.merchant,
            idempotency_key=idempotency_key,
        ).count()
        self.assertEqual(record_count, 1)

    def test_different_keys_create_separate_payouts(self):
        """Different idempotency keys should create separate payouts."""
        key_1 = str(uuid.uuid4())
        key_2 = str(uuid.uuid4())
        payload = {
            'merchant_id': str(self.merchant.id),
            'amount_paise': 5000,
            'bank_account_id': str(self.bank_account.id),
        }

        response_1 = self.client.post(
            '/api/v1/payouts/',
            data=payload,
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=key_1,
        )
        response_2 = self.client.post(
            '/api/v1/payouts/',
            data=payload,
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=key_2,
        )

        self.assertEqual(response_1.status_code, 201)
        self.assertEqual(response_2.status_code, 201)

        # Should be DIFFERENT payouts
        self.assertNotEqual(response_1.json()['id'], response_2.json()['id'])

        # Two payouts should exist
        payout_count = Payout.objects.filter(merchant=self.merchant).count()
        self.assertEqual(payout_count, 2)

    def test_missing_idempotency_key_rejected(self):
        """Requests without Idempotency-Key header should be rejected."""
        payload = {
            'merchant_id': str(self.merchant.id),
            'amount_paise': 5000,
            'bank_account_id': str(self.bank_account.id),
        }

        response = self.client.post(
            '/api/v1/payouts/',
            data=payload,
            content_type='application/json',
            # No Idempotency-Key header
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_keys_scoped_per_merchant(self):
        """
        Same idempotency key used by different merchants should
        create separate payouts (keys are merchant-scoped).
        """
        # Create a second merchant
        merchant_2 = Merchant.objects.create(
            name="Second Merchant",
            email="second@test.com",
        )
        bank_2 = BankAccount.objects.create(
            merchant=merchant_2,
            account_number="9999888877776666",
            ifsc_code="TEST0005678",
            account_holder_name="Second User",
        )
        LedgerEntry.objects.create(
            merchant=merchant_2,
            entry_type='CREDIT',
            amount_paise=50000,
            description="Credit for merchant 2",
        )

        shared_key = str(uuid.uuid4())

        # Merchant 1 uses the key
        r1 = self.client.post(
            '/api/v1/payouts/',
            data={
                'merchant_id': str(self.merchant.id),
                'amount_paise': 5000,
                'bank_account_id': str(self.bank_account.id),
            },
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=shared_key,
        )

        # Merchant 2 uses the SAME key
        r2 = self.client.post(
            '/api/v1/payouts/',
            data={
                'merchant_id': str(merchant_2.id),
                'amount_paise': 5000,
                'bank_account_id': str(bank_2.id),
            },
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY=shared_key,
        )

        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertNotEqual(r1.json()['id'], r2.json()['id'])
