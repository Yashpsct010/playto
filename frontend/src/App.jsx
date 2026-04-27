import { useState, useEffect, useCallback } from 'react';
import MerchantSelector from './components/MerchantSelector';
import BalanceCard from './components/BalanceCard';
import PayoutForm from './components/PayoutForm';
import LedgerTable from './components/LedgerTable';
import PayoutHistory from './components/PayoutHistory';
import { fetchMerchant, fetchLedger, fetchPayouts } from './api';

export default function App() {
  const [merchant, setMerchant] = useState(null);
  const [ledgerEntries, setLedgerEntries] = useState([]);
  const [payouts, setPayouts] = useState([]);
  const [loading, setLoading] = useState(false);

  // Refresh all data for the selected merchant
  const refreshData = useCallback(async (merchantId) => {
    if (!merchantId) return;
    try {
      const [merchantData, ledgerData, payoutData] = await Promise.all([
        fetchMerchant(merchantId),
        fetchLedger(merchantId),
        fetchPayouts(merchantId),
      ]);
      setMerchant(merchantData);
      setLedgerEntries(ledgerData.results || ledgerData);
      setPayouts(payoutData.results || payoutData);
    } catch (err) {
      console.error('Error refreshing data:', err);
    }
  }, []);

  // When a merchant is selected, load their data
  const handleMerchantSelect = useCallback(async (selectedMerchant) => {
    setLoading(true);
    setMerchant(selectedMerchant);
    await refreshData(selectedMerchant.id);
    setLoading(false);
  }, [refreshData]);

  // Poll for updates every 5 seconds
  useEffect(() => {
    if (!merchant?.id) return;

    const interval = setInterval(() => {
      refreshData(merchant.id);
    }, 5000);

    return () => clearInterval(interval);
  }, [merchant?.id, refreshData]);

  return (
    <div className="min-h-screen bg-bg-primary">
      {/* Header */}
      <header className="bg-bg-card border-b border-border sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-accent-light flex items-center justify-center shadow-sm">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div>
                <h1 className="text-text-primary font-bold text-lg tracking-tight">Playto Pay</h1>
                <p className="text-text-muted text-[10px] -mt-0.5 tracking-wide">MERCHANT DASHBOARD</p>
              </div>
            </div>

            {/* Merchant Selector */}
            <div className="w-72">
              <MerchantSelector
                selectedMerchant={merchant}
                onSelect={handleMerchantSelect}
              />
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="flex flex-col items-center gap-4">
              <svg className="animate-spin w-8 h-8 text-accent" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <p className="text-text-muted text-sm">Loading merchant data...</p>
            </div>
          </div>
        ) : merchant ? (
          <div className="space-y-6">
            {/* Balance Cards */}
            <BalanceCard merchant={merchant} />

            {/* Payout Form + Payout History */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-1">
                <PayoutForm
                  merchant={merchant}
                  onPayoutCreated={() => refreshData(merchant.id)}
                />
              </div>
              <div className="lg:col-span-2">
                <PayoutHistory payouts={payouts} />
              </div>
            </div>

            {/* Ledger */}
            <LedgerTable entries={ledgerEntries} />
          </div>
        ) : (
          <div className="flex items-center justify-center py-20">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-bg-card flex items-center justify-center">
                <svg className="w-8 h-8 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              </div>
              <h2 className="text-text-primary text-lg font-semibold mb-1">Select a Merchant</h2>
              <p className="text-text-muted text-sm">Choose a merchant from the dropdown above to get started</p>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border/30 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between text-text-muted text-xs">
            <span>Playto Pay — Payout Engine v1.0</span>
            <span>Built for the Founding Engineer Challenge 2026</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
