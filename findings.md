# Rewind Rust CLI — Findings

## Architecture
- Workspace: `rewind-core` (types), `rewind-finance` (Composio adapter), `rewind-cli` (binary)
- Mirrors Node.js `rewind-finance` package which already works live with Composio v3 API
- Composio v3 endpoints: `GET /api/v3/connected_accounts`, `POST /api/v3/tools/execute/{action}`
- Google Sheets structure: "Out" tab (monthly expenses by category columns), "In" tab (income)

## Node.js → Rust Mapping
| Node.js | Rust |
|---------|------|
| `finance-record.js` → `FinanceRecord` class | `rewind_core::finance::FinanceRecord` struct |
| `category-rules.js` → `categorize()` | `rewind_core::categorizer::categorize()` |
| `quota-tracker.js` → `QuotaTracker` class | `rewind_finance::quota::QuotaTracker` struct |
| `composio-adapter.js` → `ComposioAdapter` | `rewind_finance::adapter::ComposioAdapter` |
| `task-emitter.js` → `emitTasks()` | `rewind_finance::emitter::emit_tasks()` |
| `cli.js` → CLI entry | `rewind_cli::main()` with clap |
| `goal_logic.py` → `plan_goal_steps()` | `rewind_core::goals::plan_goal_steps()` |

## Claude Auth
- `claude setup-token` uses OAuth browser flow → stores token locally
- OpenClaw stores auth in `~/.openclaw/credentials/`
- Rewind should store in `~/.rewind/auth.json`

---
*Update after every 2 view/browser/search operations*
