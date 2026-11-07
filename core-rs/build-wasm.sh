#!/usr/bin/env bash
# Build the wasm bundle twice: once for Node (pkg/, used by bench/) and once
# for the browser (../web/core/, committed so `git clone && python3 server.py`
# needs no build step).
#
# The browser build is --target no-modules on purpose: web/app.js is a classic
# script and the wasm lives in a classic Worker, so importScripts() has to be
# able to pull the glue in. Needs rustc 1.98.0 with the wasm32-unknown-unknown
# target and wasm-bindgen 0.2.127 (see pinned-env.sh).
#
# No wasm-opt: its output depends on the binaryen version, and the committed
# files must rebuild byte for byte from the source and the pinned tools alone.
set -euo pipefail

cd "$(dirname "$0")"
source ./pinned-env.sh

require_pinned_rustc
require_pinned_wasm_bindgen

TARGET_DIR=target/wasm32-unknown-unknown/release
OUT=pkg
WEB_OUT=../web/core

pinned_cargo build --locked --release -p ludicrous-wasm --target wasm32-unknown-unknown

# ---- Node bundle (benchmarks)
rm -rf "$OUT"
wasm-bindgen "$TARGET_DIR/ludicrous_wasm.wasm" --out-dir "$OUT" --target nodejs
RAW=$(stat -c %s "$OUT/ludicrous_wasm_bg.wasm")
gzip -9 -c "$OUT/ludicrous_wasm_bg.wasm" > "$OUT/ludicrous_wasm_bg.wasm.gz"
GZ=$(stat -c %s "$OUT/ludicrous_wasm_bg.wasm.gz")

# ---- Browser bundle (committed into the web app)
rm -rf "$WEB_OUT"
wasm-bindgen "$TARGET_DIR/ludicrous_wasm.wasm" --out-dir "$WEB_OUT" \
  --target no-modules --no-typescript

# Stamp the glue so nobody hand-edits a generated file.
HEADER=$(cat <<'EOF'
// GENERATED FILE -- do not edit.
// Built from core-rs/ by core-rs/build-wasm.sh (wasm-bindgen --target no-modules).
// Rebuild with:  ./core-rs/build-wasm.sh
EOF
)
printf '%s\n%s\n' "$HEADER" "$(cat "$WEB_OUT/ludicrous_wasm.js")" \
  > "$WEB_OUT/ludicrous_wasm.js.tmp"
mv "$WEB_OUT/ludicrous_wasm.js.tmp" "$WEB_OUT/ludicrous_wasm.js"

WEB_WASM=$(stat -c %s "$WEB_OUT/ludicrous_wasm_bg.wasm")
WEB_GZ=$(gzip -9 -c "$WEB_OUT/ludicrous_wasm_bg.wasm" | wc -c)

printf 'wasm.bytes.raw\t%s\n'        "$RAW"
printf 'wasm.bytes.gzipped\t%s\n'    "$GZ"
printf 'wasm.js_glue_bytes\t%s\n'    "$(stat -c %s "$OUT/ludicrous_wasm.js")"
printf 'web.wasm_bytes\t%s\n'        "$WEB_WASM"
printf 'web.wasm_gzipped\t%s\n'      "$WEB_GZ"
printf 'web.js_glue_bytes\t%s\n'     "$(stat -c %s "$WEB_OUT/ludicrous_wasm.js")"
