#!/usr/bin/env node
/**
 * rewind-finance CLI
 *
 * Usage:
 *   rewind-finance sync       # fetch from Composio (or cache), emit tasks
 *   rewind-finance status     # show quota + task summary
 *   rewind-finance cache      # show cached records
 *
 * Env vars:
 *   COMPOSIO_API_KEY    - Composio API key
 *   GOOGLE_SHEET_ID     - target sheet ID
 *   COMPOSIO_MONTHLY_LIMIT - default 10000
 */
const { ComposioAdapter } = require('./composio-adapter');
const { QuotaTracker } = require('./quota-tracker');
const { emitTasks, summarize } = require('./task-emitter');

const cmd = process.argv[2] || 'sync';

async function main() {
  const quota = new QuotaTracker({
    monthlyLimit: parseInt(process.env.COMPOSIO_MONTHLY_LIMIT || '10000', 10),
  });
  const adapter = new ComposioAdapter({ quota });

  switch (cmd) {
    case 'sync': {
      console.log('🔄 Syncing finance records...\n');
      const records = await adapter.fetchRecords();
      if (records.length === 0) {
        console.log('No records found. Add a cache CSV at finance/cache-sheet.csv or set COMPOSIO_API_KEY.');
        break;
      }
      const tasks = emitTasks(records);
      console.log(summarize(tasks));
      console.log(`\n✅ ${records.length} records → ${tasks.length} tasks`);
      break;
    }
    case 'status': {
      const q = quota.getState();
      const qs = quota.check();
      console.log('📊 Composio Quota');
      console.log(`  Month:     ${q.month}`);
      console.log(`  Used:      ${q.used} / ${q.monthlyLimit}`);
      console.log(`  Remaining: ${qs.remaining}`);
      console.log(`  Throttled: ${qs.throttled ? '⚠️ YES' : '✅ No'}`);
      console.log(`  API key:   ${adapter.apiKey ? '✅ Set' : '❌ Not set'}`);
      break;
    }
    case 'cache': {
      const records = adapter._fetchFromCache();
      if (records.length === 0) {
        console.log('No cached records. Place a CSV at finance/cache-sheet.csv');
        break;
      }
      for (const r of records) {
        console.log(`${r.date}  ${r.account.padEnd(10)} ${String(r.amount).padStart(10)}  ${r.description}`);
      }
      break;
    }
    default:
      console.log('Usage: rewind-finance <sync|status|cache>');
  }
}

main().catch(err => { console.error(err); process.exit(1); });
