# Rewind + OpenClaw: Value Proof & Productization Plan (Brutal Edition)

Date: 2026-02-21
Branch: rust-native

## Why this doc exists
Rewind has strong architecture ideas, but users care about outcomes, not elegance. This document defines a concrete way to prove value and close the current productization gaps.

---

## 1) The core problems (current reality)

1. Real-time disruption loop is not fully productized.
2. Reliability gaps still being fixed.
3. Setup friction is too high.
4. Differentiation is clear in theory, not obvious every day.

---

## 2) 7-day Proof-of-Value rubric (no-BS)

If Rewind cannot pass this, stop pretending it is ready.

### Primary success metrics
- **Planning time saved/day:** target >= 20 minutes/day
- **Deadline miss reduction:** target >= 50% reduction vs baseline week
- **Replan latency after disruption:** target <= 2 minutes from disruption to actionable update
- **User follow-through:** target >= 60% of suggested next actions accepted/completed

### Reliability metrics
- **Reminder send success rate:** target >= 99%
- **False-positive disruption rate:** target <= 10%
- **Duplicate reminder incidents:** target 0 per day
- **Crash-free days:** target 7/7

### User trust / UX metrics
- **"I know what to do next" check-ins:** >= 2 points improvement (1-10 scale)
- **Manual schedule edits needed:** <= 3/day
- **User sentiment:** net positive daily check-in by day 4+

---

## 3) What Rewind + OpenClaw can uniquely do together

### A) Real-time disruption loop completion (fastest path)
Use OpenClaw as event/control plane while Rewind becomes deterministic scheduler brain.

- OpenClaw monitors channels/integrations + emits `ContextChangeEvent`.
- Rewind classifies disruption + computes `UpdatedSchedule` + reminder intents.
- OpenClaw delivers notifications/messages across channels reliably.
- Rewind tracks outcomes + refines policy.

Why this helps now:
- OpenClaw already has robust cron, messaging, and orchestration primitives.
- Rewind focuses on core scheduling intelligence instead of rebuilding every integration first.

### B) Reliability hardening by dual-layer checks
- Rewind validates intent generation and dedupe logic.
- OpenClaw confirms dispatch success/failure and retries by policy.
- Daily watchdog job compares intended reminders vs delivered reminders.

### C) Setup friction reduction via guided onboarding agent
Add `rewind doctor` + `rewind setup-smart` backed by OpenClaw conversational flow:
- checks calendar auth, reminder channel readiness, iMessage/macOS constraints
- writes config.toml defaults
- runs test disruption + test reminder send
- reports PASS/FAIL with exact fix commands

### D) Make differentiation obvious daily (not conceptual)
Users should receive a short "Rewind Daily Delta" card:
- disruptions detected today
- what got auto-replanned
- deadlines protected
- minutes saved estimate

No delta, no product value.

---

## 4) Concrete feature map to close the 4 gaps

### Gap 1: Real-time disruption loop not fully productized
Ship sequence:
1. Event adapters (calendar first) -> `ContextChangeEvent`
2. Disruption classifier -> `DisruptionEvent`
3. Kernel orchestrator (MTS+STS) -> `UpdatedSchedule`
4. Push loop to UI + reminders

### Gap 2: Reliability gaps
- idempotency keys everywhere
- dispatch audit log + replay tool
- deterministic dedupe tests
- canary test every hour (synthetic reminder)

### Gap 3: Setup friction high
- single command bootstrap (`rewind bootstrap`)
- doctor command with actionable fixes
- one-click channel test sends

### Gap 4: Differentiation unclear in daily use
- Daily Delta card
- weekly performance summary:
  - saved minutes
  - avoided misses
  - accepted suggestions
- show "what changed because of Rewind" with concrete examples

---

## 5) Brutal go/no-go criteria (after 2 weeks)

Go forward ONLY if:
- replan latency <= 2 min median
- reminder reliability >= 99%
- measurable time saved >= 20 min/day for pilot users
- at least 70% of pilot users say they'd miss it if removed

If not met:
- narrow scope hard (calendar-only disruption + reminders)
- remove weak features
- stop shipping broad claims

---

## 6) Recommended immediate implementation order

1. Finish kernel event pipeline from contracts already added.
2. Add `rewind doctor` and bootstrap for setup reliability.
3. Add reminder delivery audit + Daily Delta output.
4. Run 7-day pilot with strict metrics and publish honest results in docs.

This is the shortest path from "interesting architecture" to "users visibly benefit every day."
