# Rewind Rust CLI — Task Plan

## Goal
Build a Rust-native scheduler + CLI (`rewind`) that:
1. Captures **long-term goals** (initial setup wizard + WhatsApp capture later)
2. Runs the **LTS/MTS/STS** scheduling algorithm against explicit goals + implicit signals
3. Ingests statements (CSV now; PDF later, bank-specific)
4. Uses **code routing** + optional LLM intent classification (Claude/OpenAI) for goal alignment
5. Ships with a setup flow that a fresh GitHub clone can run

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

### Phase 2: Finance Watcher (statements + finance-only goals)
- [x] AMEX CSV parsing + category rules + task emitter (real-data tests)
- [x] `rewind finance sync --csv amex.csv`
- [ ] Add statement-ingest abstraction (CSV + PDF text)
- [ ] Implement Capital One US parser in Rust (ported from `capitalone_us.py`)
- [ ] Add PDF text extraction strategy (crate choice + fallback)
- [ ] Add Composio adapter (optional) later
- [ ] Commit + push

### Phase 3: CLI Entry Point
- [x] Create `rewind-cli` binary crate
- [x] Subcommands: `finance sync` (AMEX CSV) + `auth` helpers
- [x] Wire finance parser + task emitter into CLI (`rewind finance sync --csv amex.csv`)
- [x] Calendar:
  - [x] ICS export
  - [x] Google Calendar direct API (feature `gcal`) + connect/status
  - [x] Nudge mode (max 3/day) as default
  - [x] Graveyard cancelled events + preserve " - done"
- [x] Implement `rewind chat` (TUI skeleton)
- [ ] Tighten `rewind chat` UX:
  - [ ] Daily logs to `~/.rewind/chat/YYYY-MM-DD.md`
  - [ ] Startup splash "Rewind" + session header (Codex-style)
  - [ ] Slash commands: /help, /status, /calendar, /goals, /statements, /reminders (scaffold)
  - [ ] Tone rules: wellwisher voice, respectful, avoid pathologizing language
  - [ ] Keybind help: `?` for shortcuts
- [ ] Add `status` / `cache` / `configure`
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
