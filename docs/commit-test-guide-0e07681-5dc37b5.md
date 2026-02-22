# Commit Test Guide: `0e07681` and `5dc37b5`

This guide shows how to test each commit independently, and then test both together.

- `0e07681` — docs: iOS ship checklist
- `5dc37b5` — finance: `RH_PYTHON` + `venv-rh` default for Robinhood bridge

## 0) Confirm commit availability

```bash
cd ~/rewind
git fetch origin
git show --no-patch --oneline 0e07681
git show --no-patch --oneline 5dc37b5
```

---

## 1) Rust/package versions at both commits

Both commits use the same workspace package versions.

### Workspace package version (both)
- `workspace.package.version = 0.1.13`
- `edition = 2024`

### Key workspace deps (both)
- `serde = 1.0`
- `tokio = 1.42`
- `anyhow = 1.0`
- `chrono = 0.4`
- `regex = 1.11`
- `csv = 1.3`
- `clap = 4.5`
- `chrono-tz = 0.10`
- `reqwest = 0.12`
- `serde_json = 1.0`

### Verify directly by commit
```bash
cd ~/rewind
for c in 0e07681 5dc37b5; do
  echo "=== $c"
  git show ${c}:Cargo.toml | sed -n '1,80p'
done
```

---

## 2) Test `0e07681` independently (docs commit)

This commit is docs-only. Validate file presence and markdown quality.

```bash
cd ~/rewind
git worktree add /tmp/rewind-0e 0e07681
cd /tmp/rewind-0e

# expected file from commit
ls -l docs/ios-ship-checklist.md

# optional markdown lint-ish checks
wc -l docs/ios-ship-checklist.md
head -n 30 docs/ios-ship-checklist.md
```

Pass criteria:
- `docs/ios-ship-checklist.md` exists
- Contains Mac preflight, build, FFI, QA, TestFlight, go/no-go sections

Cleanup:
```bash
cd ~/rewind
git worktree remove /tmp/rewind-0e
```

---

## 3) Test `5dc37b5` independently (Robinhood bridge behavior)

```bash
cd ~/rewind
git worktree add /tmp/rewind-5dc 5dc37b5
cd /tmp/rewind-5dc

# compile focused package
cargo check -p rewind-finance

# inspect commit target file
sed -n '1,220p' rewind-finance/src/robinhood_bridge.rs
```

### Functional smoke tests (env var + default path behavior)

#### A) Default path behavior (expects `venv-rh` fallback logic)
```bash
cd /tmp/rewind-5dc
cargo run -p rewind-cli -- finance robinhood --help
```

#### B) Explicit `RH_PYTHON`
```bash
cd /tmp/rewind-5dc
export RH_PYTHON="/usr/bin/python3"
# run a command path that touches bridge invocation
cargo run -p rewind-cli -- finance robinhood status || true
```

Pass criteria:
- `cargo check -p rewind-finance` succeeds
- Bridge code references `RH_PYTHON` and fallback handling

Cleanup:
```bash
cd ~/rewind
git worktree remove /tmp/rewind-5dc
```

---

## 4) Test both together

`rust-native` currently contains both commits, with `HEAD` at `5dc37b5`.

```bash
cd ~/rewind
git checkout rust-native
git pull origin rust-native

# verify both are in history
git log --oneline --decorate -20

# full workspace checks
cargo check
cargo test --no-run
```

### Combined acceptance checks
- Docs path exists: `docs/ios-ship-checklist.md`
- Robinhood bridge compiles and still honors `RH_PYTHON`
- Workspace checks pass (`cargo check`, `cargo test --no-run`)

---

## 5) Quick one-shot verification script

```bash
cd ~/rewind
set -e

git show --no-patch --oneline 0e07681
git show --no-patch --oneline 5dc37b5

git checkout rust-native
git pull origin rust-native

[ -f docs/ios-ship-checklist.md ]

grep -n "RH_PYTHON\|venv-rh" rewind-finance/src/robinhood_bridge.rs

cargo check -p rewind-finance
cargo check
cargo test --no-run

echo "OK: 0e07681 + 5dc37b5 validated together on rust-native"
```
