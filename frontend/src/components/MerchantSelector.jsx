import { useState, useEffect } from 'react';
import { fetchMerchants } from '../api';

export default function MerchantSelector({ selectedMerchant, onSelect }) {
  const [merchants, setMerchants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    fetchMerchants()
      .then((data) => {
        setMerchants(data);
        // Auto-select first merchant
        if (data.length > 0 && !selectedMerchant) {
          onSelect(data[0]);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="animate-pulse flex items-center gap-3 p-3 rounded-xl bg-bg-card">
        <div className="w-10 h-10 rounded-full bg-border"></div>
        <div className="h-4 w-32 rounded bg-border"></div>
      </div>
    );
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-3 w-full p-2.5 rounded-xl bg-transparent border-0 hover:bg-bg-secondary transition-all cursor-pointer"
      >
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-accent to-accent-light flex items-center justify-center text-white font-bold text-sm shadow-sm">
          {selectedMerchant?.name?.[0] || '?'}
        </div>
        <div className="flex-1 text-left">
          <p className="text-text-primary font-bold text-sm">
            {selectedMerchant?.name || 'Select Merchant'}
          </p>
          <p className="text-text-muted text-xs">
            {selectedMerchant?.email || ''}
          </p>
        </div>
        <svg
          className={`w-4 h-4 text-text-muted transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute top-full left-0 right-0 mt-2 rounded-xl bg-bg-card border-0 shadow-lg shadow-accent/5 z-50 overflow-hidden animate-fade-in ring-1 ring-border">
          {merchants.map((m) => (
            <button
              key={m.id}
              onClick={() => {
                onSelect(m);
                setOpen(false);
              }}
              className={`flex items-center gap-3 w-full p-3 hover:bg-bg-secondary transition-colors cursor-pointer ${
                selectedMerchant?.id === m.id ? 'bg-bg-secondary/50' : ''
              }`}
            >
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-accent to-accent-light flex items-center justify-center text-white font-bold text-xs shadow-sm">
                {m.name[0]}
              </div>
              <div className="text-left">
                <p className="text-text-primary text-sm font-bold">{m.name}</p>
                <p className="text-text-muted text-xs">{m.email}</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
