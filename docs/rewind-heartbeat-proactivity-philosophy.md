# Rewind: Heartbeat-style proactivity (trust-first)

Rewind should evolve from reactive to proactive via a heartbeat-style loop: propose a small set of daily tasks that move the user toward explicit goals using implicit signals, while keeping trust and clarity high.

## Core philosophies / constraints

1) Trust is earned incrementally
- Start with low-risk, mundane, reviewable tasks.
- Default to drafts for review (draft email/scripts/notes) rather than irreversible external actions (sending/posting).

2) Transparency beats speed
- Users lose trust when agents act invisibly/too quickly.
- Always track work (kanban/log/checklist) and report what changed and why.

3) Accessibility matters
- Proactive assistance must be reliably reachable and not depend on the user remembering to ask.

4) Humans resist what helps them
- Expect inconsistent behavior (alarms set → snoozed → frustration).
- The system should stay resilient and supportive, optimizing for long-term wellbeing.

## Product direction
- Implement a “heartbeat” workflow (in the spirit of ZeroClaw): generate ~4–5 tasks/day, execute within guardrails, and keep the user in the loop.
