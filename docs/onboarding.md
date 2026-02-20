# Onboarding UX (v0) — first-time user

## Design goal
A new user should go from “I’m curious” → “I trust it” → “I got my first helpful reminder” in **under 2 minutes**.

## First run story
### Step 0: Install
- Single binary (`rewind`)
- No Python, no gcalcli

### Step 1: `rewind chat`
- Shows a friendly splash + a single prompt.
- If not configured, it should *offer exactly one next step*.

**Example:**
- “Want to connect your calendar so I can place 3 small reminders per day? (y/n)”

### Step 2: Minimal configuration (Pareto)
Ask only what’s needed to be useful:
1) Timezone (or auto-detect + confirm)
2) One goal (short/medium/long)
3) Statement (optional initially)
4) Calendar connect (optional but high value)

## What we do with statements (avoid calendar dread)
Statements are used to:
- detect recurring bills and due-date patterns
- estimate “next action that prevents damage” (minimum payment, upcoming bill)
- provide gentle nudges (pay/check/review)

Statements are **not** converted into many calendar tasks by default.

## Trust & safety cues
- Clear local paths: “Your data stays in `~/.rewind/` by default.”
- Minimal scopes: calendar events only.
- Explain exactly what will be written to calendar (3 nudges).
- A `/status` command that lists:
  - what is stored
  - where it is stored
  - what external calls are enabled

## Chat UX principles
- Respectful tone: user is capable, chooses Rewind as a companion.
- Streaming tokens: “feels alive” and reduces perceived latency.
- Cancelable: sending a new message stops the current response.
- Commands are discoverable:
  - `/help` shows top commands
  - `?` shows shortcuts

## Planned commands
- `/provider` / `/model`
- `/goals add` (L/M/S)
- `/statements add` (path)
- `/calendar connect` / `/calendar push`
- `/vault setup` / `/vault unlock`
- `/reminders add` (WhatsApp/iMessage/cron)
