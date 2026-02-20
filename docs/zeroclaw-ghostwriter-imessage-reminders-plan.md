# Rewind ↔ ZeroClaw plan: iMessage + reminder delivery (Ghostwriter flow)

Date: 2026-02-20

## 1) Current scheduler status in Rewind

### Verified in codebase
- **STS exists and is wired for ordering/scheduling views**
  - `rewind-core/src/sts.rs` (ShortTermScheduler implementation)
  - `rewind-cli/src/calendar.rs` (STS-based task ordering helper)
- **MTS exists (swap-in/swap-out + delegation paths)**
  - `rewind-core/src/mts.rs`
  - `rewind-finance/tests/test_sts_mts_from_amex.rs` (real-data regression)
- **LTS is not implemented/wired yet**
  - `rewind-core/src/lib.rs` exports STS/MTS modules, no `lts` module export
  - `docs/quickstart.md` already states LTS is planned and not yet wired

### Validation evidence
- `cargo test -p rewind-core --quiet` passes (34 tests)

Conclusion: **STS ✅, MTS ✅, LTS ❌ (planned)**.

---

## 2) ZeroClaw capabilities relevant to Rewind delivery

### iMessage
ZeroClaw has a first-party iMessage channel implementation:
- `src/channels/imessage.rs`
  - Polls Messages DB
  - Sends via AppleScript bridge
  - Includes target validation + AppleScript escaping hardening

Onboarding docs/code confirm:
- `src/onboard/wizard.rs` iMessage setup is **macOS-only**
- Requires Full Disk Access for terminal to read Messages DB

### Reminder/scheduling system
ZeroClaw includes native cron + schedule tool support:
- `src/cron/mod.rs` + `src/cron/scheduler.rs`
- `src/tools/schedule.rs` with actions for create/list/get/cancel/pause/resume and one-shots

Implication: ZeroClaw can act as a message/reminder delivery runtime once Rewind emits the right tasks/events.

---

## 3) Proposed architecture (Ghostwriter through Rewind)

### Goal
Rewind should remain source-of-truth for planning/scheduling logic while delegating outbound messaging/reminders to a Ghostwriter execution layer backed by ZeroClaw channels.

### Proposed split
1. **Rewind (planner core)**
   - Build/maintain tasks from signals/goals
   - Run STS/MTS (later LTS)
   - Produce normalized reminder intents

2. **Ghostwriter adapter (new in Rewind CLI)**
   - Translates reminder intents into delivery jobs
   - Chooses target channel (`imessage`, `whatsapp`, etc.) + cadence
   - Handles idempotency keys so duplicate nudges are not sent

3. **ZeroClaw runtime (delivery execution)**
   - Receives job payloads
   - Executes via schedule/cron + channel send
   - Handles channel-specific constraints and retries

---

## 4) Implementation phases

### Phase A — Reminder intent schema in Rewind
Add a stable transport schema in Rewind, e.g.:
```json
{
  "intent_id": "rw_...",
  "task_id": "...",
  "title": "Pay AMEX minimum",
  "body": "Reminder: due in 2 days",
  "priority": "high",
  "deliver_at": "2026-02-21T15:00:00Z",
  "channel": "imessage",
  "recipient": "+17373151963",
  "dedupe_key": "..."
}
```

### Phase B — Ghostwriter transport
Implement `rewind delivery` subcommands:
- `rewind delivery preview`
- `rewind delivery send --provider zeroclaw`
- `rewind delivery sync-reminders`

Initial transport options:
1. **File spool mode (recommended first)**
   - Rewind writes JSON jobs into a watched directory
   - ZeroClaw helper ingests and schedules
2. **Gateway/webhook mode (next)**
   - Rewind posts directly to a ZeroClaw endpoint/tool bridge

### Phase C — iMessage delivery profile
Create channel profile settings in `~/.rewind/config.toml`:
```toml
[delivery]
default_runtime = "zeroclaw"
default_channel = "imessage"

[delivery.imessage]
enabled = true
recipient = "+17373151963"
quiet_hours = "23:00-08:00"
```

### Phase D — Reminder policy engine
Add a deterministic policy layer:
- max reminders/day
- lead time windows (24h, 2h, 15m)
- escalation path (if no acknowledgement)
- do-not-disturb windows

### Phase E — LTS integration later
When LTS lands, have it emit long-horizon checkpoints that feed the same reminder intent pipeline.

---

## 5) What to build next (concrete backlog)

1. Add `delivery` module + reminder intent structs in `rewind-core`
2. Add `rewind delivery preview` command in `rewind-cli`
3. Add `zeroclaw_spool` writer in `rewind-cli`
4. Add end-to-end fixture test: STS output -> reminder intents -> spool file
5. Add `docs/ghostwriter-runtime-contract.md` (payload contract + retries + idempotency)
6. Add optional ack tracking (`ack_required`, `acked_at`) for adaptive reminder policy

---

## 6) Risks / constraints

- iMessage works only where ZeroClaw runs on macOS with required permissions.
- Delivery duplication risk without dedupe keys + idempotent ingest.
- Timezone drift unless Rewind stores timezone explicitly and serializes all `deliver_at` in RFC3339 UTC with display tz metadata.

---

## 7) Decision from this check

Proceed with **Ghostwriter as delivery adapter** and **ZeroClaw as runtime**, while keeping scheduling intelligence in Rewind. Build transport + reminder intent contracts first; do not block on LTS.
