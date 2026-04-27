"""
Payout engine models.

Design decisions:
- All money amounts stored as BigIntegerField in paise (1 INR = 100 paise). Never floats.
- No stored balance on Merchant — balance is always derived from ledger entries via DB aggregation.
- Payout has a state machine with strict transition validation.
- IdempotencyRecord caches full API responses, scoped per merchant, with 24h expiry.
"""

import uuid
from django.db import models
from django.utils import timezone


class Merchant(models.Model):
    """
    A merchant who receives payments and requests payouts.
    Balance is NOT stored here — it's derived from LedgerEntry aggregation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'merchants'
        ordering = ['name']

    def __str__(self):
        return self.name


class BankAccount(models.Model):
    """
    Merchant's Indian bank account for receiving payouts.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name='bank_accounts'
    )
    account_number = models.CharField(max_length=20)
    ifsc_code = models.CharField(max_length=11)
    account_holder_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bank_accounts'

    def __str__(self):
        # Mask account number for display: show last 4 digits
        masked = 'X' * (len(self.account_number) - 4) + self.account_number[-4:]
        return f"{self.account_holder_name} - {masked}"


class LedgerEntry(models.Model):
    """
    Immutable ledger entry representing a financial event.

    Entry types:
    - CREDIT: Money added to merchant balance (customer payment)
    - DEBIT: Money removed from merchant balance (successful payout settlement)
    - HOLD: Funds reserved for a pending payout (reduces available balance)
    - RELEASE: Held funds returned (payout failed or cancelled)

    Invariant:
        available_balance = SUM(CREDIT) - SUM(DEBIT) - (SUM(HOLD) - SUM(RELEASE))
    """
    ENTRY_TYPE_CHOICES = [
        ('CREDIT', 'Credit'),
        ('DEBIT', 'Debit'),
        ('HOLD', 'Hold'),
        ('RELEASE', 'Release'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name='ledger_entries'
    )
    entry_type = models.CharField(max_length=7, choices=ENTRY_TYPE_CHOICES)
    amount_paise = models.BigIntegerField(
        help_text="Amount in paise (always positive). 1 INR = 100 paise."
    )
    description = models.CharField(max_length=500)
    reference_id = models.UUIDField(
        null=True, blank=True, db_index=True,
        help_text="Links to Payout ID or external payment reference."
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'ledger_entries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['merchant', 'entry_type']),
            models.Index(fields=['merchant', '-created_at']),
        ]

    def __str__(self):
        return f"{self.entry_type} ₹{self.amount_paise / 100:.2f} - {self.description}"


class Payout(models.Model):
    """
    A payout request from a merchant to their bank account.
    Follows a strict state machine: PENDING → PROCESSING → COMPLETED | FAILED.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    # Valid state transitions — terminal states (COMPLETED, FAILED) have no exits
    VALID_TRANSITIONS = {
        'PENDING': ['PROCESSING'],
        'PROCESSING': ['COMPLETED', 'FAILED'],
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name='payouts'
    )
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.PROTECT, related_name='payouts'
    )
    amount_paise = models.BigIntegerField(
        help_text="Payout amount in paise."
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='PENDING', db_index=True
    )
    attempts = models.IntegerField(
        default=0,
        help_text="Number of processing attempts. Max 3 before marking as FAILED."
    )
    idempotency_key = models.CharField(
        max_length=255,
        help_text="Merchant-supplied UUID for request deduplication."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Timestamp when payout reached terminal state."
    )

    class Meta:
        db_table = 'payouts'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['merchant', 'idempotency_key'],
                name='unique_merchant_idempotency_key'
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'updated_at']),
            models.Index(fields=['merchant', '-created_at']),
        ]

    def __str__(self):
        return f"Payout {self.id} - ₹{self.amount_paise / 100:.2f} [{self.status}]"

    def transition_to(self, new_status):
        """
        Enforce the state machine. Only allows valid transitions.
        Raises ValueError for any illegal transition (e.g., COMPLETED → PENDING,
        FAILED → COMPLETED).

        This is THE check that prevents backward/illegal state changes.
        """
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Illegal state transition: {self.status} → {new_status}. "
                f"Allowed transitions from {self.status}: {allowed or 'none (terminal state)'}"
            )
        self.status = new_status
        if new_status in ('COMPLETED', 'FAILED'):
            self.processed_at = timezone.now()
        self.save(update_fields=['status', 'updated_at', 'processed_at'])


class IdempotencyRecord(models.Model):
    """
    Stores API responses keyed by (merchant, idempotency_key).
    Used to return the exact same response for duplicate requests.
    Keys expire after 24 hours.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name='idempotency_records'
    )
    idempotency_key = models.CharField(max_length=255)
    response_status = models.IntegerField(help_text="HTTP status code of cached response.")
    response_body = models.JSONField(help_text="Serialized JSON response body.")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'idempotency_records'
        constraints = [
            models.UniqueConstraint(
                fields=['merchant', 'idempotency_key'],
                name='unique_idempotency_per_merchant'
            ),
        ]

    def __str__(self):
        return f"Idempotency {self.idempotency_key} for {self.merchant_id}"
