const { describe, it, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { ComposioAdapter } = require('../src/composio-adapter');
const { QuotaTracker } = require('../src/quota-tracker');

function tmpDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'rw-adapter-'));
}

const SAMPLE_ROWS = [
  { date: '2026-02-01', description: 'Texas State tuition payment', amount: '-4500', account: 'Chase' },
  { date: '2026-02-05', description: 'AMEX autopay', amount: '-350', account: 'AMEX' },
  { date: '2026-02-10', description: 'Zelle to Mom monthly', amount: '-500', account: 'Zelle' },
  { date: '2026-02-12', description: 'Transfer to savings account', amount: '-1000', account: 'Chase' },
  { date: '2026-02-14', description: 'Direct deposit - payroll', amount: '2200', account: 'Chase' },
  { date: '2026-02-15', description: 'Uber Eats lunch', amount: '-18.50', account: 'AMEX' },
  { date: '2026-02-16', description: 'Monthly rent payment', amount: '-950', account: 'Chase' },
];

describe('ComposioAdapter', () => {
  let dir;

  beforeEach(() => {
    dir = tmpDir();
  });

  it('fetches from mock Composio and creates FinanceRecords', async () => {
    const mockFetch = async () => SAMPLE_ROWS;
    const quota = new QuotaTracker({
      quotaFile: path.join(dir, 'q.json'),
      logFile: path.join(dir, 'q.log'),
      monthlyLimit: 100,
    });
    const adapter = new ComposioAdapter({
      apiKey: 'test-key',
      sheetId: 'test-sheet',
      cachePath: path.join(dir, 'cache.csv'),
      quota,
      fetchFn: mockFetch,
    });

    const records = await adapter.fetchRecords();
    assert.equal(records.length, 7);

    // Tuition record
    const tuition = records.find(r => r.category === 'tuition');
    assert.ok(tuition);
    assert.equal(tuition.goalTag, 'short');
    assert.equal(tuition.amount, -4500);

    // Family support
    const family = records.find(r => r.category === 'family-support');
    assert.ok(family);
    assert.equal(family.goalName, 'Support parents monthly');

    // Savings
    const savings = records.find(r => r.category === 'savings');
    assert.ok(savings);
    assert.equal(savings.goalTag, 'medium');

    // Quota incremented
    assert.equal(quota.getState().used, 1);
  });

  it('falls back to cache when no API key', async () => {
    // Write a cache file
    const cachePath = path.join(dir, 'cache.csv');
    fs.writeFileSync(cachePath, 'date,description,amount,account\n2026-02-01,AMEX autopay,-350,AMEX\n');

    const adapter = new ComposioAdapter({
      apiKey: '', // no key
      cachePath,
    });
    const records = await adapter.fetchRecords();
    assert.equal(records.length, 1);
    assert.equal(records[0].category, 'credit-card');
  });

  it('falls back to cache when quota exhausted', async () => {
    const quota = new QuotaTracker({
      quotaFile: path.join(dir, 'q.json'),
      logFile: path.join(dir, 'q.log'),
      monthlyLimit: 10,
    });
    quota.increment(10); // exhaust quota

    const cachePath = path.join(dir, 'cache.csv');
    fs.writeFileSync(cachePath, 'date,description,amount,account\n2026-02-14,Direct deposit - payroll,2200,Chase\n');

    const adapter = new ComposioAdapter({
      apiKey: 'test-key',
      cachePath,
      quota,
    });
    const records = await adapter.fetchRecords();
    assert.equal(records.length, 1);
    assert.equal(records[0].category, 'income');
  });

  it('writes cache after live fetch', async () => {
    const mockFetch = async () => SAMPLE_ROWS;
    const cachePath = path.join(dir, 'cache.csv');
    const quota = new QuotaTracker({
      quotaFile: path.join(dir, 'q.json'),
      logFile: path.join(dir, 'q.log'),
      monthlyLimit: 100,
    });
    const adapter = new ComposioAdapter({
      apiKey: 'test-key',
      cachePath,
      quota,
      fetchFn: mockFetch,
    });

    await adapter.fetchRecords();
    assert.ok(fs.existsSync(cachePath));
    const csv = fs.readFileSync(cachePath, 'utf8');
    assert.ok(csv.includes('tuition'));
  });
});
