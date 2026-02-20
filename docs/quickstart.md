# Rewind CLI Quickstart (first-time user)

This is an end-to-end "from zero to first helpful reminders" setup.

> **Goal:** within ~2 minutes you should be able to run `rewind chat` and push **3 calm daily nudges** (pay/check/review) into Google Calendar.

---

## 0) Prereqs

- Rust toolchain (`cargo`, `rustc`)
- (Optional, recommended) `git`
- For Google Calendar push: you will build Rewind with the `gcal` feature

---

## 1) Clone + install

```bash
git clone https://github.com/Tar-ive/rewind.git
cd rewind
git checkout rust-native

# sanity
cargo test -q

# install rewind (with Google Calendar support)
cargo install --path rewind-cli --locked --features gcal --force
```

Check version:

```bash
rewind --version
```

---

## 2) Initialize Rewind config (ZeroClaw-style)

This writes `~/.rewind/config.toml`.

```bash
rewind config-init
cat ~/.rewind/config.toml
```

Defaults:
- `llm.provider = "openai"`
- `llm.model = "openai-codex/gpt-5.1"` (normalized when calling APIs)
- `chat.stream = true`

### Use Codex CLI quota (no API key) — recommended for fast onboarding

If you already ran `codex login`, set:

```toml
[llm]
provider = "codex-cli"
```

This makes `rewind chat` stream by running `codex exec <prompt>` as a subprocess.

---

## 3) One-time setup (timezone + goals)

```bash
rewind setup
```

Notes:
- Rewind stores local state in `~/.rewind/`
- Timezone must be an **IANA timezone** like `America/Chicago`

---

## 4) Google Calendar: OAuth + first push (nudges)

### 4.1 Create Google OAuth client secrets JSON

You need an OAuth client secret JSON downloaded from Google Cloud Console:

1) https://console.cloud.google.com/apis/credentials
2) Create Credentials → OAuth client ID
3) Application type: **Desktop app**
4) Download the JSON (commonly named `client_secret_XXXX.json`)

### 4.2 Connect Rewind to Google Calendar

```bash
rewind calendar connect --client-json /path/to/client_secret_XXXX.json
rewind calendar status
```

### 4.3 Test a push (default: max 3 nudges/day)

```bash
# optional: use the included demo statement
rewind finance sync --csv amex.csv

# push 3 calm nudges (pay/check/review)
rewind calendar push-google --mode nudge --csv amex.csv --calendar-id primary
```

What to expect:
- **At most 3 events/day**
- De-stacked time windows (morning/afternoon/evening)
- Re-runs update existing events (stable iCalUID)
- Orphaned Rewind events get moved to an end-of-day graveyard and marked **CANCELLED**
- If you manually append ` - done` to an event title, Rewind preserves it

---

## 5) Statements: AMEX CSV (works) + Chase Debit PDF (parser exists, not yet wired to CLI)

### AMEX CSV (recommended demo)

```bash
rewind finance sync --csv amex.csv
rewind plan-day --csv amex.csv --limit 10
```

See `docs/statements.md` for the AMEX CSV schema.

### Chase Debit (PDF)

Current status:
- Rust parser exists: `rewind-ingest/src/parsers/chase_debit.rs`
- It expects **PDF-to-text output** (not raw PDF bytes)
- CLI wiring is planned (we’ll add `rewind ingest chase-debit --txt <file>`)

Developer preview (manual extraction):

```bash
# macOS (if poppler is installed)
# brew install poppler
pdftotext -layout chase_statement.pdf - > chase_statement.txt

# the parser expects text with a TRANSACTION DETAIL section
# (CLI command to parse this text is not shipped yet)
```

---

## 6) Scheduling engines: where STS/MTS/LTS are today

- **STS** (short-term scheduler) exists and is used for ordering tasks in visualization mode.
- **MTS** (swap-in/swap-out) exists in `rewind-core` + real-data regression tests.
- **LTS** (long-term planner) is planned and not yet wired.

For now:
- Use `--mode nudge` for a calm, non-overwhelming reminder experience.
- Use `--mode visualize-sts` when you want to inspect STS scheduling behavior.

---

## 7) OpenAI OAuth (velocity) + Chat

### OpenAI OAuth helper

```bash
rewind auth openai-oauth
```

Notes:
- If your `llm.provider = "codex-cli"`, OAuth login is enough (no API key).
- If your `llm.provider = "openai"`, you still need an API key in `~/.rewind/auth.json` for the OpenAI HTTP API.

### Start chat

```bash
rewind chat
```

In chat:
- `?` toggles help
- `/help` shows commands
- `/quit` exits

---

## Troubleshooting

### Google Calendar build errors
Make sure you installed with:

```bash
cargo install --path rewind-cli --locked --features gcal --force
```

### Codex CLI provider doesn’t respond
- Confirm `codex exec "hello"` works in your shell.
- Set optional args in `~/.rewind/config.toml`:

```toml
[llm]
provider = "codex-cli"
codex_command = "codex"
codex_args = []
```
