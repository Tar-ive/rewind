/**
 * Composio adapter — fetches Google Sheets rows via Composio v3 REST API,
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
const COMPOSIO_BASE = 'https://backend.composio.dev/api/v3';

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
        rows = await this.fetchFn(this.apiKey, this.sheetId);
      } else {
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
   * Look up the connected Google Sheets account ID from Composio v3.
   */
  async _getConnectedAccountId() {
    // v3 endpoint for connected accounts
    const url = `${COMPOSIO_BASE}/connectedAccounts?toolkitSlug=googlesheets&status=ACTIVE`;
    console.log(`[composio-adapter] Listing connected accounts...`);
    const resp = await fetch(url, {
      headers: { 'x-api-key': this.apiKey },
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`Failed to list connected accounts (${resp.status}): ${text}`);
    }
    const data = await resp.json();
    // v3 may return { items: [...] } or { data: [...] } or top-level array
    const items = data.items || data.data || data.connectedAccounts || (Array.isArray(data) ? data : []);
    if (items.length === 0) {
      throw new Error('No active Google Sheets connected account found in Composio. Connect one at https://app.composio.dev');
    }
    const id = items[0].id;
    console.log(`[composio-adapter] Using connected account: ${id}`);
    return id;
  }

  /**
   * Hit Composio v3 REST API to execute GOOGLESHEETS_BATCH_GET action.
   * v3 endpoint: POST /api/v3/tools/execute/{action}
   */
  async _composioFetch() {
    const connectedAccountId = await this._getConnectedAccountId();
    const actionName = 'GOOGLESHEETS_BATCH_GET';
    const url = `${COMPOSIO_BASE}/tools/execute/${actionName}`;

    const body = {
      connectedAccountId,
      input: {
        spreadsheet_id: this.sheetId,
        ranges: process.env.GOOGLE_SHEET_NAME || 'Sheet1',
      },
    };

    console.log(`[composio-adapter] Executing: ${actionName} for sheet ${this.sheetId}`);

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
    return this._parseSheetResponse(data);
  }

  /**
   * Parse Composio's Google Sheets response into row objects.
   * Handles multiple response shapes from the API.
   */
  _parseSheetResponse(data) {
    let values = null;

    // Try all known response shapes
    const candidates = [
      data.response_data?.values,
      data.response_data?.valueRanges?.[0]?.values,
      data.data?.values,
      data.data?.valueRanges?.[0]?.values,
      data.result?.values,
      data.result?.valueRanges?.[0]?.values,
    ];

    // Also check if data.data or data.successfull wrapping exists
    if (data.successfull !== undefined || data.successful !== undefined) {
      const inner = data.data || data.response_data || data.result;
      if (inner) {
        candidates.push(inner.values);
        candidates.push(inner.valueRanges?.[0]?.values);
        if (Array.isArray(inner)) candidates.push(inner);
      }
    }

    for (const c of candidates) {
      if (Array.isArray(c) && c.length >= 2) {
        values = c;
        break;
      }
    }

    if (!values) {
      // Log the response structure for debugging
      console.log('[composio-adapter] Response keys:', Object.keys(data));
      if (data.data) console.log('[composio-adapter] data keys:', Object.keys(data.data));
      console.log('[composio-adapter] Full response (first 1000 chars):', JSON.stringify(data).slice(0, 1000));
      throw new Error('Could not parse sheet data from Composio response. Check GOOGLE_SHEET_ID and sheet format (expected columns: date, description, amount, account).');
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
