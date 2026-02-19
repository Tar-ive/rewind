# Rewind Rust CLI — Findings

## Architecture
- Workspace: `rewind-core` (algorithm + types), `rewind-ingest` (statement ingestion), `rewind-finance` (finance-only goals/signals), `rewind-cli` (binary)
- Mirrors Node.js `rewind-finance` package which already works live with Composio v3 API
- Composio v3 endpoints: `GET /api/v3/connected_accounts`, `POST /api/v3/tools/execute/{action}`
- Google Sheets structure: "Out" tab (monthly expenses by category columns), "In" tab (income)

## Node.js → Rust Mapping
| Node.js | Rust |
|---------|------|
| `finance-record.js` → `FinanceRecord` class | `rewind_core::finance::FinanceRecord` struct |
| `category-rules.js` → `categorize()` | (now split) `rewind_finance::category_rules` + `rewind_core::finance::Category` |
| `quota-tracker.js` → `QuotaTracker` class | (todo) `rewind_finance` module |
| `composio-adapter.js` → `ComposioAdapter` | (todo) `rewind_finance` module |
| `task-emitter.js` → `emitTasks()` | `rewind_finance::task_emitter::TaskEmitter` |
| `cli.js` → CLI entry | `rewind_cli::main()` with clap |

## Statement ingestion
- Best abstraction: **PDF/CSV → normalized transactions → deterministic tagging → scheduler signals**.
- Implemented new crate: `rewind-ingest`.
  - Output type: `StatementTransaction` (bank-agnostic)
  - First parser scaffold: Capital One US text parser (ported from python regex approach).

## PDF parsing risk
- Bank statements vary wildly. Most robust strategy is:
  1. PDF → text extraction (try multiple extractors)
  2. Bank-specific regex parser over the extracted text lines

## OpenClaw integration (sidecar)
- Using OpenClaw in the background adds a runtime dependency **but removes** a huge amount of work:
  - OAuth/login flows (Claude setup-token + OpenAI OAuth)
  - WhatsApp delivery stack and routing
- Recommended approach:
  - Keep Rewind algorithm fully Rust-native.
  - Use OpenClaw as an optional sidecar for auth + messaging early.

## Claude/OpenAI auth
- `openclaw models auth setup-token --provider anthropic` works for Claude.
- `openclaw models auth login --provider openai-codex` works for OpenAI (may route through antigravity login in this setup).
- Rewind should eventually own its own auth state (`~/.rewind/auth.json`), but can shell out to OpenClaw now.

---
*Update after every 2 view/browser/search operations*
