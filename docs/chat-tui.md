# Rewind Chat TUI (Streaming) — Design Notes

## Goals
- `rewind chat` is a **wellwisher**: calm, respectful, capable-user-first.
- **Streaming tokens** is non-negotiable UX.
- Model/provider agnostic like ZeroClaw:
  - OpenAI (OAuth-first for velocity)
  - Anthropic
  - OpenRouter (OpenAI-compatible)
- Local-first. Minimal friction onboarding.

## Core Architecture (ZeroClaw-inspired)
### Split responsibilities
1) **UI thread (sync)**
- Owns terminal state
- Reads keys, edits input buffer
- Renders frames at steady cadence
- Never blocks on network

2) **Async worker (Tokio tasks)**
- Performs network calls
- Streams tokens
- Sends incremental deltas back to UI

### Message passing
Use channels (mpsc):
- UI → worker: `ChatRequest { turns, config, request_id }`
- worker → UI: `ChatEvent`:
  - `Started { request_id }`
  - `Delta { request_id, text }`
  - `Completed { request_id }`
  - `Error { request_id, message }`

Cancellation:
- When a new request is sent, UI issues `Cancel { request_id }`.
- Worker keeps `JoinHandle` for in-flight job and calls `abort()`.

## Provider layer (model agnostic)
Introduce a trait:

```rust
#[async_trait]
pub trait ChatProvider {
  async fn stream(&self, req: ChatRequest, tx: Sender<ChatEvent>) -> Result<()>;
}
```

Providers:
- `OpenAIProvider { base_url, api_key_or_oauth }`
- `AnthropicProvider { token }`
- `OpenRouterProvider { api_key, base_url="https://openrouter.ai/api/v1" }` (OpenAI-compatible)

## Streaming implementation
### OpenAI-compatible (OpenAI/OpenRouter)
Use `POST /v1/chat/completions` with:
- `stream: true`
- parse SSE (`data: {json}` lines)
- emit `Delta` from `choices[0].delta.content`

### Anthropic
Use `POST /v1/messages` with `stream: true` (SSE)
- parse event types and extract text deltas

## Config (ZeroClaw-style)
Move toward `~/.rewind/config.toml`:

```toml
[llm]
provider = "openai"           # openai|anthropic|openrouter
model = "gpt-4o-mini"
base_url = "https://api.openai.com"

[secrets]
# for v1: stored in ~/.rewind/auth.json
# later: encrypted vault
```

Chat reads config first; falls back to env vars; then auth.json.

## OAuth-first for velocity (OpenAI)
Phase 1 (velocity): shell out to existing CLI (Codex/openai tool) to acquire token.
- `rewind auth openai-oauth` should:
  - detect `codex` (or chosen OpenAI CLI)
  - run login flow
  - store resulting token in `~/.rewind/auth.json`

Phase 2 (later): native OAuth device-flow / localhost redirect.

## Personalization + Vault (future)
- Vault is a password-protected interface for sensitive state:
  - financial details
  - goals
  - preferences
  - reminders

Design:
- encrypted at rest
- unlock during session (`rewind vault unlock`)
- keys derived with Argon2id
- store encrypted blob under `~/.rewind/vault/`.

## UX requirements
- Startup splash: "Rewind" + provider/model + workspace (Codex-like card)
- `/help`, `/status`, `/model`, `/provider`, `/calendar`, `/goals`, `/statements`, `/vault`
- `?` toggles shortcut overlay

## Non-goals (v1)
- Full agent tool system in chat
- Long memory recall

## TODO checklist
- [ ] Add `config.toml` schema + reader
- [ ] Provider trait + OpenAI-compatible streaming implementation
- [ ] Anthropic streaming implementation
- [ ] TUI: background task + incremental render buffer
- [ ] Cancel in-flight request on new user message
- [ ] Improve onboarding docs (quickstart)
- [ ] Vault encryption + unlock flow (later)
