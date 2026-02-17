/**
 * Composio adapter — fetches Google Sheets rows via Composio API,
 * falls back to cached CSV when API key is missing or quota exhausted.
 *
 * Deterministic: no LLM calls. Uses category-rules for tagging.
 */
const fs = require('fs');
const path = require('path');
const { FinanceRecord } = require('./finance-record');
const { categorize } = require('./category-rules');
const { QuotaTracker } = require('./quota-tracker');

const CACHE_PATH = path.join(__dirname, '..', 'finance', 'cache-sheet.csv');

class ComposioAdapter {
  /**
   * @param {object} opts
   * @param {string} opts.apiKey       - COMPOSIO_API_KEY
   * @param {string} opts.sheetId      - GOOGLE_SHEET_ID
   * @param {string} opts.cachePath    - fallback CSV path
   * @param {QuotaTracker} opts.quota
   * @param {function} opts.fetchFn    - injectable fetch (for testing)
   */
  constructor(opts = {}) {
    this.apiKey = opts.apiKey || process.env.COMPOSIO_API_KEY || '';
    this.sheetId = opts.sheetId || process.env.GOOGLE_SHEET_ID || '';
    this.cachePath = opts.cachePath || CACHE_PATH;
    this.quota = opts.quota || new QuotaTracker();
    this.fetchFn = opts.fetchFn || null; // injected for tests
  }

  /** True when we can hit the Composio API */
  canUseLive() {
    if (!this.apiKey) return false;
    const q = this.quota.check();
    return q.allowed && !q.throttled;
  }

  /**
   * Fetch rows from Composio (or cache).
   * @returns {Promise<FinanceRecord[]>}
   */
  async fetchRecords() {
    if (this.canUseLive() && this.fetchFn) {
      return this._fetchLive();
    }
    if (this.canUseLive() && !this.fetchFn) {
      // Real Composio HTTP call — we'll implement once we test with mocks
      console.log('[composio-adapter] Live Composio call not yet wired; using cache.');
    }
    return this._fetchFromCache();
  }

  async _fetchLive() {
    try {
      const rows = await this.fetchFn(this.apiKey, this.sheetId);
      this.quota.increment(1);
      const records = rows.map((row, i) => this._rowToRecord(row, i));
      this._writeCache(records);
      return records;
    } catch (err) {
      console.error('[composio-adapter] Live fetch failed, falling back to cache:', err.message);
      return this._fetchFromCache();
    }
  }

  _fetchFromCache() {
    if (!fs.existsSync(this.cachePath)) {
      console.log('[composio-adapter] No cache file found at', this.cachePath);
      return [];
    }
    const lines = fs.readFileSync(this.cachePath, 'utf8').trim().split('\n');
    if (lines.length < 2) return [];
    const headers = lines[0].split(',');
    return lines.slice(1).map((line, i) => {
      const cols = line.split(',');
      const row = {};
      headers.forEach((h, idx) => { row[h.trim()] = (cols[idx] || '').trim(); });
      return this._rowToRecord(row, i);
    });
  }

  /**
   * Convert a raw sheet row → FinanceRecord with deterministic tagging.
   * Expected columns: date, description, amount, account
   */
  _rowToRecord(row, idx) {
    const desc = row.description || row.Description || '';
    const { category, goalTag, goalName } = categorize(desc);
    return new FinanceRecord({
      id: `fr-${idx}-${(row.date || '').replace(/\D/g, '')}`,
      date: row.date || row.Date || new Date().toISOString().slice(0, 10),
      description: desc,
      amount: parseFloat(row.amount || row.Amount || 0),
      account: row.account || row.Account || 'unknown',
      category,
      goalTag,
      goalName,
    });
  }

  _writeCache(records) {
    fs.mkdirSync(path.dirname(this.cachePath), { recursive: true });
    const headers = 'date,description,amount,account';
    const lines = records.map(r => `${r.date},${r.description},${r.amount},${r.account}`);
    fs.writeFileSync(this.cachePath, [headers, ...lines].join('\n'));
  }
}

module.exports = { ComposioAdapter };
