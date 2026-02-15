# Profiler Agent Context & VC Profiling Research

## 1. Repository Context (Profiler Agent)

### 1.1 Vision & Responsibilities
- The Profiler Agent is a first-class Fetch.ai uAgent that learns implicit behavioral patterns—peak hours, estimation bias, distraction triggers, energy curves—and feeds them into scheduling, energy modeling, disruption detection, and delegation (`Rewind_Spec_v2.txt:24-46`, `Rewind_Spec_v2.txt:241-266`).
- It participates in the primary Sentinel → Disruption Detector → Scheduler Kernel → GhostWorker loop by answering questions such as “Is this user affected by meeting overruns?” or “What are their peak hours?” (`Rewind_Spec_v2.txt:96-104`).
- Behavioral profiling is positioned as the differentiator that turns the system from rule-based into adaptive intelligence, with ASI:One Chat exposed so users can query their own patterns (`Rewind_Spec_v2.txt:241-272`).

### 1.2 Data Sources & Signal Pipeline
- `backend/src/data_pipeline/parsers.py` ingests LinkedIn JSON, Twitter/X CSV, GitHub markdown, and certification data, extracting explicit profile facts plus implicit stats (posting cadence, engagement velocity, working style) that seed the Profiler (`backend/src/data_pipeline/parsers.py:1-220`).
- `backend/src/data_pipeline/signals.py` promotes those into `ExplicitSignal` and `ImplicitSignal` objects (peak_hours, engagement, interests, working style) ready for embedding or storage, giving the Profiler structured inputs for inference (`backend/src/data_pipeline/signals.py:1-220`).

### 1.3 Message Contracts & Schema
- `backend/src/models/messages.py` defines `UserProfile` (peak_hours array, avg_task_durations, energy_curve, adherence, distraction patterns, estimation_bias, automation_comfort) plus `ProfileQuery` for requesting specific profile slices (`backend/src/models/messages.py:19-42`).
- Tests cover serialization round-trips for `UserProfile` and `ProfileQuery` to ensure the Profiler payload remains compatible with other agents (`backend/tests/test_messages.py:174-214`).

### 1.4 Consumers of Profiler Intelligence
- **Scheduler Kernel** keeps default `peak_hours`/`estimation_bias` until the Profiler overwrites them, then uses those signals inside LTS/MTS/STS decisions and delegation thresholds (`backend/src/agents/scheduler_kernel.py:41-209`, `backend/src/engine/lts.py:1-145`, `backend/src/engine/mts.py:1-140`).
- **Energy Monitor** swaps its circadian curve for the learned energy curve whenever a fresh `UserProfile` arrives, allowing time-of-day baselines plus task-velocity heuristics to be personalized (`backend/src/agents/energy_monitor.py:78-314`).
- **Disruption Detector** and the agent factory cache peak_hours, estimation_bias, and automation comfort to refine severity classification and cascading actions (`backend/src/agents/disruption_detector.py:1-108`, `backend/src/agents/factory.py:190-268`, `backend/src/engine/disruption_classifier.py:1-120`).
- **GhostWorker delegation logic** uses `automation_comfort` thresholds so only task types above a confidence bar auto-execute, otherwise remain draft-only (`Rewind_Spec_v2.txt:308-314`).

### 1.5 Planning & Implementation Status
- Dev plan Phase 2.3 explicitly schedules work to implement the Profiler Agent, track completions, compute peak_hours + estimation_bias + automation_comfort, register on Agentverse, and wire it into the full sentinel → detector → kernel → ghostworker pipeline (`dev_a_tasks.md:41-70`).
- Later hardening work calls out sparse-data handling for the Profiler, signaling this as a known risk area once the agent is live (`dev_a_tasks.md:72-87`).

## 2. VC Founder-Profiling Frameworks (Reference Research)

### 2.1 Sequoia Capital “Founder DNA” Scorecard
- Sequoia partners lean on a qualitative scorecard focused on missionary vs. mercenary motivation, clarity of thought, ability to recruit talent, and frugal execution. They explicitly test for *drive, daring, and determination* in early meetings and reference calls.
- Inputs: live pitch interrogation (measure precision under pressure), back-channel references on hiring magnetism, shipping history, and evidence of “default to action.” Some partners use a 1–5 scoring rubric for Story, Team Magnetism, Learning Velocity, and Market Insight.

### 2.2 Y Combinator Founder Evaluation Heuristics
- YC interview rubric centers on being “relentlessly resourceful,” default technical/build ability, intensity of founder-market fit, and rate of product iteration. They probe for concrete evidence of shipping in days, not weeks, and whether the team would keep going even if the idea changed.
- Inputs: 10-minute interview transcripts, application essays, GitHub/production links, reference pings to past collaborators. YC partners effectively maintain an agent-like list of “unstoppable” teams they can re-approach for new ideas.

### 2.3 Andreessen Horowitz (a16z) Founder Diligence Loop
- a16z emphasizes *narrative dominance* (ability to articulate a market-secret), technical depth or execution proof, and go-to-market magnetism. Their diligence loop triangulates: references (former managers, co-founders), product signals (what shipped, how fast), and audience pull (followership, community-building).
- Inputs: structured reference scorecards, data-room analytics (usage, retention), media footprint, and social graph reach. Partners often maintain “talent grid” spreadsheets ranking known builders across vectors like technical spike, storytelling, and recruiting power.

### 2.4 First Round Capital “People-Product Fit” Rubric
- First Round popularized the idea that founders must demonstrate a personal superpower, high rate-of-learning, clarity about users, and ability to run deliberate experiments. They track whether each conversation shows new progress—a proxy for learning compounding.
- Inputs: founder update emails, experiment logs, recorded user interviews, references from early hires. Their talent team uses a weighted scorecard (0–4) on Superpower, Execution Pace, Narrative Clarity, and Team-Building.

### 2.5 Data-Driven Funds (SignalFire, Social Capital, etc.)
- Funds with internal “talent intelligence” platforms (e.g., SignalFire’s Beacon) ingest multi-source data—GitHub activity, LinkedIn mobility, StackOverflow, Twitter followers—to maintain heat maps of emerging builders and job changes. Individuals are profiled via scoring models that mix reach, influence, technical credibility, and hiring velocity.
- Inputs: automated scraping, proprietary data partnerships, ML-based ranking models. Human partners then run qualitative follow-ups but start from a continuously refreshed list of high-signal operators.

## 3. Lessons & Opportunities for the Rewind Profiler

1. **Adopt multi-vector scoring.** VC scorecards show the value of weighting traits such as narrative clarity, builder velocity, magnetism, and founder-market fit. Extend `UserProfile` to store normalized scores across cognitive/behavioral vectors instead of raw stats only.
2. **Capture rate-of-learning.** Track how quickly a user adjusts after feedback—e.g., time between disruption and recovery or improvement in estimation_bias. This mirrors VC focus on “learning velocity.”
3. **Reference-style signal gathering.** Parse collaboration metadata (shared calendars, Slack reactions, GitHub reviewers) to infer whether the user attracts collaborators, similar to how investors run back-channel reference nets.
4. **Narrative & audience measures.** Use LinkedIn/Twitter implicit signals to compute communication clarity, community engagement, and follower responsiveness—analogous to how a16z gauges narrative dominance.
5. **Automate heat maps.** Maintain rolling leaderboards (per role, domain, or objective) akin to VC talent grids. The Profiler Agent can surface “probability of shipping on time” or “delegation comfort” percentile ranks drawn from aggregated signals and task history.
6. **Cold-start bootstrapping from population priors.** Funds rely on pattern libraries collected over years; replicate this via Supabase defaults plus population clusters (builder archetypes) to avoid cold-start gaps noted in the roadmap.

Incorporating these elements keeps the Profiler aligned with proven human-evaluation frameworks while leveraging its access to fine-grained behavioral telemetry from Rewind’s ecosystem.
