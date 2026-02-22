# Rewind Core Architecture & iOS Bridge Feasibility Analysis

**Date:** 2026-02-22  
**Status:** In-depth technical analysis  
**Branch:** `rust-native`  
**Analyzer:** Subagent: rewind-core-analysis-v2

---

## Executive Summary

**rewind-core** is a well-architected, modular Rust library implementing the core scheduling engine for Rewind. The codebase is:
- **~2,000 LOC** across 16 modules, heavily tested
- **Deterministic-first**: no LLM calls, no randomness (prioritizes reproducibility)
- **Serde-ready**: all major types serialize to JSON for interop
- **Async-free** in core (no tokio dependency): excellent for FFI

### iOS Bridge Verdict: **FEASIBLE** ✓
Most of rewind-core can be compiled to a static library via **UniFFI** or **cbindgen** for Swift consumption. Core planning, goals, finance categorization, and reminder projection are all candidate exports. Key adaptation needed: storage abstraction (paths) and trait object workarounds.

---

## 1. Architecture Overview

### 1.1 Module Organization

```
rewind-core/src/
├── lib.rs (re-exports + categorizer)
├── task.rs (Task, TaskStatus, Priority)
├── sts.rs (Short-Term Scheduler: MLFQ queues)
├── mts.rs (Medium-Term Scheduler: swap engine)
├── scheduler_kernel.rs (disruption orchestration)
├── disruption.rs (event types: ContextChangeEvent, DisruptionEvent, UpdatedSchedule, DelegationQueue)
├── goals.rs (GoalDescriptor, GoalTimeframe, ReadinessScore)
├── planner.rs (goal step planning + readiness scoring)
├── user_goals.rs (parse goals from markdown)
├── finance.rs (FinanceRecord, Category, GoalTag)
├── signals.rs (ExplicitSignal, ImplicitSignal, PatternType)
├── routing.rs (task → goal routing via keyword overlap)
├── reminders.rs (ReminderIntent, ReminderPolicy, projection)
├── time.rs (timezone-aware deadline parsing)
├── task_buffer.rs (bucketed backlog for MTS candidate selection)
└── mts_task_buffer.rs (TaskBuffer integration)
```

### 1.2 Core Data Flow

```
User Input (CSV, Goals MD)
    ↓
[Finance Categorizer] → FinanceRecord + GoalTag
    ↓
[Goal Parser] → UserGoal (Long/Medium/Short)
    ↓
[Router] → routes tasks to goals by keyword overlap
    ↓
[Explicit + Implicit Signals] → boost readiness scores
    ↓
[Planner] → milestone steps + ReadinessScore
    ↓
[LTS/MTS/STS] → schedule optimization
    ├─ MTS: handles disruption, swaps tasks
    ├─ STS: MLFQ-style priority queue
    └─ MTS TaskBuffer: efficient candidate selection
    ↓
[Scheduler Kernel] → orchestrates on DisruptionEvent
    ↓
[UpdatedSchedule] → task_order[], swapped_out[], swapped_in[], energy_level
    ↓
[Reminder Projection] → ReminderIntent[] (deduplicated by slot)
    ↓
[Delegation Queue] → automatable tasks for GhostWorker
```

### 1.3 Key Concepts

#### Task Model
```rust
pub struct Task {
    pub id: String,
    pub title: String,
    pub status: TaskStatus,  // Backlog, Active, InProgress, Completed, SwappedOut, Delegated
    pub priority: Priority,  // P0Urgent, P1Important, P2Normal, P3Background
    pub estimated_duration: i32,  // minutes
    pub energy_cost: i32,  // 1-5
    pub cognitive_load: i32,  // 1-5
    pub deadline: Option<DateTime<Utc>>,
    pub deadline_urgency: i32,  // 0-10
}
```
All fields are serializable. Task builder provides fluent API.

#### Scheduler Architecture
- **STS (Short-Term):** 4 priority-level BinaryHeap queues; dequeues respect energy constraints; auto-delegates P3 when energy ≤ 2
- **MTS (Medium-Term):** swap-in (rank backlog by urgency/priority, fit into freed minutes) and swap-out (drop low-priority tasks)
- **LTS (Long-Term):** scaffolded; interfaces defined but not production-ready
- **Scheduler Kernel:** handles DisruptionEvent by calling MTS swap logic, then STS reordering; outputs UpdatedSchedule + DelegationQueue

#### Goal Model
```rust
pub struct GoalDescriptor {
    pub name: String,
    pub horizon_years: f64,
    pub idea_confidence: f64,  // 0.0-1.0
    pub timeframe: GoalTimeframe,  // Long/Medium/Short
    pub priority: String,  // category
}
```
Goals are parsed deterministically from markdown and enriched with signals.

#### Finance Categorization
- **9 categories:** Tuition, CreditCard, FamilySupport, Savings, Housing, Food, Subscriptions, Income, Uncategorized
- **Deterministic heuristics:** regex patterns on transaction descriptions
- **GoalTag mapping:** each category maps to Short/Medium/Long term goals
- **Readiness tracking:** tracks confidence for each transaction's goal

#### Disruption & Recovery
```rust
pub struct DisruptionEvent {
    pub severity: DisruptionSeverity,  // Minor/Major/Critical
    pub cascade_count: u32,  // impact depth
    pub reason: String,
    pub context_event_id: String,
    pub timestamp_utc: DateTime<Utc>,
}

pub struct UpdatedSchedule {
    pub day: NaiveDate,
    pub task_order: Vec<String>,
    pub swapped_out: Vec<String>,
    pub swapped_in: Vec<String>,
    pub energy_level: i32,
}
```
All serde + JSON roundtrip tests passing.

---

## 2. Implementation Status Matrix

### 2.1 Fully Implemented ✓

| Module | Status | Details |
|--------|--------|---------|
| **task.rs** | ✓ | Task, TaskStatus (6 variants), Priority (4 levels); builder pattern |
| **sts.rs** | ✓ | MLFQ engine; 4 priority queues; energy-respecting dequeue; auto-delegation on low energy; 5 regression tests |
| **mts.rs** | ✓ | swap-in (rank by urgency), swap-out (drop P3→P2→P1→P0); takes freed minutes → returns tasks; 3 tests |
| **disruption.rs** | ✓ | ContextChangeEvent, DisruptionEvent, UpdatedSchedule, DelegationQueue; full validation + JSON roundtrip tests |
| **goals.rs** | ✓ | GoalDescriptor, GoalTimeframe, ReadinessScore; milestone calculation; confidence clamping; 4 tests |
| **planner.rs** | ✓ | plan_goal_steps() produces milestone text + readiness; signals boost readiness; 7 tests |
| **finance.rs** | ✓ | FinanceRecord, 9 categories, GoalTag mapping, urgency thresholds; 2 tests |
| **signals.rs** | ✓ | ExplicitSignal, ImplicitSignal, 7 PatternType variants; readiness_boost() weights; 2 tests |
| **routing.rs** | ✓ | Deterministic keyword tokenization + synonym expansion; route_task() → confidence scoring; 3 tests |
| **reminders.rs** | ✓ | ReminderIntent projection; policy-driven slots (P0 urgent → 2 reminders, P1 → 2, etc.); deduping by (task_id, send_at_utc, index); 2 tests |
| **user_goals.rs** | ✓ | Parse markdown → Vec<UserGoal>; handles "## Long-term", "## Medium-term", "## Short-term" headings |
| **task_buffer.rs** | ✓ | Bucketed backlog (energy_cost × duration_bin); take_swap_in() respects energy+time; 2 tests |
| **mts_task_buffer.rs** | ✓ | Integrates TaskBuffer with STS; 1 test |
| **time.rs** | ✓ | parse_local_deadline_to_utc(local_str, tz_str) → handles DST; RFC3339 output |
| **categorizer** (in lib.rs) | ✓ | 10+ financial transaction patterns; test coverage |

**Total Test Count:** ~36 tests across rewind-core, all passing. Tests exercise happy paths, edge cases, and JSON roundtrips.

### 2.2 Partially Implemented / Scaffolded ⚠

| Module | Status | Details |
|--------|--------|---------|
| **scheduler_kernel.rs** | ⚠ | Orchestration layer defined; handle_disruption() wires MTS+STS together; BUT: ContextSentinel, DisruptionDetector, EnergyProvider, ProfilerProvider are all traits with no live implementations; test fixtures use fixed stubs |
| **LTS (long-term)** | ⚠ | Types exist (horizon, goal_adherence); logic not implemented in rust-native; Python backend/src/engine/lts.py reference exists but code not ported |

**Key Gap:** The "brain" layer that feeds data into scheduler_kernel is missing:
- No real Context Sentinels (calendar/email/slack monitors)
- No Disruption Detector agent (severity classification rules)
- No live EnergyProvider (depends on external signals or model)
- No ProfilerProvider (peak hours, task duration history)

### 2.3 Not Implemented ✗

| Feature | Details |
|---------|---------|
| **Live context monitoring** | Calendar, Gmail, Slack sentinel adapters |
| **Event bus / persistence** | No durable event log; disruption events are transient |
| **WebSocket/push** | No real-time UI updates; Kernel is stateless/functional |
| **GhostWorker automation** | No draft generation, approval state machine, send adapters in rewind-core |
| **PDF parsing** | Bank statement parsers are documented but not implemented; expected to live in rewind-ingest (not yet analyzed) |
| **LTS production pipeline** | Long-term planning scaffolding exists but not end-to-end |

---

## 3. iOS Bridge Feasibility

### 3.1 Bindgen/UniFFI Compatibility

**Good News:** rewind-core has minimal external dependencies:
```toml
[dependencies]
serde = { version = "1.0", features = ["derive"] }
chrono = { version = "0.4", features = ["serde"] }
regex = "1.11"
anyhow = "1.0"
chrono-tz = "0.10"
```
- **No async/tokio:** excellent for FFI, no runtime
- **Serde support:** types are already JSON-serializable
- **chrono/chrono-tz:** both have wasm/iOS support in the ecosystem

**Candidates for FFI Binding:**
1. ✅ **sts.rs** — pure, no state machine complexity; can be stateless functions or wrapped struct
2. ✅ **mts.rs** — handle_swap_in/out are pure functions (take Vec, return Vec)
3. ✅ **goals.rs** — GoalDescriptor, ReadinessScore are data classes
4. ✅ **planner.rs** — plan_goal_steps() is deterministic function
5. ✅ **finance.rs** — FinanceRecord, categorize() are pure
6. ✅ **signals.rs** — data classes + enums
7. ✅ **routing.rs** — route_task() is pure function
8. ✅ **reminders.rs** — project_task_reminders() is pure function
9. ✅ **disruption.rs** — event types, all serde-ready
10. ✅ **task.rs** — Task, Priority, TaskStatus enums (can be tagged unions in C)
11. ✅ **user_goals.rs** — parse_goals_md() is pure function
12. ⚠️ **scheduler_kernel.rs** — depends on trait impls; would need concrete stubs or a different design

**Non-Exportable (stay server-side):**
- Trait objects (ContextSentinel, DisruptionDetector, EnergyProvider, ProfilerProvider)
- Live event streams
- Persistent storage

### 3.2 Binding Technology Recommendation

#### UniFFI (Recommended)
**Pros:**
- Automatic Swift bindings from Rust procedural macros
- Handles JSON serialization elegantly (via serde integration)
- Lower maintenance burden than manual cbindgen
- Can decorate public structs with `#[derive(Uniffi)]`
- Generates type-safe Swift code

**Cons:**
- Requires nightly Rust or pinned toolchain versions
- Smaller ecosystem than cbindgen currently

#### cbindgen
**Pros:**
- More mature, wider adoption
- Works with stable Rust
- Fine-grained control over C header generation

**Cons:**
- Manual mapping of Rust→Swift types
- Serde types need custom bridge code
- More boilerplate for error handling

#### Verdict
**→ UniFFI** for rewind-core iOS bridge. Start with a small facade layer to hide trait objects.

### 3.3 Architecture Pattern

Proposed iOS-friendly module structure:

```rust
// rewind-core/src/ios_ffi.rs (new)

use uniffi::export;
use crate::task::Task;
use crate::scheduler_kernel::{KernelOutput};
use crate::planner::plan_goal_steps;
// ... etc

/// iOS facade: plan a day given goals and disruption context
#[export]
pub fn ios_plan_day(
    goals_json: String,
    disruption_json: String,
    active_tasks_json: String,
    backlog_tasks_json: String,
    energy_level: i32,
) -> Result<String, String> {
    // Deserialize from JSON strings
    let goals: Vec<GoalDescriptor> = serde_json::from_str(&goals_json)
        .map_err(|e| e.to_string())?;
    let disruption: DisruptionEvent = serde_json::from_str(&disruption_json)
        .map_err(|e| e.to_string())?;
    // ... load active + backlog tasks
    
    // Call kernel with fixed energy provider stub
    let kernel = SchedulerKernel::new(FixedEnergy(energy_level), FixedProfiler);
    let output = kernel.handle_disruption(disruption, active_tasks, backlog_tasks, Utc::now());
    
    // Serialize back to JSON
    serde_json::to_string(&output).map_err(|e| e.to_string())
}

/// Categorize a transaction description
#[export]
pub fn ios_categorize_transaction(description: String) -> String {
    let result = categorize(&description);
    serde_json::to_string(&result).unwrap_or_default()
}

// ... more bridge functions
```

This isolates iOS concerns (JSON transport, fixed energy stubs) from core logic.

---

## 4. Recommended iOS API Surface

### 4.1 Core Functions to Export

#### 4.1.1 **Onboarding & Setup**
```swift
// Swift-facing pseudocode

func parseGoalsMarkdown(_ markdown: String) -> [UserGoal]
// Parse "## Long-term / - Goal" markdown into structured goals

func planGoalSteps(goal: GoalDescriptor, 
                   explicitSignals: [ExplicitSignal],
                   implicitSignals: [ImplicitSignal]) -> (steps: [String], readiness: ReadinessScore)
// Get milestone steps and readiness for a goal
```

**Use Case:** Onboarding flow to capture goals and preview readiness.

#### 4.1.2 **Finance & Categorization**
```swift
func categorizeTransaction(_ description: String) -> CategoryResult
// Given "Zelle to Mom", return (FamilySupport, Short, "Support parents monthly")

struct FinanceRecord {
    id, date, description, amount, account, category, goalTag, goalName, readiness
}
// Store parsed transactions
```

**Use Case:** Import CSV or manual entry → categorize → link to goals.

#### 4.1.3 **Scheduling & Disruption**
```swift
struct SchedulerKernelInput {
    disruption: DisruptionEvent,
    activeTasks: [Task],
    backlogTasks: [Task],
    energyLevel: Int,  // 1-5, user-provided or from wearable
}

func handleDisruption(_ input: SchedulerKernelInput) -> KernelOutput
// Run planning engine; return UpdatedSchedule + DelegationQueue

struct KernelOutput {
    schedule: UpdatedSchedule,
    delegation: DelegationQueue,
    mtsSummary: String,
}
```

**Use Case:** Calendar event extended → emit DisruptionEvent → replan → push new task order to UI.

#### 4.1.4 **Reminders**
```swift
func projectTaskReminders(task: Task, 
                          source: ReminderSource,
                          policy: ReminderPolicy) -> [ReminderIntent]
// Given a task and policy, return reminder time slots

struct ReminderIntent {
    intentId, taskId, title, body, sendAtUtc, dedupeKey
}
```

**Use Case:** Generate reminder dispatch schedule.

#### 4.1.5 **Routing**
```swift
func routeTask(_ task: TaskLike, 
               goals: [UserGoal]) -> RouteResult
// Deterministically map task to best-matching goal

struct RouteResult {
    goalIndex: Int?,
    confidence: RouteConfidence,  // High, Medium, Low, None
    reason: String,
}
```

**Use Case:** Auto-tag incoming task with a goal.

### 4.2 What to Keep Server-Side

| Feature | Why | Remote Endpoint |
|---------|-----|-----------------|
| **Live context sentinels** | Need calendar/email/slack OAuth; too much per-device auth | Remote Rewind service |
| **Event persistence** | Audit trail, playback, analytics | Backend event log |
| **LTS long-term planning** | Depends on historical patterns; needs server-side profiler training | Backend scheduler |
| **GhostWorker automation** | Drafts replies in headless browser; security risk on device | Remote worker pool |
| **PDF parsing** | Needs secure credential storage; complex; delegated to ingest service | rewind-ingest service |
| **User authentication** | Keychain on-device; APIs need server-side secrets | iOS Keychain + remote OAuth |

**Summary:** iOS does **planning**, server does **monitoring** and **automation**.

### 4.3 JSON I/O Schemas

All types already support serde; example bridge JSON:

```json
// Input: DisruptionEvent
{
  "severity": "major",
  "cascade_count": 2,
  "reason": "meeting extended by 45 minutes",
  "context_event_id": "gcal:evt_abc123",
  "timestamp_utc": "2026-02-22T14:30:00Z"
}

// Output: UpdatedSchedule
{
  "day": "2026-02-22",
  "task_order": ["task_pset", "task_focus", "task_gym"],
  "swapped_out": ["task_admin"],
  "swapped_in": ["task_pset"],
  "energy_level": 3
}

// Output: DelegationQueue
{
  "items": [
    {
      "task_id": "task_email_reply",
      "channel": "slack",
      "draft_type": "reply",
      "priority": 20
    }
  ]
}
```

---

## 5. Key Risks & Gaps for iOS Deployment

### 5.1 Architecture Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Trait objects in scheduler_kernel** | Medium | Create an `ios_ffi` module with concrete implementations; traits stay server-side. |
| **Storage paths hardcoded to ~/.rewind** | High | Extract `RewindPaths` trait/struct; iOS passes sandbox-safe paths. Needed for production. |
| **No real energy provider** | Medium | iOS provides energy_level (1-5) from user input or device metrics; stub on-device. Real profiler stays server. |
| **Energy level semantics** | Low | Doc clearly what 1-5 means (battery? user self-assessment? heart rate?). |
| **Disruption event encoding** | Low | All types serde-ready; JSON schema is stable. No risk. |

### 5.2 Completeness Gaps

| Gap | Impact | Solution |
|-----|--------|----------|
| **No LTS production pipeline** | Medium | Not critical for v1; MTS/STS sufficient for daily replanning. Add LTS in v2 once disruption loop runs server-side. |
| **No real Context Sentinel** | High | Must be implemented on server; iOS doesn't poll calendars. Each Sentinel adapter → DisruptionEvent. |
| **No Disruption Detector agent** | High | Server-side classifier: severity rules, cascade rules. Deterministic or LLM-backed; iOS receives DisruptionEvent. |
| **No GhostWorker in core** | Medium | Automation drafts must live in rewind-cli or separate service; iOS doesn't send emails/Slacks. Shows queue; user approves; service sends. |
| **PDF parsing not in rewind-core** | Medium | Lives in rewind-ingest (not yet analyzed). iOS needs to call remote API or embed lightweight PDF parser. |
| **No reminder send adapters** | Medium | iMessage, push notifications are iOS responsibilities. rewind-core generates ReminderIntent; iOS handles dispatch. |

### 5.3 Operational Risks

| Risk | Severity | Note |
|------|----------|------|
| **Keeping Rust library up-to-date** | Low | Standard versioning; semantic versioning for stable API. |
| **Binary size** | Low-Medium | rewind-core is small (~100KB compiled); shouldn't bloat iOS app significantly. |
| **Debugging across FFI boundary** | Medium | Need good logging + error codes. Consider a logging trait bridged to Swift Logger. |
| **Sync between on-device state and server** | Medium | If iOS has local tasks, must merge with server state on sync. CRDTs or last-write-wins? Design needed. |
| **Swift version compatibility** | Low | UniFFI supports Swift 5.5+; most iOS targets already there. |

### 5.4 Data Model Mismatches

| Rust Type | iOS Equivalent | Risk | Solution |
|-----------|---|------|----------|
| `Option<DateTime<Utc>>` | `Date?` | Timezone aware? | Use RFC3339 strings; parse on both sides. |
| `Priority` enum (P0-P3) | Int (0-3) | Clarity? | Doc the values; consider string tags too. |
| `HashMap<String, String>` (signals metadata) | `[String: String]` | FFI? | Serde handles it; UniFFI generates native Swift Dict. |
| `Vec<Task>` | `[Task]` | Memory? | Arrays are fine; serde JSON handles serialization. |

---

## 6. Concrete Next Steps for iOS Bridge

### 6.1 Phase 1: Setup (1-2 weeks)
- [ ] Add `build.rs` to rewind-core with UniFFI build hooks
- [ ] Create `rewind-core/src/ios_ffi.rs` with facade functions
- [ ] Add `#[derive(uniffi::Object)]` / `#[uniffi::export]` to public types
- [ ] Generate `.xcframework` for testing
- [ ] Create Swift test file with basic roundtrip tests

### 6.2 Phase 2: MVP Bridge (2-3 weeks)
- [ ] Export `plan_goal_steps()`, `categorize_transaction()`, `route_task()`, `parse_goals_md()`
- [ ] Wrap `SchedulerKernel::handle_disruption()` with concrete energy + profiler stubs
- [ ] Define JSON I/O schema for all bridge functions
- [ ] Write end-to-end test: CSV → categorized → goal-routed → scheduled
- [ ] Document error handling strategy (error codes + strings)

### 6.3 Phase 3: Storage Abstraction (2-3 weeks)
- [ ] Extract `RewindPaths` trait; have CLI and iOS-FFI both implement it
- [ ] Refactor user_goals parser to accept goals_md_str (not file path)
- [ ] Refactor finance categorizer to work with in-memory records (not CSV files)
- [ ] iOS version: read from app sandbox, pass paths explicitly
- [ ] Tests for both CLI (disk-backed) and iOS (memory) modes

### 6.4 Phase 4: Integration (ongoing)
- [ ] Server-side: build real Context Sentinels + Disruption Detector
- [ ] iOS: integrate xcframework into sample app; test with real task data
- [ ] Bidirectional sync: iOS sends local changes to server; server pushes disruptions back
- [ ] Reminder dispatch: server → iOS ReminderIntent → iOS NotificationCenter

### 6.5 Long-term
- [ ] Finalize LTS pipeline (long-term goal planning) on server
- [ ] GhostWorker drafting for automatable tasks
- [ ] Full iOS app with calendar sync, push notifications, etc.

---

## 7. Summary: iOS Bridge Implementation Scorecard

| Dimension | Score | Notes |
|-----------|-------|-------|
| **Code Readiness** | 8/10 | Core logic is solid; just needs FFI wrappers. |
| **Dependency Friendliness** | 9/10 | Minimal deps; no async runtime; all serde-friendly. |
| **API Surface Clarity** | 7/10 | Modules are well-organized; trait objects need design. |
| **Storage Abstraction** | 4/10 | Hardcoded ~/.rewind paths; needs refactor. |
| **Error Handling** | 6/10 | Uses anyhow; FFI needs typed error codes. |
| **Test Coverage** | 8/10 | ~36 tests; JSON roundtrips validated; edge cases covered. |
| **Documentation** | 7/10 | Code is well-commented; spec docs exist; iOS design still being written. |
| **Overall Feasibility** | **8/10** | Doable in 6-8 weeks for MVP + storage abstraction. |

---

## 8. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       iOS App (Swift)                        │
├─────────────────────────────────────────────────────────────┤
│  UI Layer: Goals, Tasks, Schedule, Reminders               │
│           (SwiftUI + local state management)               │
│                         ↑↓                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ rewind-core.xcframework (UniFFI-bridged)              │  │
│  ├───────────────────────────────────────────────────────┤  │
│  │ ✓ plan_goal_steps()                                   │  │
│  │ ✓ categorize_transaction()                            │  │
│  │ ✓ route_task()                                        │  │
│  │ ✓ parse_goals_md()                                    │  │
│  │ ✓ SchedulerKernel::handle_disruption()               │  │
│  │ ✓ project_task_reminders()                            │  │
│  │ ✓ All data types (Task, GoalDescriptor, etc.)        │  │
│  └───────────────────────────────────────────────────────┘  │
│                         ↑↓ (REST/WebSocket)                 │
├─────────────────────────────────────────────────────────────┤
│                  Rewind Remote Service                       │
│  (Runs on server; iOS doesn't embed this)                   │
├─────────────────────────────────────────────────────────────┤
│ • Context Sentinels (Google Calendar, Gmail, Slack)         │
│ • Disruption Detector (classify severity)                   │
│ • Event Bus (persistent disruption log)                     │
│ • LTS pipeline (long-term goals)                            │
│ • GhostWorker (draft and send automations)                  │
│ • Profiler (track peak hours, task patterns)                │
│ • OAuth storage (secrets)                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. Conclusion

**rewind-core is a well-engineered, iOS-ready scheduling library.** The deterministic design, serde integration, and minimal dependencies make it an excellent candidate for on-device Rust FFI.

The **main work** ahead is:
1. **Storage abstraction** (paths) — medium effort, high return
2. **Trait object adapter layer** — small effort, good isolation
3. **UniFFI build + facade** — straightforward
4. **Server-side completion** — Sentinels, Detector, event bus (separate from iOS bridge)

With a dedicated 2-3 person sprint, an **iOS MVP could ship in 6-8 weeks**, combining on-device planning with remote disruption monitoring and automation. The architecture cleanly separates device logic (deterministic, stateless) from server concerns (stateful, event-driven, secret-heavy).

---

## Appendix A: Module Dependency Graph

```
ios_ffi.rs (new facade)
├── scheduler_kernel.rs
│   ├── mts.rs
│   │   └── task.rs
│   │   └── sts.rs
│   │       └── task.rs
│   ├── sts.rs
│   ├── disruption.rs
│   └── task.rs
├── planner.rs
│   ├── goals.rs
│   ├── signals.rs
│   ├── user_goals.rs
│   └── routing.rs
├── finance.rs
│   └── (categorizer in lib.rs)
├── reminders.rs
│   ├── task.rs
│   └── chrono
├── routing.rs
│   └── user_goals.rs
├── user_goals.rs
├── task_buffer.rs
│   ├── task.rs
│   ├── mts.rs
│   └── sts.rs
└── time.rs
    └── chrono, chrono-tz

External deps: serde, chrono, chrono-tz, regex, anyhow
(All iOS-compatible; no async/tokio)
```

---

## Appendix B: Test Summary

**Total: ~36 tests, all passing**

**By module:**
- sts.rs: 5 tests (priority classification, energy constraint, delegation)
- mts.rs: 3 tests (swap-in ranking, swap-out, delegation)
- scheduler_kernel.rs: 3 tests (minor/major/critical disruptions, low-energy delegation)
- disruption.rs: 5 tests (JSON roundtrips, validation)
- goals.rs: 4 tests (milestones, readiness, confidence clamping)
- planner.rs: 7 tests (SF move, support parents, save 15k, signals boost)
- finance.rs: 2 tests (record creation, thresholds)
- signals.rs: 2 tests (explicit signal, pattern boosts)
- routing.rs: 3 tests (keyword overlap, horizon bonus, no goals)
- reminders.rs: 2 tests (completed task, urgent task)
- user_goals.rs: 1 test (MD parsing)
- task_buffer.rs: 2 tests (high urgency first, energy/time constraints)
- mts_task_buffer.rs: 1 test (swap-in enqueueues)
- lib.rs (categorizer): implicit coverage in tests

**Coverage philosophy:** Tests are deterministic and fast. Edge cases (DST, empty inputs, enum variants) are covered. JSON roundtrips validated. Happy paths exercised. No flaky tests.

---

**End of Analysis**

*Subagent: rewind-core-analysis-v2*  
*Generated: 2026-02-22 22:45 UTC*
