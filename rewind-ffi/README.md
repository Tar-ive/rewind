# rewind-ffi: UniFFI Bridge for rewind-core

A Rust crate that exposes the [rewind-core](../rewind-core) scheduling engine to Swift and iOS via FFI (Foreign Function Interface).

## Overview

`rewind-ffi` provides two complementary APIs for integrating rewind-core into iOS applications:

1. **JSON-in/JSON-out Functions** (default, simple integration)
   - Stateless wrapper functions that accept JSON strings
   - No external type dependencies in Swift
   - Error codes and messages for all operations
   - Suitable for REST/WebSocket transport

2. **UniFFI Type-Safe Bindings** (advanced, future)
   - Native Swift types mapped directly to Rust types
   - Automatic `.xcframework` generation for iOS
   - Requires UniFFI build setup and Swift 5.5+
   - Generated Swift code is type-safe and idiomatic

## Features

### Core Exports

- **Goals & Planning**
  - `parse_goals_json()`: Parse markdown goals into structured data
  - `plan_goal_steps_json()`: Generate milestones and readiness scores

- **Finance**
  - `categorize_transaction_json()`: Categorize financial transactions
  - Deterministic heuristics (no ML models)

- **Task Routing**
  - `route_task_json()`: Match tasks to goals by keyword overlap

- **Scheduling**
  - `handle_disruption_json()`: Re-plan when disruptions occur
  - Energy-respecting task prioritization

- **Reminders**
  - `project_reminders_json()`: Generate reminder schedules by policy

## Usage

### JSON API (Current)

```rust
use rewind_ffi::{categorize_transaction_json, FfiResult};

let result = categorize_transaction_json("ZELLE MOM");
assert!(result.success);
assert_eq!(result.error_code, 0);
// result.data contains JSON: {"category": "FamilySupport", ...}
```

### Example in Swift (Future with UniFFI)

```swift
import RewindFFI

let goals = try RewindFFI.parseGoalsJson(goalsMarkdown: markdownString)
let schedule = try RewindFFI.handleDisruptionJson(
    disruption: disruptionJson,
    activeTasks: tasksJson,
    backlogTasks: backlogJson,
    energyLevel: 3
)
```

## Architecture

```
┌─────────────────────────────────────┐
│     iOS Swift App (SwiftUI)         │
├─────────────────────────────────────┤
│  rewind-ffi.xcframework             │
│  (UniFFI-generated Swift bindings)  │
├─────────────────────────────────────┤
│  rewind-ffi (Rust, this crate)      │
│  ├─ JSON wrappers (no_std friendly) │
│  └─ Type-safe FFI exports (future)  │
├─────────────────────────────────────┤
│  rewind-core (Rust scheduling lib)  │
│  ├─ Task, Goals, Finance            │
│  ├─ STS, MTS, LTS schedulers        │
│  └─ Serde support (JSON i/o)        │
└─────────────────────────────────────┘
```

## Building

### For Library (Rust)

```bash
cd rewind-ffi
cargo build --release
```

### For iOS (with UniFFI)

```bash
# Prerequisites
rustup target add aarch64-apple-ios
rustup target add aarch64-apple-ios-sim
cargo install uniffi-cli

# Build xcframework
./build_ios.sh  # (to be created)
```

This generates `rewind_ffi.xcframework` suitable for Xcode integration.

## API Reference

### JSON Wrapper Functions

All functions return `FfiResult` with:
- `success: bool` - operation succeeded
- `data: String` - JSON payload (on success) or error message (on failure)
- `error_code: i32` - 0 for success; error-specific codes otherwise

#### Goals

- `parse_goals_json(markdown: &str) -> FfiResult`
  - Parses `## Long-term`, `## Medium-term`, `## Short-term` sections
  - Returns array of `UserGoal` objects

- `plan_goal_steps_json(goal_json, signals_explicit, signals_implicit) -> FfiResult`
  - Returns milestone steps and `ReadinessScore`

#### Finance

- `categorize_transaction_json(description: &str) -> FfiResult`
  - Categories: Tuition, CreditCard, FamilySupport, Savings, Housing, Food, Subscriptions, Income, Uncategorized
  - Returns `{category, goal_tag, goal_name}`

#### Scheduling

- `route_task_json(task_json, goals_json) -> FfiResult`
  - Matches task to best goal by keyword overlap
  - Returns `RouteResult` with confidence level

- `handle_disruption_json(disruption, active, backlog, energy) -> FfiResult`
  - Re-prioritizes tasks after a disruption event
  - Returns `UpdatedSchedule` with new task order

#### Reminders

- `project_reminders_json(task_json, source, policy) -> FfiResult`
  - Generates reminder slots based on task priority and policy
  - Returns array of `ReminderIntent` objects

### Error Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1001-1003 | Goal parsing errors |
| 2001-2003 | Task routing errors |
| 3001-3003 | Goal planning errors |
| 4001-4004 | Scheduling/disruption errors |
| 5001-5002 | Reminder projection errors |

## Dependencies

- **rewind-core** (path dependency): Core scheduling engine
- **serde**: Serialization/deserialization
- **serde_json**: JSON support
- **chrono**: Date/time utilities
- **anyhow**: Error handling

Optional:
- **uniffi** (v0.28+): For Swift code generation (currently optional)

## Testing

```bash
cargo test --lib
```

Tests validate:
- JSON parsing and serialization
- Error handling and codes
- FfiResult success/error states
- Round-trip serde compatibility

## Future Work

### Phase 1: UniFFI Integration
- [ ] Add `#[uniffi::export]` macros to public functions
- [ ] Generate `.xcframework` for iOS deployment
- [ ] Create Xcode test project

### Phase 2: Advanced Features
- [ ] Add logging bridge (iOS Logger ↔ Rust log!)
- [ ] Storage abstraction for sandboxed paths
- [ ] Sync conflict resolution (CRDT or LWW)

### Phase 3: Full Integration
- [ ] Calendar event monitoring (disruption detector)
- [ ] Push notification dispatch
- [ ] Real-time schedule updates via WebSocket

## Architecture Notes

### Why JSON Wrappers?
1. **No FFI ceremony**: Pass strings, get strings back
2. **Platform agnostic**: Can be used from C, Swift, Python, etc.
3. **Transport friendly**: Works over REST, WebSocket, IPC
4. **Deterministic**: All inputs/outputs are text-based

### Why Keep rewind-core Async-Free?
1. **No Tokio dependency**: Lighter binary, fewer CVEs
2. **FFI-friendly**: Easier to bind to blocking C/Swift code
3. **Determinism**: No runtime surprises
4. **Server can add async**: rewind-service wraps rewind-core with tokio

### Storage Abstraction (TODO)
Currently, some functions assume paths like `~/.rewind/`. For iOS:
1. Use `FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)`
2. Pass sandbox-safe paths as function parameters
3. Avoid OS-specific filesystem access in rewind-core

## License

MIT (see ../LICENSE)

## Contributing

See main rewind repo for contribution guidelines.

---

**Maintained by:** Tarive  
**Repository:** https://github.com/Tar-ive/rewind  
**Latest commit:** Check `git log rewind-ffi/`
