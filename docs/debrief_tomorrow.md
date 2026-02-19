# Debrief for tomorrow (Rewind rust-native)

## What landed tonight
- Rewind is now an OSS-shaped Rust workspace (README + MIT LICENSE).
- `rewind setup` captures goals + timezone (IANA) and writes `~/.rewind/goals.md` + `~/.rewind/profile.json`.
- `rewind finance sync --csv amex.csv` parses AMEX CSV and emits grouped finance tasks.
- `rewind plan-day` combines:
  - explicit goals (parsed from goals.md)
  - implicit finance signals (from statement)
  - deterministic routing (keyword overlap + synonym expansion)
  - and prints temporal anchors: "Now" + statement date range.
- `rewind-ingest` now has parsers:
  - Capital One US (text) scaffold
  - Chase debit (text) parser + running balance support

## How to use it tomorrow morning
```bash
cd ~/rewind
git checkout rust-native
git pull

cargo test -q
cargo install --path rewind-cli --locked

rewind setup
rewind finance sync --csv amex.csv
rewind plan-day --csv amex.csv --limit 10
```

## If on macOS and auth fails
Rewind no longer requires OpenClaw. Auth is optional.

Claude OAuth via Claude Code CLI:
```bash
npm i -g @anthropic-ai/claude-code
rewind auth claude-setup-token
```

Or paste token:
```bash
rewind auth paste-anthropic-token
```

## Next work items
- Deadline goals format in goals.md (OpenClaw-style markdown blocks with due + tz)
- Time-blocked scheduling + export to Google Calendar via Composio (v3)
- Intent classification as first-class Rewind module (no OpenClaw sidecar)
- Improve deterministic routing: route by merchant/category/transaction text (already partially done via samples)
