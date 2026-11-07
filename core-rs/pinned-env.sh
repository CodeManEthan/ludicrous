# Sourced by build-wasm.sh, build-native.sh and check-artifacts.sh. Not meant
# to run on its own.
#
# The committed artifacts (web/core/ludicrous_wasm_bg.wasm,
# web/core/ludicrous_wasm.js, bin/lud-batch) must be a function of the source
# and these pinned tools only, so check-artifacts.sh can rebuild them anywhere
# and get the same bytes:
#
#   rustc 1.98.0 with the wasm32-unknown-unknown and x86_64-unknown-linux-musl
#   targets, and wasm-bindgen-cli 0.2.127 (cargo install --locked).
#
# The only host tool left in the build is the system linker (cc) that rustc
# drives for the musl binary.
#
# The pin lives here rather than in a rust-toolchain.toml so that
# `cargo test` keeps running on whatever stable is current: the tests should
# catch a newer compiler breaking the code, and opening core-rs/ should not
# make rustup download an old toolchain. Run the build scripts with
# RUSTUP_TOOLCHAIN=1.98.0 when your default toolchain is something else.

PINNED_RUSTC=1.98.0
PINNED_WASM_BINDGEN=0.2.127
PINNED_TARGETS=(wasm32-unknown-unknown x86_64-unknown-linux-musl)

CARGO_DIR=${CARGO_HOME:-$HOME/.cargo}
REPO_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export PATH="$CARGO_DIR/bin:$PATH"

# True when the active rustc is the pinned one and has both targets.
have_pinned_rustc() {
  command -v rustc >/dev/null 2>&1 || return 1
  case "$(rustc --version)" in
    "rustc $PINNED_RUSTC "*) ;;
    *) return 1 ;;
  esac
  local sysroot t
  sysroot=$(rustc --print sysroot)
  for t in "${PINNED_TARGETS[@]}"; do
    [ -d "$sysroot/lib/rustlib/$t" ] || return 1
  done
}

have_pinned_wasm_bindgen() {
  [ "$(wasm-bindgen --version 2>/dev/null || true)" = "wasm-bindgen $PINNED_WASM_BINDGEN" ]
}

require_pinned_rustc() {
  if ! have_pinned_rustc; then
    echo "error: the artifacts are built with rustc $PINNED_RUSTC and the targets" \
      "${PINNED_TARGETS[*]}; found: $(rustc --version 2>/dev/null || echo 'no rustc')" >&2
    echo "  rustup toolchain install $PINNED_RUSTC --profile minimal \\" >&2
    echo "    --target $(IFS=,; echo "${PINNED_TARGETS[*]}")" >&2
    echo "  then rerun with RUSTUP_TOOLCHAIN=$PINNED_RUSTC" >&2
    exit 1
  fi
}

require_pinned_wasm_bindgen() {
  if ! have_pinned_wasm_bindgen; then
    echo "error: need wasm-bindgen $PINNED_WASM_BINDGEN, found:" \
      "$(wasm-bindgen --version 2>/dev/null || echo none)" >&2
    echo "  cargo install wasm-bindgen-cli --version $PINNED_WASM_BINDGEN --locked" >&2
    exit 1
  fi
}

# Keep host paths out of the output: source paths of the cargo registry and of
# the repo end up in panic locations, so map both to fixed names. Passed as
# CARGO_ENCODED_RUSTFLAGS, which overrides RUSTFLAGS and any rustflags in a
# cargo config on the host, so nothing ambient reaches the compiler. Callers
# set RUSTFLAGS_EXTRA (one flag per array element) before calling
# pinned_cargo.
RUSTFLAGS_PINNED=(
  "--remap-path-prefix=$CARGO_DIR=/cargo"
  "--remap-path-prefix=$REPO_DIR=/ludicrous"
)
RUSTFLAGS_EXTRA=()

pinned_cargo() {
  local all=("${RUSTFLAGS_PINNED[@]}" "${RUSTFLAGS_EXTRA[@]}")
  local flags
  flags=$(IFS=$'\x1f'; printf '%s' "${all[*]}")
  CARGO_ENCODED_RUSTFLAGS=$flags cargo "$@"
}
