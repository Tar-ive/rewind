# Rewind iOS Ship Checklist (rust-native) — Execution Ready

**Scope:** fastest path from current `rust-native` branch to TestFlight build.

**Repo source of truth:** `/home/sadhikari/rewind`  
**Branch:** `rust-native`  
**iOS sources:** `ios/Rewind` (Swift files only, no `.xcodeproj` yet)  
**Rust FFI crate:** `rewind-ffi`

---

## Assumptions (explicit)

1. You have Apple Developer Program access with an **Admin/App Manager** role on the team that will sign the app.
2. You will perform build/sign/archive on a **real Mac** (cannot be completed in this Linux VM).
3. You are okay shipping MVP behavior with current mock-backed bridge unless FFI wiring is fully completed (below includes both).
4. App identifier target is `com.rewind.ios` (change if needed before provisioning).

---

## 1) Preflight (Mac requirements)

## Must be done on Mac (not possible on Linux VM)
- Install/launch Xcode and iOS SDKs
- Create/sign iOS app certificates & provisioning
- Archive + upload to App Store Connect
- Run iOS Simulator / physical iPhone tests

## Toolchain checks (copy/paste)
```bash
# Xcode (recommend 16.x; minimum 15.x)
xcodebuild -version
xcode-select -p

# Accept license if needed
sudo xcodebuild -license accept

# Rust
rustup --version
cargo --version

# iOS Rust targets (device + simulator)
rustup target add aarch64-apple-ios aarch64-apple-ios-sim x86_64-apple-ios

# CocoaPods/SPM assumptions for this repo
# (there is currently NO Podfile/Package.swift under /home/sadhikari/rewind)
find /path/to/rewind \( -name 'Podfile' -o -name 'Package.swift' \) -print
```

## Apple account + App Store Connect checks
- [ ] Apple ID can sign into Xcode (`Xcode > Settings > Accounts`).
- [ ] Team selected in Xcode and has active membership.
- [ ] App Store Connect app record exists (or create it) for final bundle id.
- [ ] Bundle ID is registered in Certificates, IDs & Profiles.
- [ ] At least one iOS Distribution cert/profile available for release upload.

---

## 2) Exact terminal commands on Mac

## 2.1 Get latest code and verify structure
```bash
# If fresh clone
git clone <YOUR_REMOTE_URL> rewind
cd rewind
git checkout rust-native
git pull --ff-only origin rust-native

# If repo already cloned
cd /path/to/rewind
git fetch origin
git checkout rust-native
git pull --ff-only origin rust-native

# Verify expected files
ls -la ios/Rewind
ls -la rewind-ffi
test -f ios/Rewind/RewindApp.swift && echo "OK: Swift sources present"
test -f rewind-ffi/src/lib.rs && echo "OK: FFI crate present"
```

## 2.2 Build Rust static libs for iOS
```bash
cd /path/to/rewind

# clean optional
cargo clean -p rewind-ffi

# Device
cargo build -p rewind-ffi --release --target aarch64-apple-ios

# Simulator (Apple Silicon)
cargo build -p rewind-ffi --release --target aarch64-apple-ios-sim

# Simulator (Intel, optional but useful for CI/legacy Macs)
cargo build -p rewind-ffi --release --target x86_64-apple-ios
```

## 2.3 Create universal simulator lib + xcframework
```bash
cd /path/to/rewind

mkdir -p build/ios

# Merge simulator arches (if both exist)
lipo -create \
  target/aarch64-apple-ios-sim/release/librewind_ffi.a \
  target/x86_64-apple-ios/release/librewind_ffi.a \
  -output build/ios/librewind_ffi_sim.a

# Create xcframework (best for Xcode integration)
xcodebuild -create-xcframework \
  -library target/aarch64-apple-ios/release/librewind_ffi.a \
  -library build/ios/librewind_ffi_sim.a \
  -output build/ios/RewindFFI.xcframework
```

## 2.4 Generate UniFFI Swift bindings (if needed)
> Current repo has `rewind-ffi/src/rewind_ffi.udl` and `#[cfg_attr(feature="uniffi-bindings", uniffi::export)]` exports, but no committed `build.rs`/generated Swift output. Use this only if you choose typed UniFFI route now.

```bash
cd /path/to/rewind

# install tool if missing
cargo install uniffi_bindgen --locked || true

# generate Swift bindings from UDL
mkdir -p ios/Rewind/Generated
uniffi-bindgen generate rewind-ffi/src/rewind_ffi.udl \
  --language swift \
  --out-dir ios/Rewind/Generated

ls -la ios/Rewind/Generated
```

## 2.5 Create/open Xcode project (required; not in repo today)
```bash
cd /path/to/rewind
open -a Xcode
# Then in Xcode:
# File > New > Project > iOS App > Name: Rewind > Interface: SwiftUI > Language: Swift
# Save as ios/Rewind.xcodeproj (or ios/RewindApp/Rewind.xcodeproj)
```

---

## 3) Xcode target setup checklist

## Project/Target
- [ ] Target name: `Rewind`
- [ ] Bundle ID: `com.rewind.ios` (or final production ID)
- [ ] Version: `1.0.0` (Marketing) and Build number incremented
- [ ] iOS Deployment target: **15.0+**
- [ ] Team + Signing: Automatic signing enabled (or manual with valid profile)

## Add source files
- [ ] Add all files under `ios/Rewind/**` into target membership `Rewind`.
- [ ] Ensure `Info.plist` path points to imported plist (or merge keys into generated plist).

## Link Rust artifact
**Preferred:** use `RewindFFI.xcframework`
- [ ] Drag `build/ios/RewindFFI.xcframework` into Xcode project.
- [ ] Target > General > Frameworks, Libraries, and Embedded Content: add framework (**Do Not Embed** for static).

**Alternative:** static `.a`
- [ ] Build Settings > Library Search Paths includes rust target output dirs.
- [ ] Build Phases > Link Binary With Libraries includes `librewind_ffi.a`.

## Build Phases (if automating Rust rebuild)
- [ ] Add **Run Script** before link:
```bash
set -euo pipefail
cd "$SRCROOT/.."   # adjust if project nested
cargo build -p rewind-ffi --release --target aarch64-apple-ios
cargo build -p rewind-ffi --release --target aarch64-apple-ios-sim
```

## Info.plist/privacy permissions
Current plist already includes:
- `NSCalendarsUsageDescription`
- `NSRemindersUsageDescription`
- `NSContactsUsageDescription`

Ship checks:
- [ ] Text is user-readable and matches actual feature usage.
- [ ] Remove permissions you do not actually use in MVP to reduce review risk.

---

## 4) FFI wiring checklist

## File to edit first
- `ios/Rewind/Services/RewindBridge.swift`

## Current state
- Bridge methods exist but are mostly mock implementations (`TODO: Call Rust FFI`).

## Wiring path (minimum viable)
1. Add generated UniFFI Swift files (if using UniFFI) into target.
2. `import` generated module in `RewindBridge.swift`.
3. Replace one mock function end-to-end first (recommended: `categorizeTransaction`).
4. Map Rust response to app model (`FinanceCategory`).
5. Repeat for `parseFinanceCSV`, `planDay`, `handleDisruption`.

## Sample call path (smoke target)
`FinanceView` UI action -> `RewindBridge.categorizeTransaction(_:)` -> Rust `categorize_transaction_json` -> Swift mapping -> category chip in UI updates.

## Smoke tests (must pass)
- [ ] Input `"ZELLE MOM"` returns `FamilySupport` (or expected mapping).
- [ ] Input `"TUITION PAYMENT"` returns `Tuition`.
- [ ] App does not crash when Rust lib unavailable (graceful error path).
- [ ] Release build launches on physical device with linked Rust library.

---

## 5) Functional QA matrix (MVP)

| Area | Test | Expected | Fail if |
|---|---|---|---|
| Onboarding | Complete 3-step flow | Lands in main tabs, state persisted | Loop back / blank screen |
| Today tab | Load day plan | Task list renders, priority badges visible | Empty due to crash/parse error |
| Goals tab | Add/Edit/Delete goal | CRUD persists across relaunch | Data lost or stale UI |
| Finance tab | Import sample CSV/mock | Records shown + category summary | Parse failure without error UX |
| Finance->FFI | Categorize sample descriptions | Deterministic categories | Random/incorrect mapping |
| Reminders tab | Generate reminders | Upcoming/missed sections populate | No reminders or duplicate spam |
| Disruption flow | Trigger “Disrupt” | Updated schedule appears | App freeze/crash |
| Settings | Change timezone/energy | Values persist and reflect in views | Reverts after relaunch |
| Offline behavior | Airplane mode (if any network calls added) | App usable with local data | Blocking errors |
| Permissions | Calendar/Reminders prompts | Prompt appears once + graceful deny handling | Crash on deny |

**Mock data paths in code:** `Task.mockTasks`, `Goal.mockGoals`, `FinanceRecord.mockRecords`, `ReminderIntent.mockReminders`.

---

## 6) Release hardening checklist

- [ ] App icon set complete in `Assets.xcassets` including 1024x1024 App Store icon.
- [ ] Launch/splash and empty states look intentional (no placeholders).
- [ ] Versioning: set `CFBundleShortVersionString` and increment `CFBundleVersion` for each upload.
- [ ] Privacy review:
  - [ ] Keep only required `NS*UsageDescription` keys.
  - [ ] Add `PrivacyInfo.xcprivacy` if any required-reason API/SDK usage applies.
- [ ] Crash logging decision made (none / Sentry / Firebase Crashlytics) and verified in release config.
- [ ] No debug prints, TODO banners, or mock-only labels visible to testers.
- [ ] App Store metadata prepared: subtitle, description, keywords, support URL, privacy policy URL.
- [ ] iPhone screenshots captured for required sizes.
- [ ] Release notes drafted for TestFlight build.

---

## 7) TestFlight submission steps (exact sequence)

1. **App Store Connect**
   - My Apps -> `+` -> New App (if not created)
   - Set platform iOS, app name, primary language, bundle ID, SKU.

2. **Xcode archive/upload (Mac only)**
```bash
# from project directory containing .xcodeproj
xcodebuild -scheme Rewind -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath build/Rewind.xcarchive archive

xcodebuild -exportArchive \
  -archivePath build/Rewind.xcarchive \
  -exportOptionsPlist ExportOptions.plist \
  -exportPath build/export
```
(Or use Xcode Organizer -> Distribute App -> App Store Connect -> Upload.)

3. **Process build**
   - Wait until build appears under TestFlight.

4. **TestFlight config**
   - Add compliance/privacy answers.
   - Add internal testers first.
   - Add external group only after internal sanity pass.
   - Fill What to Test notes.

5. **Release to testers**
   - Internal: immediate.
   - External: submit for Beta App Review if prompted.

---

## 8) Go/No-Go gate (objective)

## Go only if ALL pass
- [ ] `xcodebuild archive` succeeds on clean checkout.
- [ ] App launches on 1 physical iPhone (iOS 15+) with no startup crash.
- [ ] Core tabs (Today/Goals/Finance/Reminders) each pass one full user action.
- [ ] Finance categorization smoke tests match expected output for at least 10 known inputs.
- [ ] Permission deny paths (Calendar/Reminders/Contacts) do not crash.
- [ ] No P0/P1 defects open.
- [ ] TestFlight build distributed to internal testers with release notes.

## No-Go triggers
- Archive/signing failures
- Crash in first 60 seconds of launch/session
- Broken onboarding or data loss across relaunch
- Privacy permission text mismatch vs actual behavior

---

## 9) Timeboxed plan (Day 0/1/2)

## Day 0 (3-4h): Build lane + signing
- [ ] Mac preflight, Xcode + Rust targets, Apple account setup (1h)
- [ ] Create Xcode project and import Swift sources (1h)
- [ ] Build Rust iOS libs + xcframework and link (1-2h)

## Day 1 (5-7h): FFI + QA
- [ ] Wire at least one real FFI path (`categorizeTransaction`) (2h)
- [ ] Extend to remaining critical bridge methods or keep controlled mock fallback with explicit flags (2-3h)
- [ ] Run full QA matrix on simulator + 1 real device (1-2h)

## Day 2 (3-5h): Hardening + TestFlight
- [ ] Finalize icons/privacy/version/build number (1-2h)
- [ ] Archive + upload + resolve App Store Connect metadata/compliance (1-2h)
- [ ] Internal tester rollout + triage window (1h)

**Expected fastest TestFlight ETA:** ~2 working days if no signing/review blockers.

---

## Linux VM limitations (explicit)

From this Linux environment you can **prepare code/docs only**. You **cannot**: run Xcode, iOS Simulator, code sign, archive `.xcarchive`, or upload to TestFlight. Those steps require macOS.
