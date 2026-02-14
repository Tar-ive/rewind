# Dev A Tasks: Backend & Agents (Rewind Spec v2)

This document outlines the tasks for Developer A, focusing on the backend infrastructure, agent development, and core logic.

## Phase 1: Foundation (Hours 0–6)

### 1.1 Infrastructure Setup (Hours 0-1)
- [ ] Initialize repository.
- [ ] Set up Python virtual environment (`venv`).
- [ ] Install dependencies (`pip install uagents`).
- [ ] Create Agentverse account and generate API keys.
- [ ] Set up Supabase project (Database & Auth).
- [ ] Set up Redis instance (Upstash or local).
- [ ] Configure Google Calendar + Gmail OAuth credentials.

### 1.2 Context Sentinel Agent (Hours 1-3)
- [ ] Implement `Context Sentinel` agent using `uAgents`.
- [ ] Integrate Google Calendar API to poll for changes.
- [ ] Implement `ContextChangeEvent` emission logic.
- [ ] Register agent on Agentverse with `mailbox=True`.
- [ ] Implement Chat Protocol for ASI:One discovery.
- [ ] **Test**: Verify ASI:One discoverability.

### 1.3 Disruption Detector & Scheduler Kernel (Hours 3-6)
- [ ] Implement `Disruption Detector` agent.
    - [ ] Receive `ContextChangeEvent`.
    - [ ] Classify severity using rules + LLM reasoning.
    - [ ] Emit `DisruptionEvent`.
- [ ] Register `Disruption Detector` on Agentverse.
- [ ] Implement `Scheduler Kernel` agent foundation.
    - [ ] Receive `DisruptionEvent`.
    - [ ] Implement placeholder scheduling (simple swap to buffer).

---
**[CHECKPOINT 1 - Phase 1 Complete]**
- **Test Integration**: Verify the flow: Calendar change → Sentinel → Detector → Kernel.
- **Sync**: Merge all backend agent code to `main`.
- **Verify**: Confirm 3 agents are live and discoverable on Agentverse.
---

## Phase 2: Core Intelligence (Hours 6–18)

### 2.1 Scheduling Engine Core (Hours 6-10)
- [ ] Implement **Task Buffer**: Redis hash table with composite keys.
- [ ] Implement **LTS (Long-Term Scheduler)**: Daily planning pull logic.
- [ ] Implement **MTS (Medium-Term Scheduler)**: Swap-in/swap-out logic triggered by `DisruptionEvent`.
- [ ] Implement priority queue data structures using `heapq`.

### 2.2 STS & Energy Monitor (Hours 10-14)
- [ ] Implement **STS (Short-Term Scheduler)**: MLFQ priority queues (P0–P3).
- [ ] Implement `Energy Monitor` agent.
    - [ ] Time-of-day heuristics + task velocity tracking.
    - [ ] Emit `EnergyLevel`.
- [ ] Register `Energy Monitor` on Agentverse.
- [ ] Wire `energy_level` into STS scheduling constraints.

### 2.3 Profiler Agent & Pipeline Integration (Hours 14-18)
- [ ] Implement `Profiler Agent`.
    - [ ] Track task completions.
    - [ ] Compute `peak_hours`, `estimation_bias`, `automation_comfort`.
- [ ] Register `Profiler Agent` on Agentverse.
- [ ] **Full Pipeline Integration**:
    - [ ] Sentinel → Detector → Kernel (queries Profiler + Energy Monitor) → GhostWorker → Kernel update.

---
**[CHECKPOINT 2 - Phase 2 Complete]**
- **Test Integration**: Verify full pipeline from disruption to rescheduling with real data.
- **Sync**: Merge backend intelligence updates to `main`.
- **Verify**: All 6 agents registered on Agentverse. Profiler providing real data to Kernel.
---

## Phase 3: Polish & Prize Lock (Hours 18–30)

### 3.1 Payment Protocol & Documentation (Hours 18-22)
- [ ] Implement Fetch.ai Payment Protocol on `GhostWorker`.
    - [ ] Implement buyer/seller flow.
    - [ ] Test with demo wallet.
- [ ] Create detailed `README.md` files for all 6 agents (keyword-rich for ASI:One discoverability).
- [ ] **Test**: Verify all agents respond correctly via ASI:One Chat.

### 3.2 Hardening & Edge Cases (Hours 22-26)
- [ ] Handle rapid successive disruptions.
- [ ] Handle concurrent swaps.
- [ ] Handle energy model boundaries.
- [ ] Handle sparse data scenarios for Profiler.
- [ ] (Stretch) Implement Gmail API integration for `Context Sentinel` (new email detection).

### 3.3 Rehearsal & Support (Hours 26-30)
- [ ] Support automated demo flow scripting (set up scenario data).
- [ ] Fix backend bugs found during rehearsal.
- [ ] Assist with recording backup demo video (agent logs/terminal).

---
**[CHECKPOINT 3 - Phase 3 Complete]**
- **Verification**: Payment Protocol works (micro-transactions confirmed). ASI:One discovery works.
- **Sync**: Code freeze on major features. Only bug fixes allowed.
---

## Phase 4: Ship (Hours 30–36)

- [ ] (Hours 30-32) Final backend bug fixes. Ensure high availability of agents.
- [ ] (Hours 32-34) Generate architecture diagrams and agent address tables for documentation.
- [ ] (Hours 34-36) Final demo support. Submit to prize tracks.
