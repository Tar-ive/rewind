# Rewind CLI Quickstart (first-time user)

This guide assumes you have Rust installed.

## Install

```bash
git clone https://github.com/Tar-ive/rewind.git
cd rewind
git checkout rust-native

cargo test -q
cargo install --path rewind-cli --locked
```

## Setup (goals + timezone)

```bash
rewind setup
```

Notes:
- Rewind stores user state in `~/.rewind/`.
- Timezone must be an **IANA timezone** like `America/Chicago`.
- You can override timezone non-interactively with:

```bash
export REWIND_TZ=America/Chicago
rewind setup
```

## Statements

AMEX CSV demo (repo includes `amex.csv`):
```bash
rewind finance sync --csv amex.csv
```

Plan for today (goals + statement tasks + deterministic routing):
```bash
rewind plan-day --csv amex.csv --limit 10
```

See full statement format notes in `docs/statements.md`.

## Auth (optional)

Rewind supports native auth storage at `~/.rewind/auth.json`.

### Claude
OAuth via Claude Code CLI:
```bash
npm i -g @anthropic-ai/claude-code
rewind auth claude-setup-token
```

Or paste token:
```bash
rewind auth paste-anthropic-token
```

### OpenAI
Paste key:
```bash
rewind auth paste-openai-api-key
```

## What Rewind does
- Captures explicit goals (long/medium/short)
- Ingests statements (CSV now; PDF→text parsers scaffolded)
- Extracts implicit signals (spend, merchants, balance trends)
- Routes signals to goals deterministically first
- Uses intent classification only when ambiguous (planned)
