# Playto Payout Engine

A minimal but production-grade payout engine for Playto Pay, where merchants can view their balance, request payouts, and track payout status. Built for the Founding Engineer Challenge 2026.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
│  React + Tailwind│────▶│ Django + DRF │────▶│  PostgreSQL  │
│  (Vite SPA)      │     │  (REST API)  │     │  (Data)      │
└─────────────────┘     └──────┬───────┘     └──────────────┘
                               │
                        ┌──────▼───────┐     ┌──────────────┐
                        │ Celery Worker│────▶│    Redis      │
                        │ Celery Beat  │     │  (Broker)     │
                        └──────────────┘     └──────────────┘
```

## Quick Start (Docker)

The fastest way to get everything running:

```bash
docker-compose up --build
```

This starts: PostgreSQL, Redis, Django API (port 8000), Celery Worker, Celery Beat, and the React frontend (port 5173).

The backend auto-runs migrations and seeds 3 test merchants on startup.

**Dashboard:** http://localhost:5173
**API:** http://localhost:8000/api/v1/

## Local Development Setup

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL 16+
- Redis 7+

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables (or create .env file)
export DATABASE_URL=postgres://postgres:postgres@localhost:5432/playto
export REDIS_URL=redis://localhost:6379/0

# Run migrations
python manage.py migrate

# Seed test data (3 merchants with credit history)
python manage.py seed_data

# Start the Django dev server
python manage.py runserver
```

### Celery Workers

In separate terminals:

```bash
# Worker (processes payout tasks)
cd backend
celery -A playto worker --loglevel=info

# Beat (schedules periodic sweep of stuck payouts)
cd backend
celery -A playto beat --loglevel=info
```

### Frontend

```bash
cd frontend

npm install
npm run dev
```

The frontend dev server runs on http://localhost:5173 and proxies API requests to the Django backend on port 8000.

## Running Tests

Tests require a running PostgreSQL instance (SQLite doesn't support `select_for_update`).

```bash
cd backend
python manage.py test payouts.tests --verbosity=2
```

### Test Coverage
- **test_concurrency.py**: Two threads simultaneously request 60₹ payouts against 100₹ balance. Verifies exactly one succeeds and no overdraw occurs.
- **test_idempotency.py**: Duplicate idempotency keys return identical responses, different keys create separate payouts, keys are merchant-scoped.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/merchants/` | List all merchants with balances |
| GET | `/api/v1/merchants/{id}/` | Merchant details + balances |
| GET | `/api/v1/merchants/{id}/ledger/` | Paginated ledger entries |
| POST | `/api/v1/payouts/` | Create payout (requires `Idempotency-Key` header) |
| GET | `/api/v1/payouts/list/` | List payouts (filter by `?merchant=<id>`) |
| GET | `/api/v1/payouts/{id}/` | Payout details |

### Example: Create Payout

```bash
curl -X POST http://localhost:8000/api/v1/payouts/ \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "merchant_id": "<merchant-uuid>",
    "amount_paise": 500000,
    "bank_account_id": "<bank-account-uuid>"
  }'
```

## Seed Data

The `seed_data` management command creates:

| Merchant | Balance | Credits |
|----------|---------|---------|
| Priya's Design Studio | ₹22,500 | 5 payments |
| Raj's Software Solutions | ₹41,500 | 4 payments |
| Ananya Freelance Writing | ₹6,700 | 3 payments |

## Tech Stack

- **Backend:** Django 5.1, Django REST Framework 3.15
- **Database:** PostgreSQL 16 (BigIntegerField for money, select_for_update for locking)
- **Task Queue:** Celery 5.4 + Redis (background payout processing)
- **Frontend:** React 18 (Vite) + Tailwind CSS v4
- **DevOps:** Docker Compose, Gunicorn, Whitenoise, Nginx
