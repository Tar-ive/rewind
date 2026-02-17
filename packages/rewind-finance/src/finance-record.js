/**
 * FinanceRecord — a single financial transaction or obligation
 * tagged with goal metadata for the scheduler.
 */
class FinanceRecord {
  /**
   * @param {object} opts
   * @param {string} opts.id          - unique row/txn id
   * @param {string} opts.date        - ISO date string
   * @param {string} opts.description - human-readable label
   * @param {number} opts.amount      - positive = income, negative = expense
   * @param {string} opts.account     - e.g. "Chase", "AMEX", "Zelle"
   * @param {string} opts.category    - deterministic category tag
   * @param {string} opts.goalTag     - long|medium|short goal association
   * @param {string} opts.goalName    - e.g. "Save 15k by semester"
   * @param {number} opts.readiness   - 0-1 score from profiler
   */
  constructor(opts = {}) {
    this.id = opts.id || `fr-${Date.now()}`;
    this.date = opts.date || new Date().toISOString().slice(0, 10);
    this.description = opts.description || '';
    this.amount = opts.amount || 0;
    this.account = opts.account || 'unknown';
    this.category = opts.category || 'uncategorized';
    this.goalTag = opts.goalTag || 'short';
    this.goalName = opts.goalName || '';
    this.readiness = opts.readiness || 0;
  }

  isExpense() { return this.amount < 0; }
  isIncome() { return this.amount > 0; }

  toJSON() {
    return { ...this };
  }
}

module.exports = { FinanceRecord };
