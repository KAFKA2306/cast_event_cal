import test from "node:test";
import assert from "node:assert/strict";
import {assess, monitor} from "./worker.mjs";

const NOW = Date.parse("2026-11-10T12:00:00Z");
const at = (minutesAgo) => new Date(NOW - minutesAgo * 60000).toISOString();
const run = (minutesAgo, extras = {}) => ({
  created_at: at(minutesAgo), updated_at: at(minutesAgo), head_branch: "main",
  status: "completed", conclusion: "success", event: "schedule", ...extras
});
const snapshot = (minutesAgo) => ({event_count: 100, generated_at: at(minutesAgo)});

test("recent run and snapshot are both required", () => {
  assert.equal(assess({runs: [run(30)], snapshot: snapshot(40), now: NOW}).state, "healthy");
  assert.equal(assess({runs: [run(30)], snapshot: snapshot(210), now: NOW}).dispatch, false);
});

test("stale run and snapshot without an active attempt allows one recovery", () => {
  const d = assess({runs: [run(220)], snapshot: snapshot(220), now: NOW});
  assert.equal(d.dispatch, true);
  assert.equal(d.run_age_minutes, 220);
});

test("unknown and future data cannot authorize dispatch", () => {
  assert.equal(assess({runs: [], snapshot: snapshot(220), now: NOW}).state, "unknown");
  assert.equal(assess({runs: [run(220)], snapshot: snapshot(-1), now: NOW}).state, "unknown");
  assert.equal(assess({runs: [run(220, {created_at: "garbage"})], snapshot: snapshot(220), now: NOW}).state, "unknown");
  assert.equal(assess({runs: [run(220, {created_at: "2026-11-10T08:20:00"})], snapshot: snapshot(220), now: NOW}).state, "unknown");
});

test("active updater and cooldown suppress dispatch", () => {
  assert.equal(assess({runs: [run(215, {status:"in_progress", conclusion:null}), run(240)], snapshot: snapshot(220), now: NOW}).dispatch, false);
  assert.equal(assess({runs: [run(25, {event:"workflow_dispatch", conclusion:"failure"}), run(240)], snapshot: snapshot(220), now: NOW}).reason, "recovery_cooldown");
});

test("two dispatches in 24 hours exhaust recovery budget", () => {
  const d = assess({runs: [run(110, {event:"workflow_dispatch", conclusion:"failure"}), run(240, {event:"workflow_dispatch", conclusion:"failure"}), run(300)], snapshot: snapshot(220), now: NOW});
  assert.equal(d.reason, "daily_dispatch_budget_exhausted");
  assert.equal(d.dispatch, false);
});

test("overfull GitHub response is unknown rather than undercounted", () => {
  const runs = Array.from({length: 100}, (_, i) => run(200 + i));
  assert.equal(assess({runs, snapshot: snapshot(230), now: NOW}).reason, "run_history_incomplete_for_daily_budget");
});

test("missing token observes but does not dispatch", async () => {
  const fake = async (url) => ({ok:true, json: async () => url.includes("/actions/") ? {workflow_runs: [run(220)]} : snapshot(220)});
  const original = console.log;
  console.log = () => {};
  try {
    const result = await monitor({}, fake, NOW);
    assert.equal(result.reason, "dispatch_token_not_configured");
    assert.equal(result.dispatch, false);
  } finally { console.log = original; }
});

test("successful dispatch accepts only GitHub 204", async () => {
  let posts = 0;
  const fake = async (url, options={}) => {
    if (options.method === "POST") { posts++; return {status:204}; }
    return {ok:true, json: async () => url.includes("/actions/") ? {workflow_runs: [run(220)]} : snapshot(220)};
  };
  const original = console.log;
  console.log = () => {};
  try {
    const result = await monitor({GITHUB_WATCHDOG_TOKEN:"test-token"}, fake, NOW);
    assert.equal(result.state, "recovery_requested");
    assert.equal(posts, 1);
  } finally { console.log = original; }
});
