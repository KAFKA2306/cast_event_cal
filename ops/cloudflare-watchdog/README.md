# Independent calendar watchdog (Issue #406)

**Authoritative deployment:** existing Cloudflare Worker `cast-event-cal`, configured by the repository-root `wrangler.jsonc`. No second Worker deployment is required or recommended. The standalone `wrangler.toml` is retired to prevent duplicate schedulers.

Cloudflare Cron Trigger runs at **53 minutes past each hour (UTC)**, independently of GitHub Actions. `ops/cloudflare-watchdog/worker.mjs` keeps normal site requests intact through `env.ASSETS.fetch(request)`.

Every tick verifies:
- Main updater last successful completion via GitHub Actions API
- Published `https://kafka2306.github.io/cast_event_cal/snapshot.json` generation time and event count
- Both must be fresher than 180 minutes to be healthy

Recovery is bounded: suppress if any update is active or unknown, if any run occurred in the past 90 minutes, if >=2 workflow_dispatch runs occurred in past 24 hours, or if run history cannot establish the day budget. Missing/invalid timestamps, unknown API state, and invalid public snapshots cannot authorize recovery.

If a qualified outage occurs, `GITHUB_WATCHDOG_TOKEN` must be configured as a **Cloudflare Secret** (fine-grained GitHub token scoped to this repo with Actions read/write); without it the Worker monitors but never sends a dispatch. Do not commit the token. No `YAHOO_COLLECTION_APPROVED` flag is needed: Yahoo network collection is independently stopped by the fail-closed permission gate from #405. The watchdog merely requests the normal authorized-source-only production updater.

Machine-readable JSON audit is written to Cloudflare Workers Logs on each tick, including ages, last success/snapshot times and last-day manual dispatch count. Run deterministic tests with:

```sh
node --test ops/cloudflare-watchdog/worker.test.mjs
```

**Not yet independently verified:** actual Cron activation, two separate scheduled ticks, Cloudflare secret, and a safe live recovery and publication read-back. Keep #406 open until evidence exists.

Documentation:
- https://developers.cloudflare.com/workers/configuration/cron-triggers/
- https://developers.cloudflare.com/workers/static-assets/binding/
- https://github.com/KAFKA2306/cast_event_cal/issues/405
- https://github.com/KAFKA2306/cast_event_cal/issues/406
