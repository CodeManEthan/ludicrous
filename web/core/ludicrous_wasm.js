// GENERATED FILE -- do not edit.
// Built from core-rs/ by core-rs/build-wasm.sh (wasm-bindgen --target no-modules).
// Rebuild with:  ./core-rs/build-wasm.sh
let wasm_bindgen = (function(exports) {
    let script_src;
    if (typeof document !== 'undefined' && document.currentScript !== null) {
        script_src = new URL(document.currentScript.src, location.href).toString();
    }

    /**
     * One prepared game: everything the UI needs up front, plus the machinery
     * to reconstruct any single round on demand.
     */
    class WarPrepared {
        static __wrap(ptr) {
            const obj = Object.create(WarPrepared.prototype);
            obj.__wbg_ptr = ptr;
            WarPreparedFinalization.register(obj, obj.__wbg_ptr, obj);
            return obj;
        }
        __destroy_into_raw() {
            const ptr = this.__wbg_ptr;
            this.__wbg_ptr = 0;
            WarPreparedFinalization.unregister(this);
            return ptr;
        }
        free() {
            const ptr = this.__destroy_into_raw();
            wasm.__wbg_warprepared_free(ptr, 0);
        }
        /**
         * Sample rounds for the chart, ascending, first is 0 (the deal).
         * @returns {Uint32Array}
         */
        chartRounds() {
            const ret = wasm.warprepared_chartRounds(this.__wbg_ptr);
            var v1 = getArrayU32FromWasm0(ret[0], ret[1]).slice();
            wasm.__wbindgen_free(ret[0], ret[1] * 4, 4);
            return v1;
        }
        /**
         * Card counts at those rounds, player-major, `-1` once a player is out.
         * @returns {Int32Array}
         */
        chartSeries() {
            const ret = wasm.warprepared_chartSeries(this.__wbg_ptr);
            var v1 = getArrayI32FromWasm0(ret[0], ret[1]).slice();
            wasm.__wbindgen_free(ret[0], ret[1] * 4, 4);
            return v1;
        }
        /**
         * @returns {number}
         */
        get checkpointBytes() {
            const ret = wasm.warprepared_checkpointBytes(this.__wbg_ptr);
            return ret >>> 0;
        }
        /**
         * @returns {number}
         */
        get checkpointCount() {
            const ret = wasm.warprepared_checkpointCount(this.__wbg_ptr);
            return ret >>> 0;
        }
        /**
         * @returns {number}
         */
        get checkpointInterval() {
            const ret = wasm.warprepared_checkpointInterval(this.__wbg_ptr);
            return ret >>> 0;
        }
        /**
         * Where the resim cursor currently sits. Exposed for tests that want to
         * prove a sequential step did not restore anything.
         * @returns {number}
         */
        get cursorRound() {
            const ret = wasm.warprepared_cursorRound(this.__wbg_ptr);
            return ret >>> 0;
        }
        /**
         * @returns {Uint32Array}
         */
        elimPlayers() {
            const ret = wasm.warprepared_elimPlayers(this.__wbg_ptr);
            var v1 = getArrayU32FromWasm0(ret[0], ret[1]).slice();
            wasm.__wbindgen_free(ret[0], ret[1] * 4, 4);
            return v1;
        }
        /**
         * @returns {Uint32Array}
         */
        elimRounds() {
            const ret = wasm.warprepared_elimRounds(this.__wbg_ptr);
            var v1 = getArrayU32FromWasm0(ret[0], ret[1]).slice();
            wasm.__wbindgen_free(ret[0], ret[1] * 4, 4);
            return v1;
        }
        /**
         * @returns {Uint32Array}
         */
        initialCounts() {
            const ret = wasm.warprepared_initialCounts(this.__wbg_ptr);
            var v1 = getArrayU32FromWasm0(ret[0], ret[1]).slice();
            wasm.__wbindgen_free(ret[0], ret[1] * 4, 4);
            return v1;
        }
        /**
         * @returns {number}
         */
        get numPlayers() {
            const ret = wasm.warprepared_numPlayers(this.__wbg_ptr);
            return ret >>> 0;
        }
        /**
         * One round, as the JSON the UI renders. Round 0 (the deal) has no
         * round data by construction and returns `null`.
         * @param {number} round
         * @returns {string}
         */
        roundView(round) {
            let deferred2_0;
            let deferred2_1;
            try {
                const ret = wasm.warprepared_roundView(this.__wbg_ptr, round);
                var ptr1 = ret[0];
                var len1 = ret[1];
                if (ret[3]) {
                    ptr1 = 0; len1 = 0;
                    throw takeFromExternrefTable0(ret[2]);
                }
                deferred2_0 = ptr1;
                deferred2_1 = len1;
                return getStringFromWasm0(ptr1, len1);
            } finally {
                wasm.__wbindgen_free(deferred2_0, deferred2_1, 1);
            }
        }
        /**
         * @returns {number}
         */
        get rounds() {
            const ret = wasm.warprepared_rounds(this.__wbg_ptr);
            return ret >>> 0;
        }
        /**
         * @returns {Uint32Array}
         */
        standings() {
            const ret = wasm.warprepared_standings(this.__wbg_ptr);
            var v1 = getArrayU32FromWasm0(ret[0], ret[1]).slice();
            wasm.__wbindgen_free(ret[0], ret[1] * 4, 4);
            return v1;
        }
        /**
         * @returns {string}
         */
        summaryJson() {
            let deferred1_0;
            let deferred1_1;
            try {
                const ret = wasm.warprepared_summaryJson(this.__wbg_ptr);
                deferred1_0 = ret[0];
                deferred1_1 = ret[1];
                return getStringFromWasm0(ret[0], ret[1]);
            } finally {
                wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
            }
        }
    }
    if (Symbol.dispose) WarPrepared.prototype[Symbol.dispose] = WarPrepared.prototype.free;
    exports.WarPrepared = WarPrepared;

    /**
     * A live game that can be checkpointed and rewound. This is the seek API:
     * keep a sparse array of `save()` blobs, then `restore` the nearest one
     * and `advance` the remainder.
     */
    class WarSession {
        static __wrap(ptr) {
            const obj = Object.create(WarSession.prototype);
            obj.__wbg_ptr = ptr;
            WarSessionFinalization.register(obj, obj.__wbg_ptr, obj);
            return obj;
        }
        __destroy_into_raw() {
            const ptr = this.__wbg_ptr;
            this.__wbg_ptr = 0;
            WarSessionFinalization.unregister(this);
            return ptr;
        }
        free() {
            const ptr = this.__destroy_into_raw();
            wasm.__wbg_warsession_free(ptr, 0);
        }
        /**
         * Play up to `k` more rounds. Returns how many actually happened.
         * @param {number} k
         * @returns {number}
         */
        advance(k) {
            const ret = wasm.warsession_advance(this.__wbg_ptr, k);
            return ret >>> 0;
        }
        /**
         * @returns {boolean}
         */
        get isOver() {
            const ret = wasm.warsession_isOver(this.__wbg_ptr);
            return ret !== 0;
        }
        /**
         * @param {number} num_players
         * @param {number} num_decks
         * @param {number} max_rounds
         * @param {number} seed
         */
        constructor(num_players, num_decks, max_rounds, seed) {
            const ret = wasm.warsession_new(num_players, num_decks, max_rounds, seed);
            this.__wbg_ptr = ret;
            WarSessionFinalization.register(this, this.__wbg_ptr, this);
            return this;
        }
        /**
         * Rebuild from a checkpoint blob.
         * @param {Uint8Array} bytes
         * @returns {WarSession}
         */
        static restore(bytes) {
            const ptr0 = passArray8ToWasm0(bytes, wasm.__wbindgen_malloc);
            const len0 = WASM_VECTOR_LEN;
            const ret = wasm.warsession_restore(ptr0, len0);
            if (ret[2]) {
                throw takeFromExternrefTable0(ret[1]);
            }
            return WarSession.__wrap(ret[0]);
        }
        /**
         * @returns {number}
         */
        get round() {
            const ret = wasm.warsession_round(this.__wbg_ptr);
            return ret >>> 0;
        }
        /**
         * Play to the end.
         * @returns {number}
         */
        run() {
            const ret = wasm.warsession_run(this.__wbg_ptr);
            return ret >>> 0;
        }
        /**
         * @returns {Uint8Array}
         */
        save() {
            const ret = wasm.warsession_save(this.__wbg_ptr);
            var v1 = getArrayU8FromWasm0(ret[0], ret[1]).slice();
            wasm.__wbindgen_free(ret[0], ret[1] * 1, 1);
            return v1;
        }
        /**
         * @returns {string}
         */
        summaryJson() {
            let deferred1_0;
            let deferred1_1;
            try {
                const ret = wasm.warsession_summaryJson(this.__wbg_ptr);
                deferred1_0 = ret[0];
                deferred1_1 = ret[1];
                return getStringFromWasm0(ret[0], ret[1]);
            } finally {
                wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
            }
        }
    }
    if (Symbol.dispose) WarSession.prototype[Symbol.dispose] = WarSession.prototype.free;
    exports.WarSession = WarSession;

    /**
     * Batch throughput probe: run `games` games from `seed0` and return the
     * total round count. Exists so a benchmark measures the engine, not the
     * JS/wasm call overhead.
     * @param {number} num_players
     * @param {number} num_decks
     * @param {number} seed0
     * @param {number} games
     * @returns {number}
     */
    function bench_rounds(num_players, num_decks, seed0, games) {
        const ret = wasm.bench_rounds(num_players, num_decks, seed0, games);
        return ret;
    }
    exports.bench_rounds = bench_rounds;

    /**
     * Run a whole game once and keep what playback needs.
     *
     * `checkpoint_interval` is a hint: pass 0 (or a negative) to let the pass
     * pick one, which is almost always what you want -- the round count is not
     * known until the game is over.
     * @param {number} num_players
     * @param {number} num_decks
     * @param {number} seed
     * @param {number} max_rounds
     * @param {number} checkpoint_interval
     * @returns {WarPrepared}
     */
    function prepare(num_players, num_decks, seed, max_rounds, checkpoint_interval) {
        const ret = wasm.prepare(num_players, num_decks, seed, max_rounds, checkpoint_interval);
        if (ret[2]) {
            throw takeFromExternrefTable0(ret[1]);
        }
        return WarPrepared.__wrap(ret[0]);
    }
    exports.prepare = prepare;

    /**
     * Play one game to completion and hand back its summary as JSON.
     * @param {number} num_players
     * @param {number} num_decks
     * @param {number} max_rounds
     * @param {number} seed
     * @returns {string}
     */
    function simulate(num_players, num_decks, max_rounds, seed) {
        let deferred1_0;
        let deferred1_1;
        try {
            const ret = wasm.simulate(num_players, num_decks, max_rounds, seed);
            deferred1_0 = ret[0];
            deferred1_1 = ret[1];
            return getStringFromWasm0(ret[0], ret[1]);
        } finally {
            wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
        }
    }
    exports.simulate = simulate;

    /**
     * Play one game with the event log on, returning NDJSON.
     * @param {number} num_players
     * @param {number} num_decks
     * @param {number} max_rounds
     * @param {number} seed
     * @returns {string}
     */
    function simulate_with_events(num_players, num_decks, max_rounds, seed) {
        let deferred1_0;
        let deferred1_1;
        try {
            const ret = wasm.simulate_with_events(num_players, num_decks, max_rounds, seed);
            deferred1_0 = ret[0];
            deferred1_1 = ret[1];
            return getStringFromWasm0(ret[0], ret[1]);
        } finally {
            wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
        }
    }
    exports.simulate_with_events = simulate_with_events;
    function __wbg_get_imports() {
        const import0 = {
            __proto__: null,
            __wbg_Error_408e67f47ca7b58b: function(arg0, arg1) {
                const ret = Error(getStringFromWasm0(arg0, arg1));
                return ret;
            },
            __wbg___wbindgen_throw_bb96b2010945f0bc: function(arg0, arg1) {
                throw new Error(getStringFromWasm0(arg0, arg1));
            },
            __wbindgen_init_externref_table: function() {
                const table = wasm.__wbindgen_externrefs;
                const offset = table.grow(4);
                table.set(0, undefined);
                table.set(offset + 0, undefined);
                table.set(offset + 1, null);
                table.set(offset + 2, true);
                table.set(offset + 3, false);
            },
        };
        return {
            __proto__: null,
            "./ludicrous_wasm_bg.js": import0,
        };
    }

    const WarPreparedFinalization = (typeof FinalizationRegistry === 'undefined')
        ? { register: () => {}, unregister: () => {} }
        : new FinalizationRegistry(ptr => wasm.__wbg_warprepared_free(ptr, 1));
    const WarSessionFinalization = (typeof FinalizationRegistry === 'undefined')
        ? { register: () => {}, unregister: () => {} }
        : new FinalizationRegistry(ptr => wasm.__wbg_warsession_free(ptr, 1));

    function getArrayI32FromWasm0(ptr, len) {
        ptr = ptr >>> 0;
        return getInt32ArrayMemory0().subarray(ptr / 4, ptr / 4 + len);
    }

    function getArrayU32FromWasm0(ptr, len) {
        ptr = ptr >>> 0;
        return getUint32ArrayMemory0().subarray(ptr / 4, ptr / 4 + len);
    }

    function getArrayU8FromWasm0(ptr, len) {
        ptr = ptr >>> 0;
        return getUint8ArrayMemory0().subarray(ptr / 1, ptr / 1 + len);
    }

    let cachedInt32ArrayMemory0 = null;
    function getInt32ArrayMemory0() {
        if (cachedInt32ArrayMemory0 === null || cachedInt32ArrayMemory0.byteLength === 0) {
            cachedInt32ArrayMemory0 = new Int32Array(wasm.memory.buffer);
        }
        return cachedInt32ArrayMemory0;
    }

    function getStringFromWasm0(ptr, len) {
        return decodeText(ptr >>> 0, len);
    }

    let cachedUint32ArrayMemory0 = null;
    function getUint32ArrayMemory0() {
        if (cachedUint32ArrayMemory0 === null || cachedUint32ArrayMemory0.byteLength === 0) {
            cachedUint32ArrayMemory0 = new Uint32Array(wasm.memory.buffer);
        }
        return cachedUint32ArrayMemory0;
    }

    let cachedUint8ArrayMemory0 = null;
    function getUint8ArrayMemory0() {
        if (cachedUint8ArrayMemory0 === null || cachedUint8ArrayMemory0.byteLength === 0) {
            cachedUint8ArrayMemory0 = new Uint8Array(wasm.memory.buffer);
        }
        return cachedUint8ArrayMemory0;
    }

    function passArray8ToWasm0(arg, malloc) {
        const ptr = malloc(arg.length * 1, 1) >>> 0;
        getUint8ArrayMemory0().set(arg, ptr / 1);
        WASM_VECTOR_LEN = arg.length;
        return ptr;
    }

    function takeFromExternrefTable0(idx) {
        const value = wasm.__wbindgen_externrefs.get(idx);
        wasm.__externref_table_dealloc(idx);
        return value;
    }

    let cachedTextDecoder = new TextDecoder('utf-8', { ignoreBOM: true, fatal: true });
    cachedTextDecoder.decode();
    function decodeText(ptr, len) {
        return cachedTextDecoder.decode(getUint8ArrayMemory0().subarray(ptr, ptr + len));
    }

    let WASM_VECTOR_LEN = 0;

    let wasmModule, wasmInstance, wasm;
    function __wbg_finalize_init(instance, module) {
        wasmInstance = instance;
        wasm = instance.exports;
        wasmModule = module;
        cachedInt32ArrayMemory0 = null;
        cachedUint32ArrayMemory0 = null;
        cachedUint8ArrayMemory0 = null;
        wasm.__wbindgen_start();
        return wasm;
    }

    async function __wbg_load(module, imports) {
        if (typeof Response === 'function' && module instanceof Response) {
            if (!module.ok) {
                throw new Error(`failed to fetch Wasm: ${module.status} ${module.statusText} fetching '${module.url}'`);
            }

            if (typeof WebAssembly.instantiateStreaming === 'function') {
                try {
                    return await WebAssembly.instantiateStreaming(module, imports);
                } catch (e) {
                    const validResponse = expectedResponseType(module.type);

                    if (validResponse && module.headers.get('Content-Type') !== 'application/wasm') {
                        console.warn("`WebAssembly.instantiateStreaming` failed because your server does not serve Wasm with `application/wasm` MIME type. Falling back to `WebAssembly.instantiate` which is slower. Original error:\n", e);

                    } else { throw e; }
                }
            }

            const bytes = await module.arrayBuffer();
            return await WebAssembly.instantiate(bytes, imports);
        } else {
            const instance = await WebAssembly.instantiate(module, imports);

            if (instance instanceof WebAssembly.Instance) {
                return { instance, module };
            } else {
                return instance;
            }
        }

        function expectedResponseType(type) {
            switch (type) {
                case 'basic': case 'cors': case 'default': return true;
            }
            return false;
        }
    }

    function initSync(module) {
        if (wasm !== undefined) return wasm;


        if (module !== undefined) {
            if (Object.getPrototypeOf(module) === Object.prototype) {
                ({module} = module)
            } else {
                console.warn('using deprecated parameters for `initSync()`; pass a single object instead')
            }
        }

        const imports = __wbg_get_imports();
        if (!(module instanceof WebAssembly.Module)) {
            module = new WebAssembly.Module(module);
        }
        const instance = new WebAssembly.Instance(module, imports);
        return __wbg_finalize_init(instance, module);
    }

    async function __wbg_init(module_or_path) {
        if (wasm !== undefined) return wasm;


        if (module_or_path !== undefined) {
            if (Object.getPrototypeOf(module_or_path) === Object.prototype) {
                ({module_or_path} = module_or_path)
            } else {
                console.warn('using deprecated parameters for the initialization function; pass a single object instead')
            }
        }

        if (module_or_path === undefined && script_src !== undefined) {
            module_or_path = script_src.replace(/\.js$/, "_bg.wasm");
        }
        const imports = __wbg_get_imports();

        if (typeof module_or_path === 'string' || (typeof Request === 'function' && module_or_path instanceof Request) || (typeof URL === 'function' && module_or_path instanceof URL)) {
            module_or_path = fetch(module_or_path);
        }

        const { instance, module } = await __wbg_load(await module_or_path, imports);

        return __wbg_finalize_init(instance, module);
    }

    return Object.assign(__wbg_init, { initSync }, exports);
})({ __proto__: null });
