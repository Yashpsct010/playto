"""
Business logic for the payout engine.

All balance calculations use database-level aggregation (never Python arithmetic
on fetched rows). Payout creation uses select_for_update() to serialize
concurrent requests per merchant.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Sum, Case, When, Value, BigIntegerField
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.conf import settings

from .models import Merchant, LedgerEntry, BankAccount, Payout, IdempotencyRecord

logger = logging.getLogger(__name__)


class InsufficientBalance(Exception):
    """Raised when merchant doesn't have enough available balance."""
    pass


class InvalidBankAccount(Exception):
    """Raised when bank account doesn't belong to merchant."""
    pass


def compute_merchant_balance(merchant_id):
    """
    Compute merchant balance entirely at the database level.

    Returns dict with:
        - total_balance: SUM(CREDIT) - SUM(DEBIT) in paise
        - held_balance: SUM(HOLD) - SUM(RELEASE) in paise
        - available_balance: total_balance - held_balance in paise

    Uses Django ORM's conditional aggregation which translates to a single
    SQL query with CASE/WHEN expressions — no Python arithmetic on fetched rows.
    """
    result = LedgerEntry.objects.filter(
        merchant_id=merchant_id
    ).aggregate(
        total_credits=Coalesce(
            Sum(
                Case(
                    When(entry_type='CREDIT', then='amount_paise'),
                    default=Value(0),
                    output_field=BigIntegerField(),
                )
            ),
            Value(0),
            output_field=BigIntegerField(),
        ),
        total_debits=Coalesce(
            Sum(
                Case(
                    When(entry_type='DEBIT', then='amount_paise'),
                    default=Value(0),
                    output_field=BigIntegerField(),
                )
            ),
            Value(0),
            output_field=BigIntegerField(),
        ),
        total_holds=Coalesce(
            Sum(
                Case(
                    When(entry_type='HOLD', then='amount_paise'),
                    default=Value(0),
                    output_field=BigIntegerField(),
                )
            ),
            Value(0),
            output_field=BigIntegerField(),
        ),
        total_releases=Coalesce(
            Sum(
                Case(
                    When(entry_type='RELEASE', then='amount_paise'),
                    default=Value(0),
                    output_field=BigIntegerField(),
                )
            ),
            Value(0),
            output_field=BigIntegerField(),
        ),
    )

    total_balance = result['total_credits'] - result['total_debits']
    held_balance = result['total_holds'] - result['total_releases']
    available_balance = total_balance - held_balance

    return {
        'total_balance_paise': total_balance,
        'held_balance_paise': held_balance,
        'available_balance_paise': available_balance,
    }


def check_idempotency(merchant_id, idempotency_key):
    """
    Check if we've already processed a request with this idempotency key.

    Returns the cached (status_code, response_body) tuple if found and not expired,
    or None if the key is new or expired.
    """
    expiry_hours = settings.PAYOUT_CONFIG['IDEMPOTENCY_KEY_EXPIRY_HOURS']
    cutoff = timezone.now() - timedelta(hours=expiry_hours)

    try:
        record = IdempotencyRecord.objects.get(
            merchant_id=merchant_id,
            idempotency_key=idempotency_key,
        )
        if record.created_at < cutoff:
            # Key has expired — delete it and treat as new
            record.delete()
            return None
        return (record.response_status, record.response_body)
    except IdempotencyRecord.DoesNotExist:
        return None


def create_payout(merchant_id, amount_paise, bank_account_id, idempotency_key):
    """
    Create a payout request with full concurrency protection.

    This is the critical money-moving operation. The flow:
    1. Acquire a row-level lock on the Merchant row (select_for_update).
    2. Compute available balance via DB aggregation.
    3. If sufficient, atomically create the Payout + HOLD ledger entry.
    4. Cache the response in IdempotencyRecord.
    5. Dispatch the background processing task.

    The select_for_update() lock on Merchant ensures that two concurrent
    requests for the same merchant are serialized — the second request
    blocks until the first commits, then sees the updated balance.

    Raises:
        InsufficientBalance: If available balance < requested amount.
        InvalidBankAccount: If bank account doesn't belong to merchant.
        Merchant.DoesNotExist: If merchant not found.
    """
    with transaction.atomic():
        # Step 1: Lock the merchant row.
        # Any concurrent transaction trying to lock the same merchant
        # will BLOCK here until this transaction commits or rolls back.
        # This is the PostgreSQL row-level exclusive lock that prevents
        # the race condition where two 60₹ requests pass a 100₹ balance check.
        merchant = Merchant.objects.select_for_update().get(id=merchant_id)

        # Step 2: Validate bank account belongs to this merchant
        try:
            bank_account = BankAccount.objects.get(
                id=bank_account_id, merchant=merchant
            )
        except BankAccount.DoesNotExist:
            raise InvalidBankAccount(
                f"Bank account {bank_account_id} does not belong to merchant {merchant_id}"
            )

        # Step 3: Compute available balance using DB aggregation.
        # This runs inside the transaction AFTER acquiring the lock,
        # so we're guaranteed to see the latest committed state.
        balances = compute_merchant_balance(merchant_id)
        available = balances['available_balance_paise']

        if available < amount_paise:
            raise InsufficientBalance(
                f"Insufficient balance. Available: {available} paise, "
                f"Requested: {amount_paise} paise."
            )

        # Step 4: Create the payout record
        payout = Payout.objects.create(
            merchant=merchant,
            bank_account=bank_account,
            amount_paise=amount_paise,
            status='PENDING',
            idempotency_key=idempotency_key,
        )

        # Step 5: Create HOLD ledger entry to reserve the funds
        LedgerEntry.objects.create(
            merchant=merchant,
            entry_type='HOLD',
            amount_paise=amount_paise,
            description=f"Funds held for payout {payout.id}",
            reference_id=payout.id,
        )

        # Step 6: Build the response data (will be cached for idempotency)
        response_data = {
            'id': str(payout.id),
            'merchant_id': str(merchant.id),
            'bank_account_id': str(bank_account.id),
            'amount_paise': payout.amount_paise,
            'status': payout.status,
            'idempotency_key': payout.idempotency_key,
            'created_at': payout.created_at.isoformat(),
        }

        # Step 7: Cache the response for idempotency
        IdempotencyRecord.objects.create(
            merchant=merchant,
            idempotency_key=idempotency_key,
            response_status=201,
            response_body=response_data,
        )

    # Step 8: Dispatch background task AFTER the transaction commits.
    # We import here to avoid circular imports and ensure the task
    # only fires after the DB has committed the payout.
    from .tasks import process_payout
    process_payout.delay(str(payout.id))

    logger.info(
        f"Payout {payout.id} created for merchant {merchant_id}, "
        f"amount: {amount_paise} paise. Background task dispatched."
    )

    return (201, response_data)
