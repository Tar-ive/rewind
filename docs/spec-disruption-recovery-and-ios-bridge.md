# Rewind Spec Addendum: Disruption Recovery Primary Flow + iOS Bridge Notes

Date: 2026-02-21
Branch: `rust-native`

This document captures:
1) the target **Primary Flow (Disruption Recovery)** architecture,
2) how it maps to current `rust-native` implementation status,
3) the iOS/on-device Rust bridge notes and API direction.

---

## 1) Primary Flow (Disruption Recovery) — target behavior

1. **Context Sentinel** monitors Google Calendar, Gmail, Slack APIs.
   - Detects calendar change (example: meeting extended by 45 min).
   - Emits `ContextChangeEvent` to Disruption Detector.

2. **Disruption Detector** analyzes the event.
   - Queries Profiler Agent (e.g. “is user typically affected by meeting overruns?”).
   - Classifies severity (e.g. `major`, with cascade impact count).
   - Emits `DisruptionEvent` to Scheduler Kernel.

3. **Scheduler Kernel** handles disruption.
   - Queries Energy Monitor for `energy_level`.
   - Queries Profiler for `peak_hours` and `avg_task_durations`.
   - Runs MTS swap engine.

4. **MTS swap + STS reorder**.
   - Example: move non-critical gym task to tomorrow buffer.
   - Pull critical pset into peak focus slot.
   - STS re-optimizes remaining task order via MLFQ.

5. **Kernel outputs**.
   - `UpdatedSchedule` -> frontend (WebSocket push).
   - `DelegationQueue` -> GhostWorker for automatable tasks.

6. **GhostWorker execution loop**.
   - Drafts replies/messages in headless browser.
   - Emits `TaskCompletionConfirmation` to Kernel.
   - User reviews (UI or voice) and approves; GhostWorker sends.

---

## 2) Spec objects / contracts (v0)

### Events
- `ContextChangeEvent`
  - `source` (`calendar|gmail|slack`)
  - `change_type`
  - `delta_minutes`
  - `timestamp_utc`
  - `payload_ref`

- `DisruptionEvent`
  - `severity` (`minor|major|critical`)
  - `cascade_count`
  - `reason`
  - `context_event_id`
  - `timestamp_utc`

- `UpdatedSchedule`
  - `day`
  - `task_order[]`
  - `swapped_out[]`
  - `swapped_in[]`
  - `energy_level`

- `DelegationQueue`
  - `items[]` where each item has `task_id`, `channel`, `draft_type`, `priority`

### Scheduler interfaces
- `run_mts(disruption_event, energy_level, profile) -> MtsResult`
- `run_sts(active_tasks, energy_level) -> OrderedTasks`
- `project_reminders(tasks, policy) -> ReminderIntent[]`

---

## 3) Honest implementation status vs this spec (rust-native)

### Implemented now
- STS core ordering (MLFQ-style) in `rewind-core/src/sts.rs`
- MTS swap/delegation primitives in `rewind-core/src/mts.rs`
- Core + finance regression tests passing:
  - `rewind-core`: 36 tests
  - `rewind-finance`: 17 tests
- Reminder queue + dispatch + iMessage send in `rewind-cli`
- Reminder send logging to Google Calendar via Rewind direct API (no gcalcli dependency in reminder logging path)

### Partially implemented
- LTS in rust-native has starter scaffolding but not full production pipeline parity
- Reminder policy uses scheduler-aware concepts but not yet fully driven by a live disruption stream

### Not implemented yet
- Real-time Context Sentinel (calendar/gmail/slack live monitor loop)
- Full Disruption Detector agent with profiler query loop
- Scheduler Kernel service with persistent event bus + WebSocket push
- GhostWorker end-to-end draft/review/send pipeline in rust-native

---

## 4) iOS client / on-device Rust bridge notes

Repo/branch context:
- Repo: `https://github.com/Tar-ive/rewind`
- Branch: `rust-native`

Current workspace crates:
- `rewind-core`
- `rewind-ingest`
- `rewind-finance`
- `rewind-cli`

### iOS architecture direction (similar to dnakov/litter)
Two modes:
1. **Remote mode**: iOS app calls remote Rewind runtime.
2. **On-device mode**: embed Rust bridge (`xcframework`) for core planning/ingest/reminders.

### Bridge API candidates (v0)
- `onboard_decide(state) -> json`
- `setup_apply(answers, paths)`
- `finance_sync_amex(input) -> normalized + tasks`
- `plan_day(goals, txns, limit) -> plan`
- `calendar_export_ics(plan, prefs) -> ics_text`
- `reminders_project(tasks, policy) -> intents`

### iOS storage adaptation requirement
Current CLI assumes `~/.rewind/*`.
For iOS this must be abstracted behind explicit paths/storage:
- Application Support / Documents for non-secret state
- Keychain for auth secrets

---

## 5) Milestones to close spec gaps

### Milestone A — Evented disruption pipeline (backend/runtime)
- Add Context Sentinel adapters for calendar/email/slack deltas
- Add Disruption Detector classifier + severity rules
- Emit `DisruptionEvent` into scheduler runtime

### Milestone B — Scheduler Kernel runtime
- Event loop to call MTS + STS on disruption
- Produce `UpdatedSchedule` snapshots + deltas
- Expose WebSocket stream for UI

### Milestone C — Delegation + review loop
- Build GhostWorker queue contracts
- Draft generation + approval state machine
- Provider/channel adapters for send actions

### Milestone D — iOS bridge
- Extract reusable engine API from CLI wrappers
- Add explicit path abstraction (`RewindPaths`)
- Define stable JSON schemas for bridge I/O

---

## 6) Acceptance criteria for this spec

- A calendar overrun event triggers an automated MTS+STS replan end-to-end.
- Updated schedule is pushed to UI in near real-time.
- Automatable tasks are drafted and surfaced for approval.
- Reminders are generated from scheduler state and logged with auditable delivery outcomes.
- Same planning/reminder core can run in iOS on-device bridge mode with sandbox-safe storage paths.
