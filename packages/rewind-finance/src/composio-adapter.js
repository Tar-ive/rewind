/**
 * Composio adapter — fetches Google Sheets rows via Composio REST API,
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
const COMPOSIO_BASE = 'https://backend.composio.dev/api/v2';

class ComposioAdapter {
  /**
   * @param {object} opts
   * @param {string} opts.apiKey       - COMPOSIO_API_KEY
   * @param {string} opts.sheetId      - GOOGLE_SHEET_ID
   * @param {string} opts.cachePath    - fallback CSV path
   * @param {QuotaTracker} opts.quota
   * @param {function} opts.fetchFn    - injectable fetch override (for testing)
   */
  constructor(opts = {}) {
    this.apiKey = opts.apiKey || process.env.COMPOSIO_API_KEY || '';
    this.sheetId = opts.sheetId || process.env.GOOGLE_SHEET_ID || '';
    this.cachePath = opts.cachePath || CACHE_PATH;
    this.quota = opts.quota || new QuotaTracker();
    this.fetchFn = opts.fetchFn || null;
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
      let rows;
      if (this.fetchFn) {
        // Injected mock for testing
        rows = await this.fetchFn(this.apiKey, this.sheetId);
      } else {
        // Real Composio API call
        rows = await this._composioFetch();
      }
      this.quota.increment(1);
      const records = rows.map((row, i) => this._rowToRecord(row, i));
      this._writeCache(records);
      console.log(`[composio-adapter] Live fetch: ${records.length} records from Composio`);
      return records;
    } catch (err) {
      console.error('[composio-adapter] Live fetch failed, falling back to cache:', err.message);
      return this._fetchFromCache();
    }
  }

  /**
   * Hit Composio REST API to execute GOOGLESHEETS_BATCH_GET action.
   * Returns array of row objects with keys: date, description, amount, account
   */
  async _composioFetch() {
    // Step 1: Try to get sheet data via Composio's action execution endpoint
    const actionName = 'GOOGLESHEETS_BATCH_GET';
    const url = `${COMPOSIO_BASE}/actions/${actionName}/execute`;

    const body = {
      connectedAccountId: 'default',
      input: {
        spreadsheet_id: this.sheetId,
        ranges: 'Sheet1',  // default sheet name; override via GOOGLE_SHEET_NAME env
      },
      entityId: 'default',
    };

    if (process.env.GOOGLE_SHEET_NAME) {
      body.input.ranges = process.env.GOOGLE_SHEET_NAME;
    }

    console.log(`[composio-adapter] Calling Composio: ${actionName} for sheet ${this.sheetId}`);

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
      throw new Error(`Composio API ${resp.status}: ${text}`);
    }

    const data = await resp.json();

    // Parse the response — Composio returns valueRanges with 2D arrays
    return this._parseSheetResponse(data);
  }

  /**
   * Parse Composio's Google Sheets response into row objects.
   * Handles multiple response shapes from the API.
   */
  _parseSheetResponse(data) {
    // The response structure can vary; try common paths
    let values = null;

    // Direct values array
    if (data.response_data?.values) {
      values = data.response_data.values;
    }
    // Nested in valueRanges
    else if (data.response_data?.valueRanges?.[0]?.values) {
      values = data.response_data.valueRanges[0].values;
    }
    // Data might be at top level
    else if (data.data?.values) {
      values = data.data.values;
    }
    // Flat data object with successfull key (Composio spelling)
    else if (data.successfull !== undefined && data.data) {
      if (Array.isArray(data.data)) {
        values = data.data;
      } else if (data.data.valueRanges?.[0]?.values) {
        values = data.data.valueRanges[0].values;
      } else if (data.data.values) {
        values = data.data.values;
      }
    }

    if (!values || values.length < 2) {
      console.log('[composio-adapter] Response structure:', JSON.stringify(data).slice(0, 500));
      throw new Error('Could not parse sheet data from Composio response. Check GOOGLE_SHEET_ID and sheet format.');
    }

    // First row = headers, rest = data
    const headers = values[0].map(h => h.toString().trim().toLowerCase());
    const rows = [];

    for (let i = 1; i < values.length; i++) {
      const row = {};
      headers.forEach((h, idx) => {
        row[h] = (values[i][idx] || '').toString().trim();
      });
      rows.push(row);
    }

    return rows;
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
