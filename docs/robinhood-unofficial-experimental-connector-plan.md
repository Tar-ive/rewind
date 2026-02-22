# Rewind Plan: Experimental Robinhood (Unofficial) Read-Only Connector + Vault Order Capture

**Date (UTC):** 2026-02-22  
**Owner:** Rewind `rust-native` branch  
**Scope:** Experimental integration only (read-only by default), with order details persisted into Rewind vault artifacts.

---

## 1) Current Status

### Repo state
- Branch: `rust-native`
- Remote tracking: `origin/rust-native`
- Local is **behind by 1 commit** (`ebabc98` on origin)
- Working tree: clean except untracked `target` symlink

### Codebase state relevant to this request
- `rewind-finance` currently has AMEX ingestion + deterministic task emitter.
- No existing Robinhood connector implementation in `rewind-finance`.
- No production vault persistence module currently wired for finance provider artifacts.
- `rewind-cli` has finance/calendar/reminders commands and is a good place to add connector commands.

### Policy/risk status
- `sanko/Robinhood` documents a private/unofficial API. It may break without notice and could violate platform terms.
- Must be explicitly marked **experimental** and **opt-in**.

---

## 2) Goal

Enable Rewind to:
1. Pull holdings/orders from unofficial Robinhood endpoints in an **experimental read-only mode**.
2. Persist normalized order details into a local Rewind vault artifact store.
3. Keep a strict safety posture: no order placement/cancel in this phase.

---

## 3) Proposed Architecture

## Components
1. **Connector module (rewind-finance)**
   - `rewind-finance/src/robinhood_unofficial.rs`
   - Handles auth/session + request wrappers + typed response parsing.

2. **Vault persistence module (rewind-core or rewind-finance)**
   - `rewind-finance/src/vault_store.rs` (or equivalent)
   - File-backed JSONL/JSON storage in `~/.rewind/vault/finance/robinhood/`

3. **CLI commands (rewind-cli)**
   - `rewind finance robinhood sync --mode read-only`
   - `rewind finance robinhood holdings`
   - `rewind finance robinhood orders --since <date>`
   - `rewind finance robinhood status`

---

## 4) Vault Data Model (Order Details)

Persist two layers:

1. **Raw source snapshot** (for forensics/replay)
- Path: `~/.rewind/vault/finance/robinhood/raw/orders/YYYY-MM-DDTHHMMSSZ.json`
- Content: exact upstream response payload (with sensitive values redacted where needed)

2. **Normalized order records** (for Rewind logic)
- Path: `~/.rewind/vault/finance/robinhood/orders.jsonl`
- One JSON object per order event/upsert

Suggested normalized schema:

```json
{
  "provider": "robinhood_unofficial",
  "account_id": "string",
  "order_id": "string",
  "client_order_id": "string|null",
  "symbol": "AAPL",
  "asset_type": "equity|crypto|option|unknown",
  "side": "buy|sell|unknown",
  "order_type": "market|limit|stop|stop_limit|unknown",
  "time_in_force": "gfd|gtc|ioc|fok|unknown",
  "status": "queued|confirmed|partially_filled|filled|canceled|rejected|failed|unknown",
  "quantity": 0.0,
  "filled_quantity": 0.0,
  "limit_price": 0.0,
  "avg_fill_price": 0.0,
  "fees": 0.0,
  "submitted_at": "2026-02-22T22:00:00Z",
  "updated_at": "2026-02-22T22:01:30Z",
  "source_fetched_at": "2026-02-22T22:01:35Z",
  "source_hash": "sha256:...",
  "raw_ref": "raw/orders/2026-02-22T220135Z.json"
}
```

Also keep holdings snapshots:
- `~/.rewind/vault/finance/robinhood/holdings/YYYY-MM-DD.json`

---

## 5) Safety Controls (Required)

1. **Default read-only hard lock**
   - No POST/PUT/PATCH/DELETE calls in this phase.
   - Build-time and runtime guard.

2. **Feature flag gate**
   - Example: `finance.experimental_robinhood_unofficial = true`
   - Command errors out unless explicitly enabled.

3. **Secrets handling**
   - Store credentials/tokens in `~/.rewind/auth.json` (or dedicated secure file) with minimum scope.
   - Never print tokens/session cookies in logs.

4. **Kill switch**
   - Config toggle to disable connector immediately.

5. **Explicit warning banner**
   - CLI output on each run: unofficial/private API warning.

---

## 6) Implementation Plan (Phased)

### Phase 0 — Guardrails + scaffolding
- Add connector feature flag and warning text.
- Add CLI command skeletons for `status`, `holdings`, `orders`, `sync`.
- Add vault paths + directory bootstrap helpers.

### Phase 1 — Read-only fetch
- Implement authenticated read requests needed for:
  - account/portfolio context
  - holdings
  - historical orders
- Add retry/backoff and response validation.

### Phase 2 — Vault persistence
- Write raw payload snapshots with timestamped names.
- Normalize and append order records into `orders.jsonl`.
- Idempotency rule: upsert by `(provider, account_id, order_id, updated_at)`.

### Phase 3 — Rewind integration
- Convert normalized orders/holdings to internal finance records/signals.
- Surface summary in `rewind finance robinhood sync` output:
  - counts (new/updated)
  - latest order status breakdown
  - holdings exposure summary

### Phase 4 — Tests + docs
- Unit tests for normalization and idempotent writes.
- Fixture-based tests for parser stability.
- User docs: setup, risks, troubleshooting, disable instructions.

---

## 7) CLI UX (Draft)

```bash
rewind finance robinhood status
rewind finance robinhood holdings
rewind finance robinhood orders --since 2026-01-01
rewind finance robinhood sync --mode read-only
```

Example sync output:
- `Fetched holdings: 14`
- `Fetched orders: 238 (new: 4, updated: 9)`
- `Vault write: ~/.rewind/vault/finance/robinhood/orders.jsonl`

---

## 8) Acceptance Criteria

- [ ] Connector works in explicit experimental read-only mode.
- [ ] Holdings are fetchable from CLI.
- [ ] Order details are stored in vault raw + normalized formats.
- [ ] Re-running sync is idempotent (no duplicate logical orders).
- [ ] No secrets are printed in logs.
- [ ] One-command kill switch disables connector.

---

## 9) Non-Goals (for now)

- No trade placement/cancellation.
- No production guarantee for unofficial endpoints.
- No mobile/web automation fallback in this phase.

---

## 10) Recommended Next Action

1. Pull latest remote commit to align branch.  
2. Implement **Phase 0 + Phase 1** in one PR.  
3. Add **Phase 2 vault persistence** immediately after, so order detail retention is guaranteed early.
