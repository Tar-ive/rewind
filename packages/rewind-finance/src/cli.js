#!/usr/bin/env node
/**
 * rewind-finance CLI
 *
 * Usage:
 *   rewind-finance sync       # fetch from Composio (or cache), emit tasks
 *   rewind-finance status     # show quota + task summary
 *   rewind-finance cache      # show cached records
 *   rewind-finance configure  # interactively set API key + sheet ID
 *
 * Env vars (or .env file):
 *   COMPOSIO_API_KEY          - Composio API key
 *   GOOGLE_SHEET_ID           - target Google Sheet ID
 *   GOOGLE_SHEET_NAME         - sheet tab name (default: Sheet1)
 *   COMPOSIO_MONTHLY_LIMIT    - default 10000
 */
const fs = require('fs');
const path = require('path');
const readline = require('readline');

// Load .env from package root, home dir, or cwd
function loadEnv() {
  const candidates = [
    path.join(__dirname, '..', '.env'),           // package dir
    path.join(process.env.HOME || '', '.env'),     // home dir
    path.join(process.cwd(), '.env'),              // cwd
  ];
  for (const envPath of candidates) {
    if (fs.existsSync(envPath)) {
      const lines = fs.readFileSync(envPath, 'utf8').split('\n');
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) continue;
        const eqIdx = trimmed.indexOf('=');
        if (eqIdx === -1) continue;
        const key = trimmed.slice(0, eqIdx).trim();
        let val = trimmed.slice(eqIdx + 1).trim();
        // Strip surrounding quotes
        if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
          val = val.slice(1, -1);
        }
        if (!process.env[key]) {
          process.env[key] = val;
        }
      }
      console.log(`[env] Loaded ${envPath}`);
      return;
    }
  }
}

loadEnv();

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
        console.log('No records found. Run `rewind-finance configure` to set up, or place a CSV at finance/cache-sheet.csv.');
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
      console.log(`  Sheet ID:  ${adapter.sheetId ? '✅ ' + adapter.sheetId : '❌ Not set'}`);
      break;
    }
    case 'cache': {
      const records = adapter._fetchFromCache();
      if (records.length === 0) {
        console.log('No cached records. Place a CSV at finance/cache-sheet.csv or run `rewind-finance sync`.');
        break;
      }
      for (const r of records) {
        console.log(`${r.date}  ${r.account.padEnd(10)} ${String(r.amount).padStart(10)}  ${r.description}`);
      }
      break;
    }
    case 'configure': {
      const envPath = path.join(__dirname, '..', '.env');
      const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
      const ask = (q) => new Promise(res => rl.question(q, res));

      console.log('🔧 Configure rewind-finance\n');
      const apiKey = await ask(`COMPOSIO_API_KEY [${process.env.COMPOSIO_API_KEY ? '****' + process.env.COMPOSIO_API_KEY.slice(-4) : 'not set'}]: `);
      const sheetId = await ask(`GOOGLE_SHEET_ID [${process.env.GOOGLE_SHEET_ID || 'not set'}]: `);
      const sheetName = await ask(`GOOGLE_SHEET_NAME [${process.env.GOOGLE_SHEET_NAME || 'Sheet1'}]: `);
      rl.close();

      const lines = [];
      if (apiKey) lines.push(`COMPOSIO_API_KEY=${apiKey}`);
      else if (process.env.COMPOSIO_API_KEY) lines.push(`COMPOSIO_API_KEY=${process.env.COMPOSIO_API_KEY}`);
      if (sheetId) lines.push(`GOOGLE_SHEET_ID=${sheetId}`);
      else if (process.env.GOOGLE_SHEET_ID) lines.push(`GOOGLE_SHEET_ID=${process.env.GOOGLE_SHEET_ID}`);
      if (sheetName) lines.push(`GOOGLE_SHEET_NAME=${sheetName}`);
      else lines.push(`GOOGLE_SHEET_NAME=${process.env.GOOGLE_SHEET_NAME || 'Sheet1'}`);

      fs.writeFileSync(envPath, lines.join('\n') + '\n');
      console.log(`\n✅ Saved to ${envPath}`);
      console.log('Run `rewind-finance sync` to test the connection.');
      break;
    }
    default:
      console.log('Usage: rewind-finance <sync|status|cache|configure>');
  }
}

main().catch(err => { console.error(err); process.exit(1); });
