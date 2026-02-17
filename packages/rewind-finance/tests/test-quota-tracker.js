const { describe, it, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { QuotaTracker } = require('../src/quota-tracker');

function tmpDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'rw-quota-'));
}

describe('QuotaTracker', () => {
  let dir, tracker;

  beforeEach(() => {
    dir = tmpDir();
    tracker = new QuotaTracker({
      quotaFile: path.join(dir, 'quota.json'),
      logFile: path.join(dir, 'quota.log'),
      monthlyLimit: 100,
    });
  });

  it('starts at 0 used', () => {
    const s = tracker.getState();
    assert.equal(s.used, 0);
    assert.equal(s.monthlyLimit, 100);
  });

  it('increments usage', () => {
    tracker.increment(5);
    assert.equal(tracker.getState().used, 5);
    const c = tracker.check();
    assert.equal(c.remaining, 95);
    assert.equal(c.throttled, false);
  });

  it('throttles at 80%', () => {
    tracker.increment(80);
    const c = tracker.check();
    assert.equal(c.throttled, true);
    assert.equal(c.allowed, true);
  });

  it('disallows at 100%', () => {
    tracker.increment(100);
    const c = tracker.check();
    assert.equal(c.allowed, false);
    assert.equal(c.remaining, 0);
  });

  it('persists state to disk', () => {
    tracker.increment(42);
    const t2 = new QuotaTracker({
      quotaFile: path.join(dir, 'quota.json'),
      logFile: path.join(dir, 'quota.log'),
      monthlyLimit: 100,
    });
    assert.equal(t2.getState().used, 42);
  });

  it('writes to log file', () => {
    tracker.increment(1);
    const log = fs.readFileSync(path.join(dir, 'quota.log'), 'utf8');
    assert.ok(log.includes('+1 call(s)'));
  });
});
