import { useState } from 'react';
import { createPayout } from '../api';
import { formatCurrency, generateUUID } from '../utils';

export default function PayoutForm({ merchant, onPayoutCreated }) {
  const [amountRupees, setAmountRupees] = useState('');
  const [selectedBank, setSelectedBank] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  if (!merchant) return null;

  const bankAccounts = merchant.bank_accounts || [];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    const amount = parseFloat(amountRupees);
    if (isNaN(amount) || amount <= 0) {
      setError('Please enter a valid amount greater than ₹0');
      return;
    }

    if (!selectedBank) {
      setError('Please select a bank account');
      return;
    }

    const amountPaise = Math.round(amount * 100);
    if (amountPaise > merchant.available_balance_paise) {
      setError(`Insufficient balance. Available: ${formatCurrency(merchant.available_balance_paise)}`);
      return;
    }

    setLoading(true);
    try {
      const idempotencyKey = generateUUID();
      await createPayout(merchant.id, amountPaise, selectedBank, idempotencyKey);
      setSuccess(`Payout of ₹${amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })} initiated!`);
      setAmountRupees('');
      if (onPayoutCreated) onPayoutCreated();
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to create payout';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="paper-card p-8 animate-slide-up" style={{ animationDelay: '300ms' }}>
      <h2 className="text-xl font-bold text-text-primary mb-2">Request Payout</h2>
      <p className="text-text-muted text-sm mb-6">
        Withdraw funds to your bank account
      </p>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Amount Input */}
        <div>
          <label className="label-meta block mb-2">
            Amount (₹)
          </label>
          <div className="relative">
            <span className="absolute left-0 top-1/2 -translate-y-1/2 text-text-muted text-xl">₹</span>
            <input
              type="number"
              step="0.01"
              min="1"
              value={amountRupees}
              onChange={(e) => setAmountRupees(e.target.value)}
              placeholder="0.00"
              className="input-minimal w-full pl-6 text-xl"
              disabled={loading}
            />
          </div>
          <p className="text-text-muted text-xs mt-2">
            Available: {formatCurrency(merchant.available_balance_paise)}
          </p>
        </div>

        {/* Bank Account Select */}
        <div>
          <label className="label-meta block mb-2">
            Bank Account
          </label>
          <select
            value={selectedBank}
            onChange={(e) => setSelectedBank(e.target.value)}
            className="input-minimal w-full appearance-none cursor-pointer"
            disabled={loading}
          >
            <option value="">Select bank account</option>
            {bankAccounts.map((ba) => (
              <option key={ba.id} value={ba.id}>
                {ba.display_name} ({ba.ifsc_code})
              </option>
            ))}
          </select>
        </div>

        {/* Error/Success Messages */}
        {error && (
          <div className="p-3 bg-danger-bg text-danger text-sm font-medium animate-fade-in">
            {error}
          </div>
        )}
        {success && (
          <div className="p-3 bg-success-bg text-success text-sm font-medium animate-fade-in">
            {success}
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading}
          className="btn-primary w-full py-4 mt-2 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Processing...
            </>
          ) : (
            <>
              Request Payout
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8l4 4m0 0l-4 4m4-4H3" />
              </svg>
            </>
          )}
        </button>
      </form>
    </div>
  );
}
