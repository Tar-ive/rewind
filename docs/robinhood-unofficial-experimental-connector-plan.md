# Rewind Plan (Replanned): `robin_stocks`-based Experimental Robinhood Connector + Vault Order Capture

**Date (UTC):** 2026-02-22  
**Input change:** Use `https://github.com/jmfernandes/robin_stocks` as the integration base.  
**Scope:** Experimental + read-only by default; persist order details in Rewind vault.

---

## 1) Status

- Prior plan was based on generic unofficial endpoints (`sanko/Robinhood` docs).
- New direction: leverage `robin_stocks` Python library as an adapter layer for Robinhood account/holdings/order reads.
- Repo branch (`rust-native`) is up to date with the doc commit already pushed.

---

## 2) Why this replan

Using `robin_stocks` gives:
- A maintained Python wrapper with existing auth/session handling patterns.
- Faster bootstrap vs building every HTTP call from scratch in Rust.
- Coverage for holdings/orders/account data paths (subject to breakage from upstream changes).

Tradeoff:
- Adds a Python runtime dependency and subprocess boundary from Rust CLI.

---

## 3) Architecture (updated)

## A) Python bridge layer (new)
Create a small script inside Rewind repo, e.g.:
- `rewind-finance/scripts/robinhood_bridge.py`

Responsibilities:
1. Login/auth using `robin_stocks.robinhood`
2. Fetch data (holdings, open/closed orders, account profile)
3. Output strict JSON payloads to stdout (no secrets in logs)

## B) Rust connector wrapper
In `rewind-finance` add module:
- `src/robinhood_bridge.rs`

Responsibilities:
- Spawn Python bridge with controlled env vars
- Parse/validate JSON responses
- Normalize to Rewind schemas
- Hand off to vault writer

## C) Vault persistence
Store both raw and normalized:
- Raw snapshots: `~/.rewind/vault/finance/robinhood/raw/orders/<timestamp>.json`
- Normalized ledger: `~/.rewind/vault/finance/robinhood/orders.jsonl`
- Holdings snapshots: `~/.rewind/vault/finance/robinhood/holdings/<date>.json`

---

## 4) CLI commands (updated)

Add to `rewind-cli`:

```bash
rewind finance robinhood status
rewind finance robinhood holdings
rewind finance robinhood orders --since 2026-01-01
rewind finance robinhood sync --mode read-only
```

`sync` should:
1. fetch holdings/orders via Python bridge,
2. write raw snapshots,
3. append normalized order records (idempotent upsert).

---

## 5) Vault schema (order details)

Use normalized JSONL schema (same core as previous plan):

```json
{
  "provider": "robinhood_unofficial_robin_stocks",
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

Idempotency key: `(provider, account_id, order_id, updated_at)`.

---

## 6) Safety controls (unchanged, required)

1. **Read-only hard lock** in this phase (no order placement/cancel endpoints).
2. **Feature flag** required to enable connector:
   - `finance.experimental_robinhood_unofficial = true`
3. **Secret hygiene**:
   - credentials via env/auth file only,
   - never print token/session/2FA secrets.
4. **Kill switch** config toggle.
5. **CLI warning banner**: unofficial/private API risk.

---

## 7) Phased implementation (replanned)

### Phase 0: Scaffold + warnings
- Add command stubs + feature flag + warnings.
- Add vault path bootstrap.

### Phase 1: Python bridge MVP
- Implement `status`, `holdings`, `orders` JSON outputs.
- Validate bridge error handling and deterministic output schema.

### Phase 2: Rust integration + persistence
- Wire bridge execution in `rewind-finance`.
- Write raw snapshots + normalized `orders.jsonl`.
- Implement dedupe/idempotent upsert.

### Phase 3: Rewind signal integration
- Convert holdings/orders into Rewind finance signals/tasks.
- Add summary output for sync command.

### Phase 4: Tests + hardening
- Fixture tests for parser + normalization.
- Redaction tests for logs.
- Docs for setup/disable/troubleshooting.

---

## 8) Acceptance criteria

- [ ] Can fetch holdings through `robin_stocks` bridge.
- [ ] Can fetch order history and persist into Rewind vault.
- [ ] No duplicates on repeated sync runs.
- [ ] Read-only lock enforced.
- [ ] Secrets are never logged.

---

## 9) Non-goals (still)

- No trade execution/cancel in this phase.
- No guarantee of API stability (unofficial surface).
- No production SLA.

---

## 10) Next action

Implement **Phase 0 + Phase 1** in a single PR, then **Phase 2** immediately after so vault order capture is live as early as possible.
