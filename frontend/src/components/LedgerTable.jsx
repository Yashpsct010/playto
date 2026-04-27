import { formatCurrency, formatDate, getEntryTypeBadgeClass } from '../utils';

export default function LedgerTable({ entries }) {
  if (!entries || entries.length === 0) {
    return (
      <div className="paper-card p-8 animate-slide-up" style={{ animationDelay: '400ms' }}>
        <h2 className="text-xl font-bold text-text-primary mb-6">Recent Transactions</h2>
        <p className="text-text-muted text-sm text-center py-12">No transactions yet</p>
      </div>
    );
  }

  return (
    <div className="paper-card p-8 animate-slide-up" style={{ animationDelay: '400ms' }}>
      <h2 className="text-xl font-bold text-text-primary mb-6">Recent Transactions</h2>
      
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left text-text-muted text-xs font-medium uppercase tracking-wider py-3 px-2">Type</th>
              <th className="text-left text-text-muted text-xs font-medium uppercase tracking-wider py-3 px-2">Description</th>
              <th className="text-right text-text-muted text-xs font-medium uppercase tracking-wider py-3 px-2">Amount</th>
              <th className="text-right text-text-muted text-xs font-medium uppercase tracking-wider py-3 px-2">Date</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, i) => (
              <tr
                key={entry.id}
                className="border-b border-border/50 hover:bg-bg-card-hover/50 transition-colors"
              >
                <td className="py-3 px-2">
                  <span className={getEntryTypeBadgeClass(entry.entry_type)}>
                    {entry.entry_type === 'CREDIT' && '↓'}
                    {entry.entry_type === 'DEBIT' && '↑'}
                    {entry.entry_type === 'HOLD' && '⏸'}
                    {entry.entry_type === 'RELEASE' && '↩'}
                    {' '}{entry.entry_type}
                  </span>
                </td>
                <td className="py-3 px-2">
                  <p className="text-text-primary text-sm">{entry.description}</p>
                </td>
                <td className="py-3 px-2 text-right">
                  <span className={`font-bold tabular-nums text-sm ${
                    entry.entry_type === 'CREDIT' || entry.entry_type === 'RELEASE'
                      ? 'text-accent'
                      : 'text-danger'
                  }`}>
                    {entry.entry_type === 'CREDIT' || entry.entry_type === 'RELEASE' ? '+' : '-'}
                    {formatCurrency(entry.amount_paise)}
                  </span>
                </td>
                <td className="py-3 px-2 text-right">
                  <span className="text-text-muted text-xs">{formatDate(entry.created_at)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
