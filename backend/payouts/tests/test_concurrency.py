"""
Concurrency test for the payout engine.

Tests that when a merchant with 100₹ balance submits two simultaneous
60₹ payout requests, exactly one succeeds and the other is rejected.
This validates that our select_for_update() locking prevents overdraw.

Requires PostgreSQL (SQLite doesn't support row-level locking).
"""

import uuid
import threading
from django.test import TestCase, TransactionTestCase
from django.test.client import Client

from payouts.models import Merchant, BankAccount, LedgerEntry, Payout
from payouts.services import compute_merchant_balance


class ConcurrencyTest(TransactionTestCase):
    """
    TransactionTestCase is required (not TestCase) because:
    - TestCase wraps each test in a transaction, which prevents
      our select_for_update() from actually blocking concurrent access.
    - TransactionTestCase uses real transactions, so the locking
      behavior is identical to production.
    """

    def setUp(self):
        """Create a merchant with exactly 100₹ (10000 paise) balance."""
        self.merchant = Merchant.objects.create(
            name="Test Merchant",
            email="test@concurrent.com",
        )
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_number="1234567890123456",
            ifsc_code="TEST0001234",
            account_holder_name="Test User",
        )
        # Seed exactly 10000 paise (₹100) credit
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type='CREDIT',
            amount_paise=10000,
            description="Test credit for concurrency test",
        )

    def test_concurrent_payouts_prevent_overdraw(self):
        """
        Two threads simultaneously request 60₹ (6000 paise) payouts
        against a 100₹ balance. Exactly one should succeed (201),
        the other should fail (400 insufficient balance).

        This is the critical race condition test: without select_for_update(),
        both threads would read balance=100, both would pass the check,
        and both would create payouts — resulting in -20₹ balance.
        """
        client = Client()
        results = {'thread_1': None, 'thread_2': None}

        def make_payout(thread_name, idempotency_key):
            """Each thread makes a payout request with a unique idempotency key."""
            response = client.post(
                '/api/v1/payouts/',
                data={
                    'merchant_id': str(self.merchant.id),
                    'amount_paise': 6000,  # 60₹
                    'bank_account_id': str(self.bank_account.id),
                },
                content_type='application/json',
                HTTP_IDEMPOTENCY_KEY=idempotency_key,
            )
            results[thread_name] = response.status_code

        key_1 = str(uuid.uuid4())
        key_2 = str(uuid.uuid4())

        t1 = threading.Thread(target=make_payout, args=('thread_1', key_1))
        t2 = threading.Thread(target=make_payout, args=('thread_2', key_2))

        # Start both threads as close together as possible
        t1.start()
        t2.start()

        t1.join(timeout=10)
        t2.join(timeout=10)

        # Exactly one should succeed (201) and one should fail (400)
        status_codes = sorted([results['thread_1'], results['thread_2']])
        self.assertEqual(
            status_codes, [201, 400],
            f"Expected exactly one 201 and one 400, got {results}"
        )

        # Verify only ONE payout was created
        payout_count = Payout.objects.filter(merchant=self.merchant).count()
        self.assertEqual(
            payout_count, 1,
            f"Expected exactly 1 payout, got {payout_count}"
        )

        # Verify balance invariant:
        # Started with 10000, one 6000 hold → available should be 4000
        balance = compute_merchant_balance(self.merchant.id)
        self.assertEqual(
            balance['available_balance_paise'], 4000,
            f"Expected available balance of 4000 paise, got {balance}"
        )

        # Verify total balance hasn't changed (no money created or destroyed)
        self.assertEqual(
            balance['total_balance_paise'], 10000,
            f"Total balance should still be 10000 paise"
        )
