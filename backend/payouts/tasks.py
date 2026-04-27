"""
Celery tasks for the payout processing engine.

process_payout: Picks up a pending payout, simulates bank settlement,
                and transitions to COMPLETED or FAILED.

sweep_stuck_payouts: Periodic task that finds payouts stuck in PROCESSING
                     state beyond the threshold and retries or fails them.
"""

import random
import logging
import time

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
)
def process_payout(self, payout_id):
    """
    Process a single payout through the bank settlement simulation.

    Settlement outcomes (simulated):
    - 70% chance: SUCCESS → payout completed, funds debited
    - 20% chance: FAILURE → payout failed, held funds released
    - 10% chance: HANG → simulates a timeout, triggers retry

    On success: PROCESSING → COMPLETED + DEBIT entry + RELEASE entry (atomically)
    On failure: PROCESSING → FAILED + RELEASE entry (atomically)
    On hang: Task exceeds timeout, Celery retries with exponential backoff
    """
    from .models import Payout, LedgerEntry

    logger.info(f"Processing payout {payout_id}, attempt {self.request.retries + 1}")

    try:
        with transaction.atomic():
            # Lock the payout row to prevent concurrent processing
            try:
                payout = Payout.objects.select_for_update(nowait=True).get(id=payout_id)
            except Payout.DoesNotExist:
                logger.error(f"Payout {payout_id} not found")
                return
            except Exception:
                # Row is already locked by another worker — skip
                logger.info(f"Payout {payout_id} is locked by another worker, skipping")
                return

            # Only process payouts that are PENDING or PROCESSING (retry)
            if payout.status not in ('PENDING', 'PROCESSING'):
                logger.info(
                    f"Payout {payout_id} is in {payout.status} state, skipping"
                )
                return

            # Transition to PROCESSING if currently PENDING
            if payout.status == 'PENDING':
                payout.transition_to('PROCESSING')

            payout.attempts += 1
            payout.save(update_fields=['attempts', 'updated_at'])

        # Simulate bank API call OUTSIDE the transaction
        # (we don't want to hold the DB lock during external calls)
        outcome = _simulate_bank_settlement()
        logger.info(f"Payout {payout_id} bank simulation result: {outcome}")

        if outcome == 'SUCCESS':
            _complete_payout(payout_id)
        elif outcome == 'FAILURE':
            _fail_payout(payout_id)
        elif outcome == 'HANG':
            # Simulate a hanging bank API — sleep beyond the stuck threshold
            # The sweep_stuck_payouts task will pick this up and retry
            logger.warning(f"Payout {payout_id} simulating bank hang...")
            time.sleep(35)  # Exceeds the 30s stuck threshold
            # After the sleep, re-check if the payout is still in PROCESSING
            # (sweep might have already handled it)
            payout.refresh_from_db()
            if payout.status == 'PROCESSING':
                # Still hanging — will be picked up by sweep
                logger.warning(f"Payout {payout_id} still in PROCESSING after hang")

    except Exception as exc:
        logger.exception(f"Error processing payout {payout_id}: {exc}")
        # Retry with exponential backoff: 5s, 10s, 20s
        retry_delay = (2 ** self.request.retries) * 5
        raise self.retry(exc=exc, countdown=retry_delay)


def _simulate_bank_settlement():
    """
    Simulate bank settlement with realistic outcome distribution.
    Returns: 'SUCCESS' (70%), 'FAILURE' (20%), or 'HANG' (10%)
    """
    roll = random.random()
    if roll < 0.70:
        return 'SUCCESS'
    elif roll < 0.90:
        return 'FAILURE'
    else:
        return 'HANG'


def _complete_payout(payout_id):
    """
    Mark payout as COMPLETED and record the debit + release in the ledger.
    All done atomically in a single transaction.
    """
    from .models import Payout, LedgerEntry

    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)

        if payout.status != 'PROCESSING':
            logger.warning(
                f"Payout {payout_id} not in PROCESSING state "
                f"(is {payout.status}), skipping completion"
            )
            return

        # Transition to COMPLETED (state machine validates this)
        payout.transition_to('COMPLETED')

        # DEBIT: Record the actual money leaving the merchant's balance
        LedgerEntry.objects.create(
            merchant=payout.merchant,
            entry_type='DEBIT',
            amount_paise=payout.amount_paise,
            description=f"Payout {payout.id} settled to bank",
            reference_id=payout.id,
        )

        # RELEASE: Cancel the hold (since funds are now debited)
        LedgerEntry.objects.create(
            merchant=payout.merchant,
            entry_type='RELEASE',
            amount_paise=payout.amount_paise,
            description=f"Hold released for completed payout {payout.id}",
            reference_id=payout.id,
        )

    logger.info(f"Payout {payout_id} completed successfully")


def _fail_payout(payout_id):
    """
    Mark payout as FAILED and release the held funds back to the merchant.
    The state transition and fund release happen atomically.
    """
    from .models import Payout, LedgerEntry

    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)

        if payout.status != 'PROCESSING':
            logger.warning(
                f"Payout {payout_id} not in PROCESSING state "
                f"(is {payout.status}), skipping failure"
            )
            return

        # Transition to FAILED (state machine validates this)
        payout.transition_to('FAILED')

        # RELEASE: Return the held funds to the merchant's available balance
        LedgerEntry.objects.create(
            merchant=payout.merchant,
            entry_type='RELEASE',
            amount_paise=payout.amount_paise,
            description=f"Funds released for failed payout {payout.id}",
            reference_id=payout.id,
        )

    logger.info(f"Payout {payout_id} failed, funds released")


@shared_task
def sweep_stuck_payouts():
    """
    Periodic task (runs every 15s via Celery Beat) that finds payouts
    stuck in PROCESSING state beyond the configured threshold.

    For each stuck payout:
    - If attempts < max_retries: dispatch process_payout to retry
    - If attempts >= max_retries: fail the payout and release funds
    """
    from .models import Payout

    config = settings.PAYOUT_CONFIG
    threshold = timedelta(seconds=config['STUCK_THRESHOLD_SECONDS'])
    max_attempts = config['MAX_RETRY_ATTEMPTS']
    cutoff = timezone.now() - threshold

    stuck_payouts = Payout.objects.filter(
        status='PROCESSING',
        updated_at__lt=cutoff,
    )

    for payout in stuck_payouts:
        if payout.attempts >= max_attempts:
            # Max retries exhausted — fail the payout and release funds
            logger.warning(
                f"Payout {payout.id} exceeded max attempts ({max_attempts}), "
                f"marking as FAILED"
            )
            _fail_payout(str(payout.id))
        else:
            # Retry with exponential backoff
            retry_delay = (2 ** payout.attempts) * 5
            logger.info(
                f"Retrying stuck payout {payout.id} "
                f"(attempt {payout.attempts + 1}/{max_attempts}), "
                f"delay: {retry_delay}s"
            )
            process_payout.apply_async(
                args=[str(payout.id)],
                countdown=retry_delay,
            )
