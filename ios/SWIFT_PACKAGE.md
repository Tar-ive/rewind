# Swift Package Structure for Rewind iOS

## Overview

This document describes how to build the Rewind iOS app and integrate it with the Rust FFI.

## Prerequisites

- **Xcode 15.0 or later**
- **macOS 14.0 or later** (for development)
- **iOS 15.0 or later** (target)
- **Swift 5.5+**
- Rust toolchain (for FFI compilation)

## Project Setup

### 1. Create Xcode Project

```bash
# Create new app project
mkdir -p ios/RewindApp
cd ios/RewindApp
```

### 2. Organize Source Files

```
RewindApp/
├── RewindApp.swift                 # App entry point
├── ContentView.swift               # Main view
├── Views/                          # All view files
├── Models/                         # Data models
├── Services/                       # Services & FFI bridge
├── Resources/                      # Assets & localization
│   ├── Localizable.strings
│   └── Assets.xcassets
└── Info.plist
```

### 3. Build Settings

#### iOS Deployment Target
- **Minimum**: iOS 15.0
- **Recommended**: iOS 16.0+

#### Build Settings (Summary)
- **Product Name**: Rewind
- **Bundle Identifier**: com.rewind.ios
- **Team ID**: (your Apple developer team)
- **Signing Certificate**: Development or Distribution

#### Capabilities to Enable
- [x] Push Notifications (for reminders)
- [x] Calendar (for disruption detection)
- [x] Reminders (native reminders integration)
- [x] Contacts (for delegation features - future)

## Rust FFI Integration

### Build rewind-core

```bash
cd /home/sadhikari/rewind

# Build as static library (release)
cargo build --release

# Output: target/release/librewind_core.a
```

### Generate Swift Bindings (UniFFI)

1. **Add uniffi to rewind-core Cargo.toml:**
   ```toml
   [dependencies]
   uniffi = { version = "0.26", features = ["cli"] }
   
   [build-dependencies]
   uniffi = { version = "0.26", features = ["build"] }
   ```

2. **Create rewind-core/build.rs:**
   ```rust
   use uniffi::generate_bindings;
   
   fn main() {
       generate_bindings(
           "src/rewind.udl",
           None,
           vec!["src/"],
           None,
       ).unwrap();
   }
   ```

3. **Define FFI interface (rewind-core/src/rewind.udl):**
   ```
   namespace rewind {
       
       // Setup
       sequence<Goal> parse_goals_markdown(string markdown);
       void setup_apply(sequence<Goal> goals, string timezone);
       
       // Finance
       CategoryResult categorize_transaction(string description);
       sequence<FinanceRecord> parse_finance_csv(string csv_content);
       
       // Scheduling
       sequence<Task> plan_day(
           sequence<Goal> goals,
           sequence<FinanceRecord>? records,
           i32 energy_level
       );
       UpdatedSchedule handle_disruption(
           DisruptionEvent event,
           sequence<Task> current_tasks,
           sequence<Task> backlog_tasks,
           i32 energy_level
       );
       
       // Reminders
       sequence<ReminderIntent> project_reminders(
           Task task,
           ReminderPolicy policy
       );
       
       // Routing
       RouteResult route_task(Task task, sequence<Goal> goals);
   };
   ```

4. **Generate bindings:**
   ```bash
   cd rewind-core
   cargo build --release --features uniffi/cli
   
   # Generate Swift bindings
   cargo run --features uniffi/cli --bin uniffi-bindgen -- \
       generate src/rewind.udl \
       --language swift \
       --out-dir ../ios/Bindings
   ```

### Link in Xcode

1. **Add to Build Settings:**
   - **Header Search Paths**: `$(SRCROOT)/path/to/rewind-core/target/release`
   - **Library Search Paths**: `$(SRCROOT)/path/to/rewind-core/target/release`

2. **Link Binary with Libraries:**
   - Add `librewind_core.a`

3. **Copy Bindings:**
   - Run Build Phase script to copy Swift bindings to source root

## Building & Running

### From Xcode

1. Open `Rewind.xcodeproj` in Xcode
2. Select target device/simulator
3. Press `Cmd+B` to build
4. Press `Cmd+R` to run

### From Command Line

```bash
# Build
xcodebuild -scheme Rewind -configuration Debug -destination 'platform=iOS Simulator,name=iPhone 15'

# Run on simulator
xcrun simctl launch booted com.rewind.ios

# Build for release
xcodebuild -scheme Rewind -configuration Release -arch arm64 -sdk iphoneos
```

## Testing

### Unit Tests

Create `RewindTests.swift`:
```swift
import XCTest
@testable import Rewind

class RewindBridgeTests: XCTestCase {
    func testParseGoalsMarkdown() {
        // Test FFI calls
    }
    
    func testCategorizeTransaction() {
        // Test transaction categorization
    }
}
```

Run tests:
```bash
xcodebuild test -scheme Rewind
```

### UI Tests

Test views with SwiftUI preview snapshots and UITest classes.

## Debugging

### Enable Console Logging

In `RewindBridge.swift`:
```swift
import os

let logger = Logger(subsystem: "com.rewind.ios", category: "bridge")

logger.debug("Calling Rust function...")
```

View logs in Xcode Console or Console.app.

### Breakpoints in Swift

Set breakpoints in any Swift file and run with debugger attached.

### FFI Debugging

For Rust FFI debugging, use:
- `RUST_LOG=debug` environment variable
- Rust backtrace: `RUST_BACKTRACE=1`

## Deployment

### App Store Submission

1. Create App Store Connect account
2. Register Bundle ID: `com.rewind.ios`
3. Create App ID and Provisioning Profile
4. Archive and upload:
   ```bash
   xcodebuild archive -scheme Rewind -archivePath ./build/Rewind.xcarchive
   xcodebuild -exportArchive -archivePath ./build/Rewind.xcarchive \
       -exportPath ./build -exportOptionsPlist ExportOptions.plist
   ```
5. Review and submit in App Store Connect

### Beta Testing (TestFlight)

Upload .ipa to TestFlight for beta testing.

## Performance Optimization

- **App Size**: Keep Rust library under 5MB (use `strip` and link-time optimization)
- **Startup Time**: Cache parsed goals/tasks in UserDefaults
- **Memory**: Use Combine publishers with proper memory management
- **Battery**: Limit background updates and heavy operations

## Continuous Integration

### GitHub Actions Example

```yaml
name: Build Rewind iOS

on: [push, pull_request]

jobs:
  build:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Rust FFI
        run: |
          cd rewind-core
          cargo build --release --target aarch64-apple-ios
      - name: Build iOS App
        run: |
          xcodebuild -scheme Rewind \
            -configuration Release \
            -arch arm64 \
            -sdk iphoneos
```

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "Cannot find rewind_core in module" | Ensure UniFFI bindings are generated and imported |
| App crashes on startup | Check rewind-core binary compatibility (arm64 vs x86_64) |
| Xcode code completion not working | Rebuild project (`Cmd+Shift+K` then `Cmd+B`) |
| FFI calls return nil | Verify Rust library is properly linked in Build Phases |

### Check Linker Output

```bash
xcrun nm -D librewind_core.a | grep rewind
```

## Next Steps

1. ✅ Source code written (all Swift files in this repo)
2. ⏳ Set up Xcode project
3. ⏳ Build rewind-core as library
4. ⏳ Generate UniFFI bindings
5. ⏳ Link and integrate in Xcode
6. ⏳ Test on iOS simulator
7. ⏳ Test on real device
8. ⏳ App Store submission

---

**Resources:**
- [UniFFI Documentation](https://mozilla.github.io/uniffi-rs/)
- [SwiftUI Documentation](https://developer.apple.com/documentation/swiftui)
- [Xcode Help](https://help.apple.com/xcode/)
- [iOS Development Guide](https://developer.apple.com/design/)
