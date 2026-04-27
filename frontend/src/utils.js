/**
 * Format paise amount to INR display string.
 * e.g., 500000 paise → "₹5,000.00"
 */
export function formatCurrency(paise) {
  const rupees = paise / 100;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
  }).format(rupees);
}

/**
 * Format ISO date string to readable format.
 */
export function formatDate(isoString) {
  if (!isoString) return '—';
  const date = new Date(isoString);
  return date.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Generate a UUID v4 for idempotency keys.
 */
export function generateUUID() {
  return crypto.randomUUID();
}

/**
 * Get CSS class for a status badge.
 */
export function getStatusBadgeClass(status) {
  const map = {
    PENDING: 'badge-pending',
    PROCESSING: 'badge-processing',
    COMPLETED: 'badge-completed',
    FAILED: 'badge-failed',
  };
  return `badge ${map[status] || ''}`;
}

/**
 * Get CSS class for a ledger entry type badge.
 */
export function getEntryTypeBadgeClass(type) {
  const map = {
    CREDIT: 'badge-credit',
    DEBIT: 'badge-debit',
    HOLD: 'badge-hold',
    RELEASE: 'badge-release',
  };
  return `badge ${map[type] || ''}`;
}
