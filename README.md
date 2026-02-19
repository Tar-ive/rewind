# Rewind (Rust-native)

Rewind is a **long-term scheduler** (LTS/MTS/STS) that helps users achieve explicit goals using implicit real-world signals (starting with credit card statements).

- **Explicit goals**: long / medium / short
- **Implicit signals**: statements → normalized transactions → patterns → suggestions
- **Learning**: file-backed personalization (Markdown/JSON) + deterministic extraction, with optional federated learning later.

## Status (rust-native branch)
Working today:
- `rewind setup` → captures goals → writes `~/.rewind/goals.md` + `~/.rewind/profile.json`
- `rewind finance sync --csv amex.csv` → parses AMEX CSV → emits grouped tasks
- `rewind plan-day --csv amex.csv` → combines goals + statement-derived tasks
- `rewind-ingest` scaffold + Capital One US parser scaffold (expects PDF→text)
- deterministic routing scaffold in `rewind-core` (keyword overlap + tests)

## Quickstart

```bash
git clone https://github.com/Tar-ive/rewind.git
cd rewind
git checkout rust-native

cargo test -q
cargo install --path rewind-cli --locked

rewind setup
rewind finance sync --csv amex.csv
rewind plan-day --csv amex.csv --limit 10
```

## Auth (optional)
Rewind supports **native auth** (no OpenClaw required).

### Claude (Anthropic)
Option A (OAuth via Claude Code CLI):
```bash
rewind auth claude-setup-token
```
If `claude` is missing:
```bash
npm i -g @anthropic-ai/claude-code
```

Option B (paste token):
```bash
rewind auth paste-anthropic-token
```

### OpenAI
For now, Rewind supports paste-key auth:
```bash
rewind auth paste-openai-api-key
```

Tokens are stored in `~/.rewind/auth.json`.

## Statements
See `docs/statements.md` for supported formats and schemas.

## Design notes
- Rewind does deterministic routing first; LLM intent classification is used only when needed.
- Personalization is file-backed (OpenClaw-style). No fine-tuning is required.

## License
MIT
