import axios from 'axios';

const API_BASE = '/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ─── Merchants ───

export async function fetchMerchants() {
  const { data } = await api.get('/merchants/');
  return data;
}

export async function fetchMerchant(merchantId) {
  const { data } = await api.get(`/merchants/${merchantId}/`);
  return data;
}

// ─── Ledger ───

export async function fetchLedger(merchantId, page = 1) {
  const { data } = await api.get(`/merchants/${merchantId}/ledger/`, {
    params: { page },
  });
  return data;
}

// ─── Payouts ───

export async function createPayout(merchantId, amountPaise, bankAccountId, idempotencyKey) {
  const { data } = await api.post(
    '/payouts/',
    {
      merchant_id: merchantId,
      amount_paise: amountPaise,
      bank_account_id: bankAccountId,
    },
    {
      headers: {
        'Idempotency-Key': idempotencyKey,
      },
    }
  );
  return data;
}

export async function fetchPayouts(merchantId, page = 1) {
  const { data } = await api.get('/payouts/list/', {
    params: { merchant: merchantId, page },
  });
  return data;
}

export async function fetchPayout(payoutId) {
  const { data } = await api.get(`/payouts/${payoutId}/`);
  return data;
}
