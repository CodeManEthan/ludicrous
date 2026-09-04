#!/usr/bin/env bash
# Build the native batch runner the Python server spawns, as a static musl
# binary so it runs unchanged inside the python:3.12-slim deploy image.
# Output: ../bin/lud-batch (committed, like the wasm bundle).
#
#   rustup target add x86_64-unknown-linux-musl   # once
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.cargo/bin:$PATH"
cargo build --release -p ludicrous-batch --target x86_64-unknown-linux-musl
mkdir -p ../bin
cp target/x86_64-unknown-linux-musl/release/lud-batch ../bin/lud-batch
strip ../bin/lud-batch 2>/dev/null || true
ls -la ../bin/lud-batch
file ../bin/lud-batch
