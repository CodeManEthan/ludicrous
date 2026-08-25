#!/usr/bin/env bash
# Build the wasm bundle for Node (swap --target nodejs for web/bundler when
# the browser build lands). Expects wasm-bindgen 0.2.127 and, optionally,
# wasm-opt on PATH or in WASM_TOOLS.
set -euo pipefail

cd "$(dirname "$0")"
export PATH="$HOME/.cargo/bin:${WASM_TOOLS:-}:$PATH"

TARGET_DIR=target/wasm32-unknown-unknown/release
OUT=pkg

cargo build --release -p ludicrous-wasm --target wasm32-unknown-unknown

rm -rf "$OUT"
wasm-bindgen "$TARGET_DIR/ludicrous_wasm.wasm" --out-dir "$OUT" --target nodejs

RAW=$(stat -c %s "$OUT/ludicrous_wasm_bg.wasm")

if command -v wasm-opt >/dev/null 2>&1; then
  wasm-opt -O3 --enable-bulk-memory --enable-nontrapping-float-to-int \
    "$OUT/ludicrous_wasm_bg.wasm" -o "$OUT/ludicrous_wasm_bg.opt.wasm"
  mv "$OUT/ludicrous_wasm_bg.opt.wasm" "$OUT/ludicrous_wasm_bg.wasm"
fi

FINAL=$(stat -c %s "$OUT/ludicrous_wasm_bg.wasm")
gzip -9 -c "$OUT/ludicrous_wasm_bg.wasm" > "$OUT/ludicrous_wasm_bg.wasm.gz"
GZ=$(stat -c %s "$OUT/ludicrous_wasm_bg.wasm.gz")

printf 'wasm.bytes.raw\t%s\n'        "$RAW"
printf 'wasm.bytes.wasm_opt\t%s\n'   "$FINAL"
printf 'wasm.bytes.gzipped\t%s\n'    "$GZ"
printf 'wasm.js_glue_bytes\t%s\n'    "$(stat -c %s "$OUT/ludicrous_wasm.js")"
