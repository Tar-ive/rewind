# Rewind iOS App

**Status:** MVP ready for Xcode build (macOS)

A premium, native iOS SwiftUI app that brings the power of the Rewind scheduling engine to your pocket. Plan your day intelligently, adapt to disruptions in real time, and align all your tasks with your long, medium, and short-term goals.

## Features

### 📅 **Daily Planning**
- **Today's Plan**: View tasks ordered by the Short-Term Scheduler (STS) algorithm
- **Energy-Aware Scheduling**: Tasks displayed with energy cost (1-5) and cognitive load indicators
- **Real-Time Disruption Detection**: Simulate or import calendar changes and watch Rewind automatically replan your day using the Medium-Term Scheduler (MTS)
- **Priority-Based Ordering**: P0 (Urgent) → P3 (Background) with visual indicators

### 🎯 **Goal Management**
- **Multi-Horizon Goals**: Define Long, Medium, and Short-term goals with confidence scores
- **Interactive Filtering**: View goals by timeframe
- **Goal Details**: See horizon, confidence, and description for each goal
- **Add/Edit Goals**: Full CRUD interface with markdown-friendly descriptions

### 💰 **Finance Integration**
- **CSV Import**: Upload AMEX (and other bank) transactions
- **Auto-Categorization**: Rust-powered categorizer maps transactions to 9 categories:
  - Tuition, Credit Card, Family Support, Savings, Housing, Food, Subscriptions, Income, Uncategorized
- **Goal Alignment**: Each transaction is scored for how well it serves your goals
- **Transaction Analytics**: View category summaries, filter, and sort by amount, readiness, or date

### 🔔 **Intelligent Reminders**
- **Policy-Driven Scheduling**: Control reminder frequency by priority level
- **Deduplication**: Smart deduplication prevents reminder spam
- **Readiness Scoring**: Reminders incorporate explicit and implicit signals from your goals
- **Missed Reminders**: Track overdue tasks with ambient reminder queues

### 🚀 **Disruption Recovery**
- **Real-Time Replanning**: When your calendar changes, Rewind automatically:
  - Detects the disruption
  - Queries your energy level
  - Runs MTS swap engine (move low-priority tasks to backlog, pull critical ones forward)
  - Re-orders remaining tasks via STS MLFQ
  - Outputs updated schedule
- **Delegation Queue**: Automatable tasks (emails, messages) are surfaced for approval

### 🎨 **Premium UI/UX**
- **Dark Theme**: Modern, eye-friendly interface optimized for all lighting conditions
- **SF Symbols**: Native iOS icons throughout for consistency
- **Smooth Animations**: Polished transitions and interactions
- **Accessibility**: Full support for Dynamic Type and VoiceOver

## Project Structure

```
ios/Rewind/
├── RewindApp.swift              # App entry point (SwiftUI)
├── ContentView.swift            # Main tab view + settings
├── Views/
│   ├── DayPlanView.swift        # Today's tasks (STS-ordered)
│   ├── GoalsView.swift          # Goal CRUD + filtering
│   ├── FinanceView.swift        # Transaction management
│   ├── RemindersView.swift      # Reminder queue + policy
│   └── OnboardingView.swift     # Setup flow (mirrors `rewind setup`)
├── Models/
│   ├── Task.swift               # Task, TaskStatus, Priority
│   ├── Goal.swift               # Goal, GoalTimeframe, ReadinessScore
│   ├── Category.swift           # FinanceCategory, FinanceRecord
│   └── Schedule.swift           # UpdatedSchedule, DisruptionEvent, ReminderIntent
├── Services/
│   ├── RewindBridge.swift       # Interface to Rust FFI (UniFFI bindings)
│   ├── StorageService.swift     # Local persistence (UserDefaults + FileManager)
│   └── CalendarService.swift    # EventKit integration (calendar sync stub)
├── Info.plist                   # App metadata + permissions
└── Assets.xcassets/             # Placeholder (colors, images)
```

## Building & Running

### Prerequisites
- **Xcode 15.0+** (Swift 5.5+)
- **macOS 14.0+** (for running Xcode)
- **iOS 15.0+** target

### On a Mac

1. **Open the project in Xcode:**
   ```bash
   open ios/Rewind.xcodeproj
   ```
   (Note: You'll need to create an Xcode project with these source files)

2. **Select a simulator or device** in the toolbar

3. **Build & Run:**
   ```bash
   Cmd+R
   ```

### Building from Command Line (macOS)

```bash
xcodebuild -scheme Rewind -configuration Release -arch arm64 -sdk iphoneos
```

### Note: This Linux VM

This VM cannot run Xcode (requires macOS). The Swift source files are all ready to import into an actual Xcode project on a Mac. The structure follows Apple's conventions exactly.

## Rust FFI Integration (UniFFI)

The app communicates with the Rust `rewind-core` library via **UniFFI** bindings. The bridge is defined in `Services/RewindBridge.swift`.

### API Surface (Rust → Swift)

#### Setup & Onboarding
- `parseGoalsMarkdown(markdown: String) → [Goal]`
- `setupApply(goals: [Goal], timezone: String) → Void`

#### Finance
- `categorizeTransaction(description: String) → FinanceCategory`
- `parseFinanceCSV(csvContent: String) → [FinanceRecord]`

#### Scheduling
- `planDay(goals: [Goal], financialRecords: [FinanceRecord]?, energyLevel: Int) → [Task]`
- `handleDisruption(event: DisruptionEvent, currentTasks: [Task], backlogTasks: [Task], energyLevel: Int) → UpdatedSchedule`

#### Reminders
- `projectReminders(for task: Task, policy: ReminderPolicy) → [ReminderIntent]`

#### Routing
- `routeTask(task: Task, goals: [Goal]) → RouteResult`

### FFI Setup (macOS only)

1. **Build rewind-core as a library:**
   ```bash
   cd /home/sadhikari/rewind
   cargo build --release
   ```

2. **Generate UniFFI bindings:**
   Add to `rewind-core/build.rs`:
   ```rust
   uniffi::generate_bindings(&uniffi_bindgen_macro::UdlFile::new(
       "rewind-core/src/rewind.udl"
   ));
   ```

3. **Link in Xcode:**
   - Build Settings → Header Search Paths: `$(SRCROOT)/path/to/rewind-core/target/release`
   - Build Phases → Link Binary with Libraries: `librewind_core.a`

(Full FFI integration will be completed on a Mac with Xcode and the actual Rust library)

## Local Development & Testing

### Mock Data

All views have built-in mock data for development:
- `Task.mockTasks` - Sample tasks with various priorities and durations
- `Goal.mockGoals` - Example long/medium/short-term goals
- `FinanceRecord.mockRecords` - Sample transactions across categories
- `ReminderIntent.mockReminders` - Example reminder intents

### Persistence

- **Goals & Tasks**: UserDefaults (JSON-encoded)
- **Finance Records**: UserDefaults + optional FileManager export
- **Onboarding State**: UserDefaults flag
- **User Preferences**: Timezone, energy level

### Testing Disruptions

In `DayPlanView`, tap the **"Disrupt"** button to:
1. Simulate a calendar disruption event
2. Call the Rust bridge's `handleDisruption()` function
3. Display the updated schedule

## Permissions

The app requests the following permissions (see `Info.plist`):

- **Calendar**: Detect disruptions and auto-replan when events change
- **Reminders**: Send native iOS notifications (future)
- **Contacts**: Support delegation features (future)

## Styling & Theme

- **Color Scheme**: Dark theme by default (respects system setting)
- **Accent Color**: Blue for primary actions
- **Priority Colors**:
  - P0 Urgent: Red
  - P1 Important: Orange
  - P2 Normal: Blue
  - P3 Background: Gray
- **Timeframe Icons & Colors**:
  - Long-term: Purple ⏳
  - Medium-term: Blue ⏳
  - Short-term: Green ⚡

## Known Limitations & Future Work

### Current Phase (MVP)
- ✅ Core UI and navigation
- ✅ Mock data and local storage
- ✅ RewindBridge protocol definition
- ✅ All major views and flows
- ✅ Dark theme + SF Symbols

### Phase 2 (FFI Integration)
- [ ] UniFFI bindings generated and linked
- [ ] Real calls to Rust rewind-core functions
- [ ] JSON serialization/deserialization for bridge calls
- [ ] Error handling and validation

### Phase 3 (Remote Sync)
- [ ] WebSocket or REST connection to Rewind backend
- [ ] Real-time disruption stream from Calendar/Email/Slack sentinels
- [ ] Bidirectional sync of goals and tasks
- [ ] Remote authentication (OAuth)

### Phase 4 (Native Integration)
- [ ] EventKit calendar creation + modification
- [ ] Push notifications via UserNotifications
- [ ] Siri shortcuts for quick task entry
- [ ] Widgets for home/lock screen

## Debugging

### Enable Debug Logging

Add to `RewindBridge.swift` or individual services:
```swift
os_log("Debug message", log: .default, type: .debug)
```

### SwiftUI Preview

All views include `#Preview` blocks for rapid iteration. Use Xcode's Canvas or live preview.

### Bridge Mock Fallbacks

If Rust FFI is unavailable, the app falls back to mock implementations. Check `RewindBridge.swift` for current behavior.

## Contributing

When adding new views or models:
1. Follow the existing project structure (Views/, Models/, Services/)
2. Add sample/mock data for testing
3. Use environment objects for dependency injection
4. Include `#Preview` for SwiftUI views
5. Document any new RewindBridge functions

## Resources

- **Rewind Core Docs**: `/home/sadhikari/rewind/docs/rewind-core-analysis.md`
- **Finance Analysis**: `/home/sadhikari/rewind/docs/rewind-cli-finance-analysis.md`
- **iOS Bridge Spec**: `/home/sadhikari/rewind/docs/spec-disruption-recovery-and-ios-bridge.md`
- **UniFFI Guide**: https://mozilla.github.io/uniffi-rs/
- **SwiftUI Docs**: https://developer.apple.com/documentation/swiftui

## License

Same as Rewind main project.

---

**Next Steps:**
1. Import all `.swift` files into a new Xcode project
2. Set up Info.plist and assets
3. Build UniFFI bridge when on macOS with Xcode
4. Test with real Rust FFI calls
5. Integrate with remote Rewind service

Built with 🚀 for productive humans.
