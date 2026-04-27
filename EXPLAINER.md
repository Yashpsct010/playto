# EXPLAINER.md

Answers to the five grading questions for the Playto Founding Engineer Challenge.

---

## 1. The Ledger

**Balance calculation query (Django ORM → SQL):**

```python
# backend/payouts/services.py — compute_merchant_balance()

result = LedgerEntry.objects.filter(
    merchant_id=merchant_id
).aggregate(
    total_credits=Coalesce(
        Sum(Case(When(entry_type='CREDIT', then='amount_paise'),
                 default=Value(0), output_field=BigIntegerField())),
        Value(0), output_field=BigIntegerField(),
    ),
    total_debits=Coalesce(
        Sum(Case(When(entry_type='DEBIT', then='amount_paise'),
                 default=Value(0), output_field=BigIntegerField())),
        Value(0), output_field=BigIntegerField(),
    ),
    total_holds=Coalesce(
        Sum(Case(When(entry_type='HOLD', then='amount_paise'),
                 default=Value(0), output_field=BigIntegerField())),
        Value(0), output_field=BigIntegerField(),
    ),
    total_releases=Coalesce(
        Sum(Case(When(entry_type='RELEASE', then='amount_paise'),
                 default=Value(0), output_field=BigIntegerField())),
        Value(0), output_field=BigIntegerField(),
    ),
)

total_balance = result['total_credits'] - result['total_debits']
held_balance = result['total_holds'] - result['total_releases']
available_balance = total_balance - held_balance
```

This translates to a single SQL query:

```sql
SELECT
  COALESCE(SUM(CASE WHEN entry_type='CREDIT' THEN amount_paise ELSE 0 END), 0)
  - COALESCE(SUM(CASE WHEN entry_type='DEBIT' THEN amount_paise ELSE 0 END), 0)
  AS total_balance,
  COALESCE(SUM(CASE WHEN entry_type='HOLD' THEN amount_paise ELSE 0 END), 0)
  - COALESCE(SUM(CASE WHEN entry_type='RELEASE' THEN amount_paise ELSE 0 END), 0)
  AS held_balance
FROM ledger_entries WHERE merchant_id = %s;
```

**Why this model:**

I chose four entry types (CREDIT, DEBIT, HOLD, RELEASE) instead of just credit/debit because payout lifecycle requires a two-phase commit pattern:

1. When a payout is requested: create a HOLD entry (reserves funds, reduces available balance)
2. When payout succeeds: create a DEBIT entry (money leaves) + RELEASE entry (cancels the hold)
3. When payout fails: create only a RELEASE entry (funds return to available)

This means the **balance is never stored** on the Merchant model — it's always derived from the ledger via the aggregation query above. There's no "balance" column that can drift out of sync. The ledger IS the source of truth, and the invariant `SUM(credits) - SUM(debits) = total_balance` is mathematically guaranteed by the append-only nature of the ledger.

All amounts are `BigIntegerField` in paise. No floats, no decimals. 1 INR = 100 paise. This avoids all floating-point precision issues that plague payment systems.

---

## 2. The Lock

**The exact code that prevents concurrent overdraw:**

```python
# backend/payouts/services.py — create_payout()

with transaction.atomic():
    # THIS IS THE LOCK.
    # select_for_update() acquires a PostgreSQL row-level exclusive lock
    # (FOR UPDATE) on the merchant row. Any other transaction trying to
    # lock the same merchant will BLOCK here until this transaction
    # commits or rolls back.
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)

    # Now compute balance — safe because we hold the lock
    balances = compute_merchant_balance(merchant_id)
    available = balances['available_balance_paise']

    if available < amount_paise:
        raise InsufficientBalance(...)

    # Create payout + HOLD entry atomically
    payout = Payout.objects.create(...)
    LedgerEntry.objects.create(entry_type='HOLD', ...)
```

**Database primitive:** PostgreSQL's `SELECT ... FOR UPDATE`. This acquires an exclusive row-level lock in the database. It's pessimistic locking — the second transaction physically waits at the database level (not in Python) until the first transaction releases the lock by committing or rolling back.

**Why I lock the Merchant row (not the LedgerEntry rows):** The LedgerEntry table is append-only — we never update existing rows. What we need to serialize is the check-then-insert sequence: "read balance, verify sufficient, insert hold." By locking the Merchant row, we create a serialization point — all concurrent payout requests for the same merchant queue up at this lock. The balance check inside the lock always sees the latest committed state.

**The scenario: Two 60₹ requests against 100₹ balance:**
1. Thread A acquires the lock on the merchant row.
2. Thread B tries to acquire the same lock — PostgreSQL blocks it at the database level.
3. Thread A computes balance (100₹ available), creates payout + hold, commits. Lock released.
4. Thread B unblocks, acquires the lock, computes balance (now 40₹ available), rejects the 60₹ request.

---

## 3. The Idempotency

**How the system knows it has seen a key before:**

There's an `IdempotencyRecord` model with a unique constraint on `(merchant_id, idempotency_key)`. Before the payout creation logic runs, we check this table:

```python
# backend/payouts/services.py — check_idempotency()

record = IdempotencyRecord.objects.get(
    merchant_id=merchant_id,
    idempotency_key=idempotency_key,
)
if record.created_at < cutoff:  # 24h expiry
    record.delete()
    return None  # Expired, treat as new
return (record.response_status, record.response_body)
```

When a payout is successfully created, we store the full serialized response in `IdempotencyRecord` inside the same transaction:

```python
IdempotencyRecord.objects.create(
    merchant=merchant,
    idempotency_key=idempotency_key,
    response_status=201,
    response_body=response_data,
)
```

**What happens if the first request is in-flight when the second arrives:**

This is naturally handled by the `select_for_update()` lock on the Merchant row. Both requests will try to lock the same merchant:

1. Request A acquires the merchant lock, starts creating the payout.
2. Request B arrives with the same key, tries to lock the same merchant — blocked at the DB level.
3. Request A finishes: creates Payout + LedgerEntry + IdempotencyRecord, commits.
4. Request B unblocks. In the view, `check_idempotency()` finds the record (it was committed in step 3), returns the cached response.

The key insight is that the idempotency check and the merchant lock naturally serialize the requests. There's no race window where two requests with the same key can both create a payout, because they can't both hold the merchant lock simultaneously.

Keys are scoped per merchant via the unique constraint `(merchant, idempotency_key)`, so different merchants can use the same UUID without collision. Keys expire after 24 hours.

---

## 4. The State Machine

**Where in the code `FAILED → COMPLETED` (and all other backward transitions) are blocked:**

```python
# backend/payouts/models.py — Payout.transition_to()

VALID_TRANSITIONS = {
    'PENDING': ['PROCESSING'],
    'PROCESSING': ['COMPLETED', 'FAILED'],
}
# COMPLETED and FAILED are NOT keys in this dict — they have no valid next states

def transition_to(self, new_status):
    allowed = self.VALID_TRANSITIONS.get(self.status, [])
    if new_status not in allowed:
        raise ValueError(
            f"Illegal state transition: {self.status} → {new_status}. "
            f"Allowed transitions from {self.status}: "
            f"{allowed or 'none (terminal state)'}"
        )
    self.status = new_status
    if new_status in ('COMPLETED', 'FAILED'):
        self.processed_at = timezone.now()
    self.save(update_fields=['status', 'updated_at', 'processed_at'])
```

**How it works:**

- `COMPLETED` and `FAILED` are not keys in `VALID_TRANSITIONS`, so `self.VALID_TRANSITIONS.get('COMPLETED', [])` returns `[]` — no transitions are allowed out of terminal states.
- `PENDING` can only go to `PROCESSING`.
- `PROCESSING` can only go to `COMPLETED` or `FAILED`.
- Any attempt to go backward (e.g., `FAILED → COMPLETED`, `COMPLETED → PENDING`) hits the empty list and raises `ValueError`.

Every state transition in the codebase goes through this method — `_complete_payout()`, `_fail_payout()`, and `process_payout()` all call `payout.transition_to(new_status)`. There's no code path that directly sets `payout.status = 'COMPLETED'` without going through the validation.

Additionally, the atomic transactions in `_fail_payout()` ensure that the state transition to `FAILED` and the `RELEASE` ledger entry (returning funds) happen together or not at all. There's no state where a payout is `FAILED` but the funds aren't released.

---

## 5. The AI Audit

**One specific example where AI wrote subtly wrong code:**

When I first asked AI to implement the payout creation flow, it generated code that computed the balance **outside** the `transaction.atomic()` block:

```python
# ❌ What AI gave me (WRONG):

# Balance computed here — outside the transaction!
balances = compute_merchant_balance(merchant_id)
available = balances['available_balance_paise']

if available < amount_paise:
    raise InsufficientBalance(...)

with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)
    payout = Payout.objects.create(...)
    LedgerEntry.objects.create(entry_type='HOLD', ...)
```

**What's wrong:** The balance check happens BEFORE the lock is acquired. Two concurrent requests can both read `balance = 100`, both pass the `if available < amount_paise` check, and then both enter the transaction and create payouts — classic TOCTOU (Time-of-Check-to-Time-of-Use) race condition. The `select_for_update()` inside the transaction only prevents them from writing simultaneously, but the stale balance read has already happened.

**What I replaced it with:**

```python
# ✅ Corrected version:

with transaction.atomic():
    # Lock FIRST, then compute balance INSIDE the lock
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)

    # Balance computation is now inside the transaction, after the lock
    balances = compute_merchant_balance(merchant_id)
    available = balances['available_balance_paise']

    if available < amount_paise:
        raise InsufficientBalance(...)

    payout = Payout.objects.create(...)
    LedgerEntry.objects.create(entry_type='HOLD', ...)
```

The fix is structurally simple but critically important: move the balance computation **inside** the `transaction.atomic()` block, **after** `select_for_update()`. Now the balance is read while holding the exclusive lock, so it's guaranteed to reflect the latest committed state. The second concurrent request blocks at `select_for_update()` until the first one commits, then re-reads the balance with the updated data.

This is exactly the kind of bug that passes all unit tests (because tests typically run sequentially) but fails catastrophically under real concurrent load. The AI-generated code "looked right" — it used `select_for_update()`, it used `transaction.atomic()`, it checked the balance — but the ordering was subtly wrong and would have allowed double-spending in production.
