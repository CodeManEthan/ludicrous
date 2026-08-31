---
name: railway-deploy
description: Deploy the current Ludicrous working tree to Railway (the live site at ludicrous-production-6bdb.up.railway.app). Use when asked to deploy, ship, push live, update the deployment, or release the current version — also for checking deploy status, tailing production logs, or diagnosing a failed deploy.
---

# Deploy Ludicrous to Railway

The live site is **https://ludicrous-production-6bdb.up.railway.app** — Railway project
`ludicrous` (id `6c03ffcd-26b7-4a5c-8307-dd6cecac7f98`), service `ludicrous`
(id `d65e923d-f9d7-4a26-86e0-8b09a023bb19`), environment `production`. It builds from the
repo's `Dockerfile` (python:3.12-slim + the source tree; no dependencies to install).

The CLI lives at `~/.npm-global/bin/railway` and is not on the default PATH. Auth and the
project link are already configured on this machine (in `~/.railway/config.json`, linked by
cwd), but **no service is linked** — always pass `--service ludicrous`.

## Deploy (the one step)

From the repo root:

```bash
export PATH="$HOME/.npm-global/bin:$PATH"
cd /home/jpluto/projects/ludicrous
railway up --service ludicrous --ci
```

`--ci` makes it non-interactive: it uploads, streams the build logs, and exits when the
deploy is live (or fails). Expect a few minutes end to end. Give the Bash call a generous
timeout (600000 ms).

Two things to know before you run it:

- **It ships the working tree, not git HEAD.** Uncommitted changes go live. That's usually
  the point ("push the current version live"), but say so in your report, and don't deploy a
  tree with half-finished work in it.
- Upload skips anything in `.gitignore` (so `venv/`, `core-rs/target/`, `.claude/` stay
  home). The wasm build the frontend needs is the *committed* `web/core/` pair
  (`ludicrous_wasm.js` + `ludicrous_wasm_bg.wasm`) — if you changed `core-rs/`, rebuild with
  `core-rs/build-wasm.sh` first so `web/core/` is current, or the site serves the old engine.

## Verify

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://ludicrous-production-6bdb.up.railway.app/
curl -sS -X POST https://ludicrous-production-6bdb.up.railway.app/api/simulate \
  -H 'Content-Type: application/json' \
  -d '{"players": 4, "decks": 1, "seed": 1}' | head -c 200
```

Expect `200` and a JSON body starting with game data (not an error). If you shipped a UI
change, spot-check the page itself (playwright-cli with a unique `-s=` session).

## Status, logs, rollback

```bash
railway status                              # what's linked, what's running
railway logs --service ludicrous            # runtime logs (Ctrl-C to stop; use timeout)
railway logs --service ludicrous --build    # last build's logs
railway redeploy --service ludicrous --yes  # re-run the current deployment
railway down --service ludicrous --yes      # take the service down (don't, unless asked)
```

There is no one-command rollback to an older image; to roll back, check out the good
commit and `railway up` again (or use the Railway dashboard's deployment history).

## If it fails

- `Unauthorized` / login prompt: auth expired — the operator must run `railway login`
  (browser flow). Say so and stop; don't try to script the login.
- `No service linked`: you forgot `--service ludicrous`.
- Build failures: the Dockerfile is trivial, so failures are almost always a bad
  `server.py` (syntax) or a Railway-side hiccup — read the build log it streamed,
  fix, re-run.
