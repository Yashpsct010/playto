import { formatCurrency } from '../utils';

export default function BalanceCard({ merchant }) {
  if (!merchant) return null;

  const cards = [
    {
      label: 'Available Balance',
      value: merchant.available_balance_paise,
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      ),
      textColor: 'text-accent',
      iconColor: 'text-success',
    },
    {
      label: 'Held Balance',
      value: merchant.held_balance_paise,
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
      ),
      textColor: 'text-warning',
      iconColor: 'text-warning',
    },
    {
      label: 'Total Balance',
      value: merchant.total_balance_paise,
      icon: null,
      textColor: 'text-text-primary',
      iconColor: '',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {cards.map((card, i) => (
        <div
          key={card.label}
          className="paper-card p-6 animate-slide-up"
          style={{ animationDelay: `${i * 100}ms` }}
        >
          <div className="flex items-center justify-between mb-4">
            <span className="label-meta">{card.label}</span>
            {card.icon && <div className={`${card.iconColor}`}>{card.icon}</div>}
          </div>
          <p className={`text-3xl tabular-nums ${card.textColor}`}>
            {formatCurrency(card.value)}
          </p>
        </div>
      ))}
    </div>
  );
}
