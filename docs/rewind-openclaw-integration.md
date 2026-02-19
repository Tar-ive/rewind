# Rewind ↔ OpenClaw Integration (Evaluation)

## What Rewind is
Rewind is a long-term scheduler (LTS/MTS/STS) that helps users achieve explicit long-term goals.

**Inputs**
- Explicit goals: user-provided (setup wizard; later via WhatsApp capture)
- Implicit signals: transaction/statement activity (CSV/PDF), habits, calendars, etc.

**Outputs**
- A ranked task plan (short/medium/long horizon)
- Reminders + check-ins (WhatsApp)
- Optional reports/summaries

## What `rewind-finance` is
A subdomain of Rewind focused on finance-related goals and financial-signal ingestion.
It should stay modular: it produces normalized transactions + finance-tagged tasks/signals.

## Using OpenClaw in the background — what complexity does it add?
### Adds
- **Runtime dependency** (sidecar) unless we re-implement channels/auth.
- More moving parts: OpenClaw gateway + plugins + config.
- Need to decide "who owns state": OpenClaw (~/.openclaw) vs Rewind (~/.rewind).

### Removes (major wins)
- OAuth + token storage flows already exist:
  - `openclaw models auth setup-token --provider anthropic`
  - `openclaw models auth login --provider openai-codex`
- WhatsApp + Telegram + Slack messaging stack already exists.
- Cron + reminders + delivery routing already exists.

## Recommendation: Sidecar-first, Rust-native core
**Keep Rewind's algorithm and domain logic fully Rust-native.**

Then choose one of these integration modes:

### Mode A (recommended for now): OpenClaw as sidecar
- Rewind shells out to `openclaw ...` for:
  - auth flows
  - message delivery
- Pros: fastest path, minimal surface area, proven.
- Cons: users must install OpenClaw.

### Mode B: Link/port selected OpenClaw/ZeroClaw components
- Port only the parts we need in Rust:
  - OAuth device/login flows
  - channel plugins (WhatsApp)
- Pros: fewer external dependencies in the long run.
- Cons: large engineering lift; WhatsApp in particular is non-trivial.

### Mode C: Provide both
- Default: Mode A.
- Advanced users: Mode B modules.

## Feasibility check
✅ **Yes, this is possible**.

The critical engineering risks are:
1. **WhatsApp plugin parity** (hard). Suggest keep OpenClaw sidecar early.
2. **PDF parsing per bank** (medium). Strategy: extract text robustly; bank parsers are regex/format-specific.
3. **Auth UX** (medium). We can reuse OpenClaw CLI now; later embed OAuth in Rust.

## Setup flow for new GitHub users
`rewind setup` should:
1. Ask about long-term goals (store as JSON/YAML)
2. Ask which integrations they want:
   - OpenClaw sidecar? (recommended)
   - Statement sources (CSV now; PDF later)
3. If OpenClaw enabled:
   - Run `rewind auth claude-setup-token` and/or `rewind auth openai-oauth`
4. Ask for statement files to import
5. Run `rewind finance sync ...` and show initial plan
