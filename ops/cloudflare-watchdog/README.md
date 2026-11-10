# Independent calendar watchdog

This is an **external, separate failure-domain** watchdog for `KAFKA2306/cast_event_cal`.
The GitHub updater runs near :17 UTC, and GitHub's in-repository watcher runs near :47 UTC.
This Worker runs at :08 UTC, queries GitHub's workflow runs API, and checks the last
**completed success** against a 180-minute budget, independently of GitHub schedule.

### Activation

The repository file alone **does not install or start** a Cloudflare Worker.
Deploy from this directory with Cloudflare's official Wrangler command after
verifying the target Cloudflare account and the exact code.

The default is **monitor-only**. It uses GitHub's public API without a token.
Logs contain only state/age/reason. If the GitHub API fails, the invocation fails,
rather than reporting a false OK.

Recovery is intentionally disabled until BOTH conditions have been verified:
1. Yahoo real-time search automated access and derived reuse are explicitly
   approved by the service provider, or the production collector has been changed
   to an authorized source (see issue #405).
2. A fine-grained GitHub token restricted to this repository with **Actions
   read/write** is stored as a Cloudflare Worker secret `GITHUB_DISPATCH_TOKEN`
   (never commit a token). Set `YAHOO_COLLECTION_APPROVED=true` and
   `RECOVERY_ENABLED=true` only after that verification.

No privileged token is needed for read-only monitoring.

```sh
cd ops/cloudflare-watchdog
node --test worker.test.mjs
# Use an authorized Cloudflare account:
npx wrangler deploy
# Only after access rights verified:
npx wrangler secret put GITHUB_DISPATCH_TOKEN
```

`wrangler.toml` provides an hourly Cron Trigger. This integration does not
replace GitHub's existing scheduler or modify source records. The Worker
observes the same workflow and bound retries to 2 dispatches per 24h, with
a 90-minute cooldown and active-run guard. It does not perform publication
or rollback itself. `workflow_dispatch` uses `recovery_attempt=1` to
avoid re-dispatch loops.

**Not yet verified:** Cloudflare deployment, secret provisioning, two
independent scheduled ticks, and authorized Yahoo ingestion. Until then,
this is tested deployable code, *not* a claim of complete unattended operation.

References:
- https://developers.cloudflare.com/workers/configuration/cron-triggers/
- https://docs.github.com/en/actions/how-tos/troubleshoot-workflows
- https://github.com/KAFKA2306/cast_event_cal/issues/405
- https://github.com/KAFKA2306/cast_event_cal/issues/406
