# Rewind Rust CLI — Task Plan

## Goal
Build a Rust-native CLI (`rewind-cli`) that:
1. Plans financial long-term goals using the Rewind scheduling algorithm (LTS/MTS/STS)
2. Reads transactions from Composio (Google Sheets) and categorizes them
3. Emits goal-tagged tasks with urgency scoring
4. Authenticates via `claude setup-token` (like OpenClaw does)
5. Backs up daily memories to GitHub automatically

## Phases

### Phase 1: Core Types + Tests ✅ IN PROGRESS
- [x] Scaffold workspace: `rewind-core`, `rewind-finance`, `rewind-cli`
- [x] Implement `FinanceRecord`, `Category`, `GoalTag` types
- [x] Implement `GoalDescriptor`, `GoalTimeframe`, `ReadinessScore`
- [x] Implement `ExplicitSignal`, `ImplicitSignal`, `PatternType`
- [x] Implement `categorizer` module (regex-based, no LLM)
- [ ] Implement `goal_planner` module (plan_goal_steps + readiness scoring)
- [ ] Run `cargo test` on rewind-core — all tests pass
- [ ] Commit + push

### Phase 2: Finance Watcher (port from Node.js)
- [ ] Create `rewind-finance` crate with `QuotaTracker`
- [ ] Port `ComposioAdapter` (Composio v3 API: connected_accounts + BATCH_GET)
- [ ] Port `TaskEmitter` (urgency scoring, groupByGoal, summarize)
- [ ] Add `.env` file loading (dotenv crate)
- [ ] Run `cargo test` on rewind-finance
- [ ] Commit + push

### Phase 3: CLI Entry Point
- [x] Create `rewind-cli` binary crate
- [x] Subcommands: `finance sync` (AMEX CSV) + `auth` helpers
- [x] Wire finance parser + task emitter into CLI (`rewind finance sync --csv amex.csv`)
- [ ] Add `status` / `cache` / `configure` / `plan-day`
- [ ] Commit + push

### Phase 4: Claude Auth (`setup-token`)
- [ ] Research `claude setup-token` flow (OAuth browser redirect)
- [ ] Implement token storage (~/.rewind/auth.json)
- [ ] Add `rewind-cli auth` subcommand
- [ ] Test with Claude API
- [ ] Commit + push

### Phase 5: Daily Memory Backup to GitHub
- [ ] Implement `rewind-cli backup` subcommand
- [ ] Auto-commit memory/*.md files to GitHub repo
- [ ] Wire into hourly cron or post-session hook
- [ ] Commit + push

### Phase 6: Scheduling Algorithm (LTS/MTS/STS)
- [ ] Implement LTS scheduler (daily planning, score formula)
- [ ] Implement MTS scheduler (disruption recovery)
- [ ] Implement STS scheduler (4-level priority queue)
- [ ] Wire profiler signals into scheduler weights
- [ ] Commit + push

## Key Decisions
| Decision | Rationale |
|----------|-----------|
| Build on `/data` partition | Root disk at 95%, `/data` has 8GB free |
| Rust 2024 edition | Latest stable (1.93.1) |
| Workspace with 3 crates | Separation of concerns: core types, finance logic, CLI |
| Deterministic categorization | Regex/contains matching, no LLM needed |
| `claude setup-token` auth | Matches OpenClaw pattern, uses Claude Pro subscription |

## Errors Encountered
| Error | Resolution |
|-------|------------|
| Rust install failed (disk full) | Installed to `/data/rustup` + `/data/cargo` |
