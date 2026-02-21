# Rewind rust-native CLI — notes for an iOS client / on-device Rust bridge

Goal: document the current `rust-native` CLI surface area and how well it maps to an iOS app architecture similar to `dnakov/litter`.

## Repo / branch
- Repo: https://github.com/Tar-ive/rewind
- Branch: `rust-native`

## What exists today (from README)
Rewind is a long-term scheduler (LTS/MTS/STS) driven by:
- explicit goals (L/M/S)
- implicit signals (starting with credit card statements)
- file-backed personalization (e.g. `~/.rewind/goals.md`, `~/.rewind/profile.json`)

Status highlights called out in README:
- `rewind setup` → writes `~/.rewind/goals.md` + `~/.rewind/profile.json`
- `rewind finance sync --csv amex.csv` → parses AMEX CSV → emits grouped tasks
- `rewind plan-day --csv amex.csv` → combines goals + statement-derived tasks
- `rewind-ingest` scaffold + bank PDF→text parser scaffolds
- deterministic routing scaffold in `rewind-core`

## Workspace layout (Cargo workspace)
From `Cargo.toml` (workspace members):
- `rewind-core`
- `rewind-ingest`
- `rewind-finance`
- `rewind-cli`

`rewind-cli` builds a `rewind` binary.

## CLI surface (from `rewind-cli/src/main.rs`)
Top-level commands (Clap):
- `rewind setup`
  - one-time setup; captures goals and writes `~/.rewind/*`
- `rewind config-init`
  - writes `~/.rewind/config.toml` defaults (ZeroClaw-style)
- `rewind plan-day [--csv <path>] [--limit <n>]`
  - prints a basic plan for today
- `rewind calendar <subcommand>`
  - `export-ics [--csv] [--limit] [--energy] [--prefix]` → prints ICS
  - `push-gcalcli ...` → uses gcalcli import as fallback
  - `connect [--client-json]` → OAuth connect (feature-gated)
  - `status` → shows whether connected (feature-gated)
  - `push-google ... --mode {nudge|visualize-sts}` → direct API (feature-gated)
- `rewind chat`
  - interactive TUI chat
- `rewind finance sync [--csv] [--account]`
  - deterministic AMEX CSV parse + task emit
- `rewind onboard decide [--statement]`
  - outputs **ONLY JSON** with next question / proceed signal
- `rewind auth <subcommand>`
  - `claude-setup-token` (Claude Code OAuth flow)
  - `paste-anthropic-token`
  - `paste-openai-api-key`
  - `openai-oauth` (guided login; doesn’t extract tokens yet)
- `rewind reminders <...>`
  - reminder queue operations (module exists; details depend on `reminders_cmd`)

### Notes on iOS relevance
For an iOS app, the most “UI-friendly” commands are:
- `setup` (onboarding)
- `onboard decide` (already JSON-only output; great as an API boundary)
- `finance sync` (deterministic, can be converted to structured JSON output)
- `plan-day` (can become JSON output)
- `calendar export-ics` (already produces a portable artifact)
- `reminders` (if it is queue-based / structured)

The TUI (`chat`) is not directly useful on iOS, but the underlying chat/LLM logic may be.

## Statements support (from `docs/statements.md`)
Supported / planned sources:
- AMEX CSV (explicit column schema documented)
- Chase Debit PDF (expects PDF→text output)
- Capital One US PDF (parser scaffold; expects PDF→text output)

Design guidance:
- deterministic parsing first
- use LLM only for ambiguity
- keep per-bank parsers isolated and versioned

## Core types hint (from `rewind-core/src/lib.rs`)
`rewind-core` exports scheduler concepts + a categorizer that maps transaction descriptions to:
- categories (tuition/credit-card/family-support/savings/housing/etc.)
- goal tags and canned goal names

This implies a clean iOS boundary:
- ingest transactions → normalize → categorize → tasks → schedule/reminders

## Mapping to `dnakov/litter` iOS architecture
`litter` demonstrates:
- two-mode app: remote-only vs bundled on-device Rust
- packaging Rust bridge as an `.xcframework`
- Swift ↔ Rust boundary via a small bridge + JSON-RPC client

### How this maps to Rewind
A Rewind iOS app could mirror the same two modes:
1) **Remote-only**: Swift UI calls a remote Rewind service (or runs CLI remotely)
2) **On-device bridge**: embed `rewind-core` + selected modules in an xcframework

Recommended “bridge API” candidates (thin + stable):
- `onboard_decide(state) -> json`
- `setup_apply(answers) -> writes to app sandbox instead of ~/.rewind`
- `finance_sync_amex(csv_text|bytes) -> normalized_txns + tasks`
- `plan_day(goals, txns, limit) -> plan`
- `calendar_export_ics(plan, prefs) -> ics_text`
- `reminders_project(tasks, policy) -> reminders`

### Key adaptation needed
Current CLI writes to `~/.rewind/*`. On iOS, storage must be redirected to:
- app sandbox (Application Support / Documents), and/or
- Keychain for secrets (`auth.json`)

This suggests creating a reusable Rust "engine" layer that accepts an explicit `RewindPaths` / storage abstraction rather than hardcoding `~/.rewind`.

## Suggested next doc to write later
- "RewindBridge v0" API: JSON schemas for inputs/outputs for each bridge function.
- Storage/paths plan for iOS: where `goals.md`, `profile.json`, `auth.json`, task buffers, and logs live.
- PDF→text on iOS options and parser contract.
