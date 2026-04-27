import { formatCurrency, formatDate, getStatusBadgeClass } from '../utils';

export default function PayoutHistory({ payouts }) {
  if (!payouts || payouts.length === 0) {
    return (
      <div className="paper-card p-6 animate-slide-up" style={{ animationDelay: '500ms' }}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-text-primary">Payout History</h2>
          <span className="text-text-muted text-xs font-medium uppercase tracking-wider">Auto-refreshes every 5s</span>
        </div>
        <p className="text-text-muted text-sm text-center py-12">No payouts yet</p>
      </div>
    );
  }

  return (
    <div className="paper-card p-8 animate-slide-up" style={{ animationDelay: '500ms' }}>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-text-primary">Payout History</h2>
        <div className="flex items-center gap-2 bg-bg-secondary px-3 py-1.5 rounded-full">
          <span className="status-dot dot-processing"></span>
          <span className="text-text-primary text-xs font-bold uppercase tracking-wider">Live</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left text-text-muted text-xs font-medium uppercase tracking-wider py-3 px-2">ID</th>
              <th className="text-left text-text-muted text-xs font-medium uppercase tracking-wider py-3 px-2">Bank Account</th>
              <th className="text-right text-text-muted text-xs font-medium uppercase tracking-wider py-3 px-2">Amount</th>
              <th className="text-center text-text-muted text-xs font-medium uppercase tracking-wider py-3 px-2">Status</th>
              <th className="text-center text-text-muted text-xs font-medium uppercase tracking-wider py-3 px-2">Attempts</th>
              <th className="text-right text-text-muted text-xs font-medium uppercase tracking-wider py-3 px-2">Created</th>
              <th className="text-right text-text-muted text-xs font-medium uppercase tracking-wider py-3 px-2">Processed</th>
            </tr>
          </thead>
          <tbody>
            {payouts.map((payout) => (
              <tr
                key={payout.id}
                className="border-b border-border/50 hover:bg-bg-card-hover/50 transition-colors"
              >
                <td className="py-3 px-2">
                  <span className="text-text-muted text-xs font-mono">
                    {payout.id.slice(0, 8)}...
                  </span>
                </td>
                <td className="py-3 px-2">
                  <span className="text-text-primary text-sm">
                    {payout.bank_account_display}
                  </span>
                </td>
                <td className="py-3 px-2 text-right">
                  <span className="text-text-primary font-semibold text-sm">
                    {formatCurrency(payout.amount_paise)}
                  </span>
                </td>
                <td className="py-3 px-2 text-center">
                  <span className={getStatusBadgeClass(payout.status)}>
                    <span className={`status-dot dot-${payout.status.toLowerCase()}`}></span>
                    {payout.status}
                  </span>
                </td>
                <td className="py-3 px-2 text-center">
                  <span className="text-text-muted text-sm">{payout.attempts}/3</span>
                </td>
                <td className="py-3 px-2 text-right">
                  <span className="text-text-muted text-xs">{formatDate(payout.created_at)}</span>
                </td>
                <td className="py-3 px-2 text-right">
                  <span className="text-text-muted text-xs">{formatDate(payout.processed_at)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
