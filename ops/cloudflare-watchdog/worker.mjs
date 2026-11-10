// Independent Cloudflare Cron watchdog. Never treat missing evidence as success.
const REPO = "KAFKA2306/cast_event_cal";
const WORKFLOW = "update-calendar-v2.yml";
const SNAPSHOT_URL = "https://kafka2306.github.io/cast_event_cal/snapshot.json";
const MAX_AGE = 180;
const COOLDOWN = 90;
const MAX_DISPATCHES_24H = 2;

function instant(raw) {
  if (typeof raw !== "string" || !/(Z|[+-]\d{2}:\d{2})$/.test(raw)) return null;
  const value = Date.parse(raw);
  return Number.isFinite(value) ? value : null;
}

export function assess({runs, snapshot, now = Date.now()}) {
  const unknown = (reason) => ({state: "unknown", reason, dispatch: false});
  if (!Array.isArray(runs) || runs.length === 0) return unknown("updater_runs_unavailable");
  if (!snapshot || typeof snapshot !== "object" || !(snapshot.event_count > 0)) {
    return unknown("public_snapshot_invalid");
  }
  const snapshotAt = instant(snapshot.generated_at);
  if (snapshotAt === null || snapshotAt > now) return unknown("public_snapshot_time_invalid");
  const snapshotAge = Math.floor((now - snapshotAt) / 60000);
  if (runs.some(r => !r || typeof r !== "object" || r.head_branch !== "main" ||
      instant(r.created_at) === null || instant(r.created_at) > now)) {
    return unknown("updater_run_metadata_invalid");
  }
  const chronological = [...runs].sort((a, b) => instant(b.created_at) - instant(a.created_at));
  if (chronological.length >= 100 && now - instant(chronological[99].created_at) < 86400000) {
    return unknown("run_history_incomplete_for_daily_budget");
  }
  const successes = chronological.filter(r => r.conclusion === "success" && r.status === "completed" &&
    instant(r.updated_at) !== null && instant(r.updated_at) <= now);
  if (successes.length === 0) return unknown("no_observed_success");
  const lastSuccess = successes.reduce((best, r) => Math.max(best, instant(r.updated_at)), 0);
  const runAge = Math.floor((now - lastSuccess) / 60000);
  const recent = chronological.filter(r => now - instant(r.created_at) <= 86400000);
  const attempts = recent.filter(r => r.event === "workflow_dispatch").length;
  const base = {
    checked_at: new Date(now).toISOString(),
    latest_success_at: new Date(lastSuccess).toISOString(),
    snapshot_at: new Date(snapshotAt).toISOString(),
    run_age_minutes: runAge,
    snapshot_age_minutes: snapshotAge,
    dispatches_last_24h: attempts,
    dispatch: false,
  };
  if (runAge <= MAX_AGE && snapshotAge <= MAX_AGE) {
    return {...base, state: "healthy", reason: "both_fresh"};
  }
  if (chronological.some(r => r.status !== "completed")) {
    return {...base, state: "late", reason: "updater_active_or_status_unknown"};
  }
  if (recent.some(r => now - instant(r.created_at) < COOLDOWN * 60000)) {
    return {...base, state: "late", reason: "recovery_cooldown"};
  }
  if (attempts >= MAX_DISPATCHES_24H) {
    return {...base, state: "late", reason: "daily_dispatch_budget_exhausted"};
  }
  return {...base, state: "late", reason: "bounded_dispatch_allowed", dispatch: true};
}

async function jsonGet(url, token, fetcher) {
  const headers = {"Accept": "application/vnd.github+json", "Cache-Control": "no-cache"};
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetcher(url, {headers, signal: AbortSignal.timeout(15000)});
  if (!response.ok) throw new Error(`read_error_${response.status}`);
  return response.json();
}

export async function monitor(env, fetcher = fetch, now = Date.now()) {
  const token = env.GITHUB_WATCHDOG_TOKEN;
  let result;
  try {
    const [runsPayload, snapshot] = await Promise.all([
      jsonGet(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/runs?branch=main&per_page=100`, token, fetcher),
      jsonGet(SNAPSHOT_URL, null, fetcher),
    ]);
    result = assess({runs: runsPayload.workflow_runs, snapshot, now});
    if (result.dispatch) {
      if (!token) {
        result = {...result, state: "unknown", reason: "dispatch_token_not_configured", dispatch: false};
      } else {
        const response = await fetcher(
          `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
          {method: "POST", headers: {
            "Accept": "application/vnd.github+json", "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28"
          }, body: JSON.stringify({ref: "main", inputs: {recovery_attempt: "1"}}),
          signal: AbortSignal.timeout(15000)}
        );
        if (response.status !== 204) {
          throw new Error(`dispatch_http_${response.status}`);
        }
        result = {...result, state: "recovery_requested", reason: "workflow_dispatch_accepted"};
      }
    }
  } catch (e) {
    result = {checked_at: new Date(now).toISOString(), state: "unknown",
              reason: String(e?.message || "monitor_failed"), dispatch: false};
  }
  // Cloudflare Workers Logs are the machine-readable independent tick journal.
  console.log(JSON.stringify({component: "independent-updater-watchdog", ...result}));
  return result;
}

export default {
  async fetch(request, env) {
    // Keep the existing static asset delivery behavior.
    return env.ASSETS.fetch(request);
  },
  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(monitor(env));
  },
};
