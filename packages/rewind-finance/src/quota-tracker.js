/**
 * Composio quota tracker — deterministic, file-based.
 * Tracks API calls against a monthly limit and throttles when > 80%.
 */
const fs = require('fs');
const path = require('path');

const DEFAULT_MONTHLY_LIMIT = 10000;
const THROTTLE_THRESHOLD = 0.8; // 80%

class QuotaTracker {
  /**
   * @param {object} opts
   * @param {string} opts.quotaFile  - path to quota/composio.json
   * @param {string} opts.logFile    - path to logs/composio_quota.log
   * @param {number} opts.monthlyLimit
   */
  constructor(opts = {}) {
    this.quotaFile = opts.quotaFile || path.join(__dirname, '..', 'quota', 'composio.json');
    this.logFile = opts.logFile || path.join(__dirname, '..', 'logs', 'composio_quota.log');
    this.monthlyLimit = opts.monthlyLimit || DEFAULT_MONTHLY_LIMIT;
    this.state = this._load();
  }

  _load() {
    try {
      return JSON.parse(fs.readFileSync(this.quotaFile, 'utf8'));
    } catch {
      return { month: this._currentMonth(), used: 0, throttled: false };
    }
  }

  _currentMonth() {
    return new Date().toISOString().slice(0, 7); // "2026-02"
  }

  _save() {
    fs.mkdirSync(path.dirname(this.quotaFile), { recursive: true });
    fs.writeFileSync(this.quotaFile, JSON.stringify(this.state, null, 2));
  }

  _log(msg) {
    fs.mkdirSync(path.dirname(this.logFile), { recursive: true });
    const line = `[${new Date().toISOString()}] ${msg}\n`;
    fs.appendFileSync(this.logFile, line);
  }

  /** Reset counter if new month */
  _rollMonth() {
    const cm = this._currentMonth();
    if (this.state.month !== cm) {
      this._log(`Month rolled: ${this.state.month} → ${cm} (was ${this.state.used} calls)`);
      this.state = { month: cm, used: 0, throttled: false };
      this._save();
    }
  }

  /** @returns {{ allowed: boolean, used: number, remaining: number, throttled: boolean }} */
  check() {
    this._rollMonth();
    const remaining = this.monthlyLimit - this.state.used;
    const ratio = this.state.used / this.monthlyLimit;
    const throttled = ratio >= THROTTLE_THRESHOLD;

    if (throttled && !this.state.throttled) {
      this.state.throttled = true;
      this._log(`THROTTLE ON: ${this.state.used}/${this.monthlyLimit} (${(ratio * 100).toFixed(1)}%)`);
      this._save();
    }

    return {
      allowed: remaining > 0,
      used: this.state.used,
      remaining,
      throttled,
      ratio,
    };
  }

  /** Increment usage by n calls. Returns check() result. */
  increment(n = 1) {
    this._rollMonth();
    this.state.used += n;
    this._save();
    this._log(`+${n} call(s) → ${this.state.used}/${this.monthlyLimit}`);
    return this.check();
  }

  /** Get raw state */
  getState() {
    this._rollMonth();
    return { ...this.state, monthlyLimit: this.monthlyLimit };
  }
}

module.exports = { QuotaTracker, DEFAULT_MONTHLY_LIMIT, THROTTLE_THRESHOLD };
