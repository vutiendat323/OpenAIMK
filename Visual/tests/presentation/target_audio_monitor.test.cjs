// Run with node --test tests/presentation/target_audio_monitor.test.cjs.
// Reuse the workspace frontend's existing jsdom; no console package is needed.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { createRequire } = require("node:module");
const path = require("node:path");
const workspace = path.resolve(__dirname, "../../..");
const { JSDOM } = createRequire(path.join(workspace, "OpenJarvis/frontend/package.json"))("jsdom");
const consoleRoot = path.join(workspace, "vision/presentation/console");

function consolePage(t) {
  const dom = new JSDOM(readFileSync(path.join(consoleRoot, "index.html"), "utf8"), {
    url: "http://localhost:9876", runScripts: "outside-only",
  });
  t.after(() => dom.window.close());
  const win = dom.window;
  win.HTMLCanvasElement.prototype.getContext = () => new Proxy({}, {
    get: () => () => {}, set: () => true,
  });
  win.Audio = win.AudioContext = function () { throw new Error("Browser must not play PCM"); };
  const sent = [];
  win.MissionVision = { send: (command) => { sent.push(command); return true; } };
  win.eval(readFileSync(path.join(consoleRoot, "js/i18n.js"), "utf8"));
  win.eval(readFileSync(path.join(consoleRoot, "js/mission.js"), "utf8"));
  const message = (data) => win.dispatchEvent(new win.CustomEvent("vision:message", { detail: data }));
  const connected = (value) => win.dispatchEvent(new win.CustomEvent("vision:connection", { detail: value }));
  const toggle = win.document.getElementById("target-audio-toggle");
  assert.ok(toggle, "operator must have a local playback toggle");
  return { win, sent, message, connected, toggle };
}

function telemetry(enabled = false, session = "s1", status = enabled ? "playing" : "off") {
  const now = Date.now() / 1000;
  return { event: "monitor", ts: now, tracks: [], voice: {
    status: "live", session_id: session, data: {
      ts: now, verdict: "ACCEPT", verdict_ts: now, locked: true,
      settings: {}, bounds: {}, evidence: {},
      target_audio_monitor: { enabled, status, error: status === "error" ? "no audio device" : null },
    },
  } };
}

test("toggle is unavailable without an active voice session", (t) => {
  const page = consolePage(t);
  page.connected(true);
  assert.equal(page.toggle.disabled, true);
  page.toggle.click();
  assert.deepEqual(page.sent, []);
});

test("toggle sends only a boolean control and follows backend telemetry", (t) => {
  const page = consolePage(t);
  page.connected(true);
  page.message(telemetry());
  assert.equal(page.toggle.disabled, false);
  page.toggle.click();
  assert.deepEqual(JSON.parse(JSON.stringify(page.sent)), [
    { cmd: "voice_set", key: "target_audio_monitor", value: true },
  ]);
  assert.equal(page.toggle.getAttribute("aria-checked"), "false");
  assert.equal(page.toggle.disabled, true);
  page.message({ event: "voice_set_result", key: "target_audio_monitor", ok: true, value: true });
  page.message(telemetry(true));
  assert.equal(page.toggle.getAttribute("aria-checked"), "true");
  page.toggle.click();
  assert.equal(page.sent[1].value, false);
  page.message({ event: "voice_set_result", key: "target_audio_monitor", ok: true, value: false });
  page.message(telemetry(false));
  assert.equal(page.toggle.getAttribute("aria-checked"), "false");
});

test("device errors and rejected commands restore a usable toggle", (t) => {
  const page = consolePage(t);
  page.connected(true);
  page.message(telemetry());
  page.toggle.click();
  page.message({ event: "voice_set_result", key: "target_audio_monitor", ok: false, error: "no audio device" });
  assert.equal(page.toggle.disabled, false);
  assert.match(page.win.document.getElementById("target-audio-note").textContent, /unavailable/i);
  page.message(telemetry(false, "s1", "error"));
  assert.equal(page.toggle.getAttribute("aria-checked"), "false");
  page.toggle.click();
  assert.equal(page.sent.length, 2);
});

test("disconnect and a new session discard pending control state", (t) => {
  const page = consolePage(t);
  page.connected(true);
  page.message(telemetry());
  page.toggle.click();
  page.connected(false);
  assert.equal(page.toggle.disabled, true);
  page.connected(true);
  page.message(telemetry(false, "s2"));
  assert.equal(page.toggle.disabled, false);
  page.message({ event: "voice_set_result", key: "target_audio_monitor", ok: true, value: true });
  assert.equal(page.toggle.getAttribute("aria-checked"), "false");
});

test("stale voice data disables playback controls", (t) => {
  const page = consolePage(t);
  page.connected(true);
  page.message(telemetry(true));
  const stale = telemetry(true);
  stale.voice.status = "stale";
  stale.voice.data = null;
  page.message(stale);
  assert.equal(page.toggle.disabled, true);
  page.toggle.click();
  assert.equal(page.sent.length, 0);
});

test("Vietnamese labels retain the confirmed playback state", (t) => {
  const page = consolePage(t);
  page.connected(true);
  page.message(telemetry(true));
  page.win.document.querySelector('[data-language="vi"]').click();
  assert.equal(page.toggle.textContent, "BẬT");
  assert.equal(page.toggle.getAttribute("aria-checked"), "true");
  assert.equal(page.win.document.documentElement.lang, "vi");
});
