import test from "node:test";
import assert from "node:assert/strict";
import { checkAndRecover, decideRecovery } from "./worker.mjs";

const hour = 60 * 60 * 1000;
const now = Date.parse("2026-11-10T10:00:00Z");
const previous = (hours, overrides = {}) => ({
  head_branch: "main",
  status: "completed",
  conclusion: "success",
  event: "schedule",
  created_at: new Date(now - hours * hour).toISOString(),
  updated_at: new Date(now - hours * hour).toISOString(),
  ...overrides,
});

test("recent success is healthy and no recovery is attempted", () => {
  const decision = decideRecovery([previous(1)], now);
  assert.equal(decision.state, "healthy");
  assert.equal(decision.dispatch, false);
  assert.equal(decision.age_minutes, 60);
});

test("stale refresh is actionable only without newer attempts", () => {
  assert.deepEqual(
    decideRecovery([previous(4), previous(0.5, { conclusion: "failure" })], now).reason,
    "cooldown",
  );
  assert.equal(decideRecovery([previous(4)], now).dispatch, true);
  assert.equal(
    decideRecovery([
      previous(4),
      previous(2, { conclusion: null, status: "in_progress" }),
    ], now).reason,
    "already_running",
  );
});

test("recovery budget, branch boundaries and future timestamps fail closed", () => {
  assert.equal(
    decideRecovery([
      previous(7),
      previous(4, { event: "workflow_dispatch" }),
      previous(2, { event: "workflow_dispatch", conclusion: "failure" }),
    ], now).reason,
    "daily_budget_exhausted",
  );
  assert.equal(
    decideRecovery([previous(4, { head_branch: "feature" })], now).dispatch,
    true,
  );
  assert.equal(
    decideRecovery([previous(-1)], now).dispatch,
    true,
  );
});

test("no authorization means read-only observation, not dispatch", async () => {
  let posts = 0;
  const fakeFetch = async (_url, request) => {
    if (request.method === "POST") posts++;
    return { ok: true, status: 200, json: async () => ({ workflow_runs: [previous(4)] }) };
  };
  const result = await checkAndRecover({}, now, fakeFetch);
  assert.equal(result.reason, "recovery_not_approved");
  assert.equal(posts, 0);
});

test("only separately approved, token-backed recovery may dispatch", async () => {
  let posts = 0;
  const fakeFetch = async (url, request) => {
    if (url.endsWith("/dispatches")) {
      posts++;
      assert.equal(request.method, "POST");
      assert.match(request.headers.Authorization, /^Bearer /);
      assert.equal(JSON.parse(request.body).inputs.recovery_attempt, "1");
      return { ok: true, status: 204 };
    }
    return { ok: true, status: 200, json: async () => ({ workflow_runs: [previous(4)] }) };
  };
  const result = await checkAndRecover({
    GITHUB_DISPATCH_TOKEN: "test-secret",
    RECOVERY_ENABLED: "true",
    YAHOO_COLLECTION_APPROVED: "true",
  }, now, fakeFetch);
  assert.equal(result.reason, "recovery_dispatched");
  assert.equal(posts, 1);
});

test("API failure is never silently interpreted as healthy", async () => {
  const badFetch = async () => ({ ok: false, status: 403 });
  await assert.rejects(checkAndRecover({}, now, badFetch), /HTTP 403/);
});
