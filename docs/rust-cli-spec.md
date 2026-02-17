# Rust CLI Rewind (rust-cli branch)

## Vision
Build a Rust-native variant of Rewind (`rewind-cli`) that runs alongside Claude agents by leveraging the `claude-agents` SDK and `claude setup-token` for authentication. The CLI must:
- Be compact (<5 MB binary) and deterministic where possible (cache stable IDs, use deterministic filters, skip LLMs when logic suffices). Reserach on other robust Rust CLI code mainly https://github.com/zeroclaw-labs/zeroclaw.git to understand structuring, key details, compilation, 
- Route only routine text generation to a cheap LLM (configured via `CHEAP_LLM`), while heavier reasoning still uses the Claude Agents workflow.
- Automate finance planning (Composio → Google Sheets) and reminders (Claude + WhatsApp) while tracking webhook/cron states.
- Treat rollback as first-class: log rollback points in memory/TOOLS, track cron/webhook statuses, and commit every change with the `gh` CLI workflow.

## Component breakdown
1. **Entry point (rewind-cli binary)**
   - CLI/daemon spawns: scheduler core, profiler, automation watchers, webhook watcher, REST/CLI listener, and finance ingestion pipeline.
   - Config reads from `rust-cli.toml` or environment variables (including `CLAUDE_TOKEN`, `COMPOSIO_API_KEY`, `GOOGLE_SHEET_ID`, `REDIS_URL`, `WHATSAPP_NUMBER`, `CHEAP_LLM`).
   - The `claude-agents` adapter (`claude_adapter`) manages pairing via `claude setup-token` and caches stable session IDs to avoid repeated pairing sequences.

2. **Schedulers (Rust)**
   - **LTS (`rewind-core::lts`)**: daily planning that scores backlog items using `score = 0.45*urgency + 0.3*priority + 0.15*energy_alignment + 0.1*duration_score`. Plans persist `PlanId`s for traceability and rollback. Outputs feed the MLFQ queue and create `long-term` tasks tied to your goals (finance control, SF internship, opening Rewind to 100 people).
   - **MTS (`rewind-core::mts`)**: triggers on `ContextChangeEvent` (from ContextSentinel) and computes swaps based on freed/lost minutes. Maintains deterministic swap logs; when rollback is needed, the swap history can replay the previous schedule.
   - **STS (`rewind-core::sts`)**: 4-level priority queue (P0–P3). When `EnergyMonitor` reports low energy (<3), STS demotes heavy tasks and auto-delegates to `GhostWorker` with deterministic logic (no LLM needed). Routine routing decisions skip LLM entirely; only churn notes or reminder copy uses the cheap LLM.

3. **Profiler agent (Rust)**
   - Consolidates explicit signals (task completions, finance confirmations, manual habit logs) and implicit ones (energy dips, missed plans, finance overruns, WhatsApp health cron alerts).
   - Maintains a `UserProfile` with arrays for peak hours, energy curve, `finance_discipline`, `focus_habit_score`, and `goal_adherence`. Stores everything in Redis/SQLite so the scheduler can query quick metrics without hitting LLMs.
   - Emits `ProfileSignal`s to the scheduler: e.g., low `energy_level` defers intense tasks, high `finance_discipline` raises finance-planning slots, repeated `goal_adherence` boosts long-term goal weighting.
   - Cheap LLM use is limited to summary sentences when profiling needs narration; otherwise, the profiler operates purely on numeric heuristics.

## Finance planning + Composio integration
- **Data flow**: Composio pulls Google Sheets rows. The CLI ingests them, categorizes by account (Chase, AMEX, Zelle, etc.), and stores them as `FinanceRecord`s. Deterministic filters handle category matching; no LLM required.
- **Task generation**: Each row triggers Rewind tasks tagged with goal types (long-term finance control, medium-term conversions, short-term payments). The profiler tags these tasks with `financial_focus` so STS/MTS schedule them appropriately.
- **Automation**: When totals exceed thresholds, the system constructs reminder copy (via cheap LLM) and routes it through the WhatsApp automation (reuse the OpenClaw `message` pattern). However, budget calculations and alert triggers remain deterministic.

## Reminders + WhatsApp
- The CLI reuses the same WhatsApp integration patterns as OpenClaw/ZeroClaw: an automation watcher runs diagnostics, forms a structured status update, and sends via WhatsApp API (with webhook handling). Each reminder job logs its cron/webhook status (recorded in Redis + git commit message) and caches webhook IDs for rollback.
- Routine reminder text (e.g., next task) uses the cheap LLM configured by `CHEAP_LLM`; only when the reminder requires creative reasoning (e.g., summarizing a new finance row) does it call the Claude Agents system.

## Rollback / monitoring policy
- Every webhook status change, cron trigger, or automation update appends a record to `/workspace/logs/cron-history.log`. Use the `gh` CLI workflow to commit these logs after each batch.
- The memory entry about rollback workflows lives under `memory/2026-02-17.md` and is referenced by the nightly drift audit. Keep this as the “source of truth” for rollbacks.
- Cache stable IDs for cron jobs, webhook listeners, and plan versions to allow deterministic rollback without LLMs.

## Productivity notes
- Use deterministic filtering (regex, threshold comparisons) before considering LLM routes.
- Default to cheap LLM (Claude Sonnet 4.5 or equivalent) for repetitive text; upgrade to the primary Claude model only for higher-order reminders. Profiler’s textual outputs should first check if logic covers the need; fall back to LLM only when the data is ambiguous.
- Document all CLI commands (build, run, plan-day, sync-finance) plus linking instructions for `claude setup-token` in this repo’s docs, and mention that building the binary uses `cargo build --release --locked`.

## Git workflow
- Use `gh` CLI to create PRs / push branches. Every doc or code change must be committed with git (via `git add`/`commit`) and pushed; treat rollback as first-class by noting each change’s fallback plan in the commit message and logs.
- Example: `gh repo sync` after commits, `gh` to open PR. Keep watchers for cron state and log them in `logs/cron_history.log` before pushing.
