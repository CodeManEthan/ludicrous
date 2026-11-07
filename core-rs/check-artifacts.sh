#!/usr/bin/env bash
# Rebuild the three committed artifacts from source and fail unless they come
# out byte for byte the same as the checked-out copies:
#
#   web/core/ludicrous_wasm_bg.wasm, web/core/ludicrous_wasm.js  (build-wasm.sh)
#   bin/lud-batch                                                (build-native.sh)
#
# CI runs this as the "artifacts" job; run it locally the same way. It needs
# rustup, cargo and a C linker (cc) on the machine, and installs what else is
# missing: the pinned rustc with both targets (through rustup, only when the
# active rustc is not already the pinned one) and the pinned wasm-bindgen-cli
# (cargo install --locked). The pins are in pinned-env.sh. Rebuilt files are
# left in the tree, so after a failure `git diff --stat` shows what moved.
set -euo pipefail
cd "$(dirname "$0")"
source ./pinned-env.sh

if ! have_pinned_rustc; then
  rustup toolchain install "$PINNED_RUSTC" --profile minimal \
    --target "$(IFS=,; echo "${PINNED_TARGETS[*]}")"
  export RUSTUP_TOOLCHAIN=$PINNED_RUSTC
fi
require_pinned_rustc
rustc --version

if ! have_pinned_wasm_bindgen; then
  cargo install wasm-bindgen-cli --version "$PINNED_WASM_BINDGEN" --locked
fi
require_pinned_wasm_bindgen
wasm-bindgen --version

FILES=(
  ../web/core/ludicrous_wasm_bg.wasm
  ../web/core/ludicrous_wasm.js
  ../bin/lud-batch
)
before=$(mktemp -d)
trap 'rm -rf "$before"' EXIT
for f in "${FILES[@]}"; do
  cp "$f" "$before/$(basename "$f")"
done

./build-wasm.sh
./build-native.sh

status=0
for f in "${FILES[@]}"; do
  name=$(basename "$f")
  if cmp -s "$before/$name" "$f"; then
    echo "same     $(sha256sum "$f" | cut -d' ' -f1)  ${f#../}"
  else
    echo "DIFFERS  ${f#../}: committed $(sha256sum "$before/$name" | cut -d' ' -f1)," \
      "rebuilt $(sha256sum "$f" | cut -d' ' -f1)"
    status=1
  fi
done
if [ "$status" -ne 0 ]; then
  echo "The committed artifacts do not match the source. Rebuild them with" >&2
  echo "core-rs/build-wasm.sh and core-rs/build-native.sh and commit the result." >&2
fi
exit "$status"
