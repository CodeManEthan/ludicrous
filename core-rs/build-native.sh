#!/usr/bin/env bash
# Build the native batch runner the Python server spawns, as a static musl
# binary so it runs unchanged inside the python:3.12-slim deploy image.
# Output: ../bin/lud-batch (committed, like the wasm bundle).
#
# Needs rustc 1.98.0 with the x86_64-unknown-linux-musl target (see
# pinned-env.sh). It is linked by the rust-lld bundled with rustc, against
# the musl CRT objects rustc ships, and symbols are stripped by rustc (-C
# strip=symbols): the system linker and `strip` lay out the binary differently
# from one binutils version to the next. No wasm-opt or any other tool
# post-processes the binary: it must rebuild byte for byte from the source and
# the pinned tools alone.
set -euo pipefail
cd "$(dirname "$0")"
source ./pinned-env.sh
require_pinned_rustc

RUSTFLAGS_EXTRA=("-Clinker=rust-lld" "-Clinker-flavor=ld.lld" "-Cstrip=symbols")
pinned_cargo build --locked --release -p ludicrous-batch --target x86_64-unknown-linux-musl
mkdir -p ../bin
cp target/x86_64-unknown-linux-musl/release/lud-batch ../bin/lud-batch
ls -la ../bin/lud-batch
if command -v file >/dev/null 2>&1; then
  file ../bin/lud-batch
fi
