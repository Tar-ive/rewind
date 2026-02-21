# Rewind-native iMessage Reminders Plan (Forked from ZeroClaw patterns)

Date: 2026-02-21

## Decision
Rewind will **not** depend on ZeroClaw runtime for reminders.
We will fork the relevant channel/scheduling patterns and implement a **Rewind-native reminder stack**.

## Product Goal
Use Rewind’s scheduling intelligence (LTS/MTS/STS) to drive reminders directly:
- LTS decides what matters over horizon
- MTS adapts when disruptions happen
- STS decides near-term execution order
- Reminder engine turns scheduled tasks into delivery actions (iMessage first)

---

## 1) Architecture (Rewind-native)

### A. Scheduler Core (existing + expanding)
- `rewind-core/src/lts.rs` (daily planning intent generation)
- `rewind-core/src/mts.rs` (swap in/out, disruptions)
- `rewind-core/src/sts.rs` (short-term priority queue)

### B. Reminder Policy Layer (new)
`rewind-core/src/reminders/`
- `policy.rs`
  - max reminders/day
  - lead-time tiers (24h / 2h / 15m)
  - quiet hours / DND
  - escalation rules
- `projection.rs`
  - converts LTS/MTS/STS tasks into reminder candidates
- `dedupe.rs`
  - deterministic dedupe key generation

### C. Delivery Layer (new)
`rewind-cli/src/delivery/`
- `intent_store.rs` (JSON/SQLite persistence)
- `dispatcher.rs` (select due reminders and dispatch)
- `channels/imessage.rs` (forked logic, hardened)
- `channels/mod.rs`

### D. Runtime Store (new)
`~/.rewind/reminders.db`
- tables:
  - `reminder_intents`
  - `delivery_attempts`
  - `acks`
  - `dedupe_keys`

---

## 2) iMessage Channel (forked behavior)

Fork concepts from ZeroClaw into Rewind:
- AppleScript send via `osascript`
- strict target validation (E.164 phone / email)
- AppleScript escaping for message + target
- macOS capability check and explicit error messages

Rewind-specific API:
- `rewind reminders send-imessage --to <target> --text <msg>`
- internal trait `DeliveryChannel::send(ReminderMessage)`

---

## 3) Bake LTS/MTS/STS into Reminder Generation

## Inputs
- Tasks from LTS/MTS/STS with:
  - urgency
  - deadline
  - status (Backlog/Active/InProgress/etc.)
  - energy/cognitive cost

## Scoring model for reminders
`reminder_priority = f(STS_priority, MTS_disruption_flag, LTS_readiness, deadline_proximity)`

Suggested deterministic rule set:
1. If STS priority is urgent OR deadline < 24h → schedule 2 reminders (2h + 15m)
2. If MTS swapped-out task re-enters active queue → immediate nudge + next checkpoint
3. If LTS readiness high but no recent progress → one motivational reminder/day max
4. Never exceed policy caps and quiet-hour boundaries

## Output
`ReminderIntent` (versioned schema):
- id, task_id, goal_id
- channel, recipient
- title/body
- send_at_utc
- dedupe_key
- source (`lts|mts|sts`)

---

## 4) CLI Surface

### New commands
- `rewind reminders plan --from-scheduler`
- `rewind reminders list`
- `rewind reminders dispatch`
- `rewind reminders send-imessage --to ... --text ...`
- `rewind reminders ack --id ...`

### Existing commands to connect
- `rewind lts plan` should optionally emit reminder candidates
- `rewind calendar push-google` and reminders should share the same task identity + dedupe strategy

---

## 5) Incremental Build Plan

### Phase 1 (MVP, 1-2 days)
- Add `reminders.db`
- Add `ReminderIntent` v1 schema + persistence
- Add iMessage send command (manual)
- Add `rewind reminders dispatch` for due intents

### Phase 2 (Scheduler integration)
- Project STS tasks into reminder intents
- Add MTS disruption-triggered reminders
- Add LTS low-frequency progress reminders

### Phase 3 (Policy + safety)
- Quiet hours + max/day
- dedupe/ack logic
- retry/backoff with bounded attempts

### Phase 4 (observability)
- delivery logs
- reminder effectiveness metrics (sent/acked/ignored)
- policy tuning hooks

---

## 6) Acceptance Criteria

- Rewind can generate reminders directly from scheduler output without external runtime
- Rewind can deliver iMessage on macOS securely
- Dedupe prevents duplicate sends across reruns/restarts
- Reminder cadence reflects LTS/MTS/STS logic (not static timer spam)

---

## 7) Notes on Build Artifacts / Velocity

Do **not** commit build artifacts (`target/`) to git.
Use bounded local cache rotation (already added in disk maintenance) to preserve velocity while controlling disk growth.
