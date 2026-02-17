/**
 * Composio adapter — fetches Google Sheets rows via Composio v3 REST API,
 * falls back to cached CSV when API key is missing or quota exhausted.
 *
 * v3 endpoints:
 *   GET  /api/v3/connected_accounts?toolkitSlug=googlesheets&status=ACTIVE
 *   POST /api/v3/tools/execute/GOOGLESHEETS_BATCH_GET
 *        body: { connected_account_id, arguments: { spreadsheet_id, ranges: [...] } }
 */
const fs = require('fs');
const path = require('path');
const { FinanceRecord } = require('./finance-record');
const { categorize } = require('./category-rules');
const { QuotaTracker } = require('./quota-tracker');

const CACHE_PATH = path.join(__dirname, '..', 'finance', 'cache-sheet.csv');
const COMPOSIO_BASE = 'https://backend.composio.dev/api/v3';

class ComposioAdapter {
  constructor(opts = {}) {
    this.apiKey = opts.apiKey || process.env.COMPOSIO_API_KEY || '';
    this.sheetId = opts.sheetId || process.env.GOOGLE_SHEET_ID || '';
    this.cachePath = opts.cachePath || CACHE_PATH;
    this.quota = opts.quota || new QuotaTracker();
    this.fetchFn = opts.fetchFn || null;
  }

  canUseLive() {
    if (!this.apiKey) return false;
    const q = this.quota.check();
    return q.allowed && !q.throttled;
  }

  async fetchRecords() {
    if (this.canUseLive()) {
      return this._fetchLive();
    }
    if (!this.apiKey) {
      console.log('[composio-adapter] No COMPOSIO_API_KEY set; using cache.');
    } else {
      console.log('[composio-adapter] Quota exhausted/throttled; using cache.');
    }
    return this._fetchFromCache();
  }

  async _fetchLive() {
    try {
      let records;
      if (this.fetchFn) {
        const rows = await this.fetchFn(this.apiKey, this.sheetId);
        records = rows.map((row, i) => this._rowToRecord(row, i));
      } else {
        records = await this._composioFetch();
      }
      this.quota.increment(1);
      this._writeCache(records);
      console.log(`[composio-adapter] Live fetch: ${records.length} records from Composio`);
      return records;
    } catch (err) {
      console.error('[composio-adapter] Live fetch failed, falling back to cache:', err.message);
      return this._fetchFromCache();
    }
  }

  async _getConnectedAccountId() {
    const url = `${COMPOSIO_BASE}/connected_accounts?toolkitSlug=googlesheets&status=ACTIVE`;
    console.log('[composio-adapter] Listing connected accounts...');
    const resp = await fetch(url, {
      headers: { 'x-api-key': this.apiKey },
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`Failed to list connected accounts (${resp.status}): ${text.slice(0, 200)}`);
    }
    const data = await resp.json();
    const items = data.items || data.data || [];
    if (items.length === 0) {
      throw new Error('No active Google Sheets connected account. Connect one at https://app.composio.dev');
    }
    const id = items[0].id;
    console.log(`[composio-adapter] Using connected account: ${id}`);
    return id;
  }

  /**
   * Fetch "Out" and "In" tabs from the finance spreadsheet via Composio v3.
   * Parses monthly expense rows into FinanceRecords.
   */
  async _composioFetch() {
    const connectedAccountId = await this._getConnectedAccountId();
    const url = `${COMPOSIO_BASE}/tools/execute/GOOGLESHEETS_BATCH_GET`;

    const sheetNames = (process.env.GOOGLE_SHEET_NAME || 'Out,In').split(',').map(s => s.trim());

    const body = {
      connected_account_id: connectedAccountId,
      arguments: {
        spreadsheet_id: this.sheetId,
        ranges: sheetNames,
      },
    };

    console.log(`[composio-adapter] Fetching sheets: ${sheetNames.join(', ')}`);

    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': this.apiKey,
      },
      body: JSON.stringify(body),
    });

    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`Composio API ${resp.status}: ${text.slice(0, 300)}`);
    }

    const data = await resp.json();
    return this._parseFinanceSheet(data);
  }

  /**
   * Parse the monthly expense/income sheet into FinanceRecords.
   * The "Out" sheet has: Month | Budget | Total Spent | Housing | Gas | ... (categories as columns)
   * The "In" sheet has:  Month | Gross Income | ... | Net Income | ...
   */
  _parseFinanceSheet(data) {
    const records = [];
    const valueRanges = data.data?.valueRanges || data.valueRanges || [];

    for (const range of valueRanges) {
      const values = range.values;
      if (!values || values.length < 2) continue;

      const sheetName = (range.range || '').split('!')[0];
      const isIncome = sheetName.toLowerCase() === 'in';
      const headers = values[0];

      // Skip summary rows (rows without a month like "7/2023")
      for (let i = 1; i < values.length; i++) {
        const row = values[i];
        if (!row || !row[0]) continue;
        const month = row[0].toString().trim();
        // Must look like a date: M/YYYY or MM/YYYY
        if (!/^\d{1,2}\/\d{4}$/.test(month)) continue;

        if (isIncome) {
          // Income sheet: extract Gross Income and Net Income
          const gross = this._parseDollar(row[1]);
          const net = this._parseDollar(row[8]); // Net Income column
          if (gross > 0 || net > 0) {
            records.push(new FinanceRecord({
              id: `fr-in-${month.replace('/', '-')}`,
              date: this._monthToDate(month),
              description: `Income (${month})`,
              amount: net || gross,
              account: 'income',
              category: 'income',
              goalTag: 'medium',
              goalName: 'Save 15k by semester',
            }));
          }
        } else {
          // Out sheet: each column after "Total Spent" is a category
          const totalSpent = this._parseDollar(row[2]);
          if (totalSpent === 0) continue;

          // Create one record per category that has spending
          for (let c = 3; c < headers.length && c < row.length; c++) {
            const amount = this._parseDollar(row[c]);
            if (amount <= 0) continue;
            const catName = (headers[c] || 'misc').toString().trim();
            const { category, goalTag, goalName } = this._categorizeColumn(catName);
            records.push(new FinanceRecord({
              id: `fr-out-${month.replace('/', '-')}-${c}`,
              date: this._monthToDate(month),
              description: `${catName} (${month})`,
              amount: -amount, // expenses are negative
              account: catName.toLowerCase(),
              category,
              goalTag,
              goalName,
            }));
          }
        }
      }
    }

    return records;
  }

  /** Map sheet column names to our category system */
  _categorizeColumn(colName) {
    const col = colName.toLowerCase().trim();
    const MAP = {
      'housing': { category: 'housing', goalTag: 'long', goalName: 'Move to SF' },
      'groceries': { category: 'food', goalTag: 'short', goalName: 'Daily expenses' },
      'eating out': { category: 'food', goalTag: 'short', goalName: 'Daily expenses' },
      'insurance': { category: 'subscriptions', goalTag: 'short', goalName: 'Daily expenses' },
      'internet': { category: 'subscriptions', goalTag: 'short', goalName: 'Daily expenses' },
      'education': { category: 'tuition', goalTag: 'short', goalName: 'Pay tuition' },
      'medical': { category: 'uncategorized', goalTag: 'short', goalName: 'Daily expenses' },
      'gifts': { category: 'family-support', goalTag: 'short', goalName: 'Support parents monthly' },
      'charity': { category: 'family-support', goalTag: 'short', goalName: 'Support parents monthly' },
      'clothing': { category: 'uncategorized', goalTag: 'short', goalName: 'Daily expenses' },
      'entertainment': { category: 'uncategorized', goalTag: 'short', goalName: 'Daily expenses' },
      'gym': { category: 'subscriptions', goalTag: 'short', goalName: 'Daily expenses' },
      'music': { category: 'subscriptions', goalTag: 'short', goalName: 'Daily expenses' },
      'self care': { category: 'uncategorized', goalTag: 'short', goalName: 'Daily expenses' },
      'laundry': { category: 'uncategorized', goalTag: 'short', goalName: 'Daily expenses' },
      'fees': { category: 'credit-card', goalTag: 'short', goalName: 'Pay off credit card' },
      'misc': { category: 'uncategorized', goalTag: 'short', goalName: 'Daily expenses' },
    };
    // Try exact match, then partial
    if (MAP[col]) return MAP[col];
    for (const [key, val] of Object.entries(MAP)) {
      if (col.includes(key)) return val;
    }
    return { category: 'uncategorized', goalTag: 'short', goalName: 'Daily expenses' };
  }

  _parseDollar(val) {
    if (!val) return 0;
    const cleaned = val.toString().replace(/[$,\s]/g, '');
    const num = parseFloat(cleaned);
    return isNaN(num) ? 0 : Math.abs(num);
  }

  _monthToDate(month) {
    // "2/2026" → "2026-02-01"
    const [m, y] = month.split('/');
    return `${y}-${m.padStart(2, '0')}-01`;
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
    const headers = 'date,description,amount,account,category,goalTag';
    const lines = records.map(r =>
      `${r.date},${r.description.replace(/,/g, ';')},${r.amount},${r.account},${r.category},${r.goalTag}`
    );
    fs.writeFileSync(this.cachePath, [headers, ...lines].join('\n'));
  }
}

module.exports = { ComposioAdapter };
