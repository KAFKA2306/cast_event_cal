const API = "https://api.github.com/repos/KAFKA2306/cast_event_cal/actions/workflows/update-calendar-v2.yml";
const STALE_MS = 3 * 60 * 60 * 1000;
const COOLDOWN_MS = 90 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

function timestamp(value) {
  const millis = Date.parse(value || "");
  return Number.isFinite(millis) ? millis : null;
}

export function decideRecovery(runs, nowMs) {
  if (!Array.isArray(runs)) throw new TypeError("workflow_runs must be an array");
  if (!Number.isFinite(nowMs)) throw new TypeError("nowMs must be numeric");
  const mainRuns = runs.filter((run) => run.head_branch === "main");
  const successes = mainRuns
    .filter((run) => run.conclusion === "success")
    .map((run) => timestamp(run.updated_at || run.created_at))
    .filter((time) => time !== null && time <= nowMs);
  const latestSuccess = successes.length ? Math.max(...successes) : null;
  const ageMinutes = latestSuccess === null ? null : Math.floor((nowMs - latestSuccess) / 60000);
  if (latestSuccess !== null && nowMs - latestSuccess <= STALE_MS) {
    return { state: "healthy", dispatch: false, age_minutes: ageMinutes };
  }

  const recent = mainRuns
    .map((run) => ({ run, created: timestamp(run.created_at) }))
    .filter(({ created }) => created !== null && created <= nowMs);
  if (recent.some(({ created }) => nowMs - created <= COOLDOWN_MS)) {
    return { state: "stale", dispatch: false, reason: "cooldown", age_minutes: ageMinutes };
  }
  if (recent.some(({ run, created }) =>
    nowMs - created <= STALE_MS &&
    ["queued", "in_progress", "waiting", "pending", "requested"].includes(run.status)
  )) {
    return { state: "stale", dispatch: false, reason: "already_running", age_minutes: ageMinutes };
  }
  const recoveries = recent.filter(({ run, created }) =>
    run.event === "workflow_dispatch" && nowMs - created <= DAY_MS
  ).length;
  if (recoveries >= 2) {
    return { state: "stale", dispatch: false, reason: "daily_budget_exhausted", age_minutes: ageMinutes };
  }
  return { state: "stale", dispatch: true, reason: "refresh_required", age_minutes: ageMinutes };
}

export async function checkAndRecover(env, nowMs = Date.now(), fetcher = fetch) {
  const token = env.GITHUB_DISPATCH_TOKEN;
  const headers = {
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "cast-event-cal-external-watchdog",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  const response = await fetcher(`${API}/runs?branch=main&per_page=50`, { headers });
  if (!response.ok) throw new Error(`GitHub runs API failed: HTTP ${response.status}`);
  const body = await response.json();
  const decision = decideRecovery(body.workflow_runs, nowMs);
  if (!decision.dispatch) return decision;
  if (env.RECOVERY_ENABLED !== "true" || env.YAHOO_COLLECTION_APPROVED !== "true") {
    return { ...decision, dispatch: false, reason: "recovery_not_approved" };
  }
  if (!token) return { ...decision, dispatch: false, reason: "token_not_configured" };

  const dispatch = await fetcher(`${API}/dispatches`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify({ ref: "main", inputs: { recovery_attempt: "1" } }),
  });
  if (![200, 202, 204].includes(dispatch.status)) {
    throw new Error(`GitHub workflow dispatch failed: HTTP ${dispatch.status}`);
  }
  return { ...decision, dispatch: true, reason: "recovery_dispatched" };
}

export default {
  async scheduled(_event, env) {
    const result = await checkAndRecover(env);
    // Logs contain only state, age and action, never a credential or post body.
    console.log(JSON.stringify(result));
  },
};
