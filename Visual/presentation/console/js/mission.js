"use strict";
/* Operator views consume observations. Verdicts are always supplied by the
   backend; the browser never derives acceptance from a camera or a meter. */
(() => {
  const byId = (id) => document.getElementById(id);
  const tr = (value) => window.MissionI18n ? window.MissionI18n.t(value) : value;
  const text = (id, value) => { byId(id).textContent = tr(value); };
  const finite = (value) => typeof value === "number" && Number.isFinite(value);
  const percentage = (value) => finite(value) ? `${Math.round(value * 100)}%` : "--";
  const db = (value) => finite(value) ? `${value.toFixed(1)} dBFS` : "--";
  const drawer = byId("tuning-drawer");
  const knobs = new Map();
  let connected = false, canSave = false, saving = false, lastMessage = 0;
  let currentSession = null, lastDecision = "", lastSnapshot = null;
  const decisions = [];
  let lastFeedback = "Waiting for connection.";
  const monitorToggle = byId("target-audio-toggle");
  let monitorSession = null, monitorPending = null, monitorTimer = null, monitorError = "";

  function clearMonitorRequest() {
    clearTimeout(monitorTimer); monitorTimer = null; monitorPending = null;
  }

  function renderMonitor(voice, session) {
    if (session !== monitorSession) {
      clearMonitorRequest(); monitorError = ""; monitorSession = session;
    }
    const monitor = voice?.target_audio_monitor;
    monitorToggle.disabled = !monitor || monitorPending !== null;
    monitorToggle.setAttribute("aria-checked", String(monitor?.enabled === true));
    text("target-audio-toggle", monitor?.enabled ? "ON" : "OFF");
    text("target-audio-note", !voice ? "Available during a kiosk voice session."
      : !monitor ? "Local playback unavailable."
      : monitorPending !== null ? "Applying local playback…"
      : monitorError || (monitor.status === "error" ? "Local playback unavailable."
        : monitor.status === "playing" ? "Playing on the OpenJarvis machine."
        : monitor.enabled ? "Waiting for STT audio."
        : "Plays on the OpenJarvis machine."));
    byId("target-audio-note").title = monitor?.error || "";
  }

  monitorToggle.addEventListener("click", () => {
    const voice = lastSnapshot?.voice;
    if (!connected || voice?.status !== "live" || monitorPending !== null) return;
    const value = !voice.data.target_audio_monitor.enabled;
    if (!window.MissionVision.send({ cmd: "voice_set", key: "target_audio_monitor", value })) return;
    monitorPending = { session: voice.session_id }; monitorError = "";
    monitorTimer = setTimeout(() => {
      clearMonitorRequest(); monitorError = "Local playback unavailable."; render(lastSnapshot);
    }, 6000);
    render(lastSnapshot);
  });

  function onMonitorResult(message) {
    if (!monitorPending || monitorPending.session !== monitorSession) return;
    clearMonitorRequest();
    monitorError = message.ok ? "" : "Local playback unavailable.";
    // The switch displays telemetry, never an optimistic command value.
    render(lastSnapshot);
  }

  function feedback(message, error = false) {
    lastFeedback = message;
    text("tuning-feedback", message);
    byId("tuning-feedback").dataset.error = String(error);
  }

  function refreshSave() {
    const pending = [...knobs.values()].some((knob) => knob.pending !== null);
    byId("save-settings").disabled = !connected || !canSave || saving || pending;
  }

  function displayKnob(knob) {
    const input = knob.input;
    const places = input.step.includes(".") ? input.step.split(".")[1].length : 0;
    const value = Number(input.value);
    byId(input.id.replace("k-", "o-")).textContent = knob.confirmed === null && knob.pending === null
      ? "--" : `${value.toFixed(places)}${input.dataset.unit ? ` ${input.dataset.unit}` : ""}`;
    input.style.setProperty("--p", `${(value - Number(input.min)) / (Number(input.max) - Number(input.min)) * 100}%`);
    input.setAttribute("aria-valuetext", `${value.toFixed(places)} ${input.dataset.unit}`.trim());
  }

  function loadValues(scope, values = {}, bounds = {}) {
    knobs.forEach((knob, key) => {
      if (knob.scope !== scope) return;
      if (finite(values[key])) {
        if (Array.isArray(bounds[key])) {
          knob.input.min = bounds[key][0]; knob.input.max = bounds[key][1];
        }
        knob.confirmed = values[key];
        if (knob.pending === null) knob.input.value = values[key];
        knob.input.disabled = !connected;
        displayKnob(knob);
      } else {
        knob.input.disabled = true;
      }
    });
  }

  document.querySelectorAll(".tuning-knob input").forEach((input) => {
    const knob = { input, scope: input.closest(".tuning-knob").dataset.scope,
      confirmed: null, pending: null, timer: null, inFlight: null };
    knobs.set(input.dataset.key, knob);
    input.addEventListener("input", () => {
      knob.pending = Number(input.value);
      displayKnob(knob); refreshSave();
      feedback("Applying live change…");
      clearTimeout(knob.timer);
      knob.timer = setTimeout(() => sendKnob(knob), 120);
    });
  });

  function sendKnob(knob) {
    if (knob.inFlight !== null) return;
    if (knob.pending === null) return;
    const value = knob.pending;
    const sent = window.MissionVision.send({ cmd: knob.scope === "voice" ? "voice_set" : "set",
      key: knob.input.dataset.key, value });
    if (sent) knob.inFlight = value;
    else {
      knob.pending = null; knob.input.value = knob.confirmed ?? knob.input.min;
      displayKnob(knob); feedback("Connection lost. Change was not applied.", true); refreshSave();
    }
  }

  function onSetResult(message) {
    const knob = knobs.get(message.key);
    if (!knob) return;
    const sent = knob.inFlight;
    knob.inFlight = null;
    const newer = knob.pending !== null && knob.pending !== sent;
    if (message.ok && finite(message.value)) knob.confirmed = message.value;
    if (!newer) {
      knob.pending = null;
      knob.input.value = knob.confirmed ?? knob.input.min;
      displayKnob(knob);
      feedback(message.ok ? "Live change confirmed. Save to keep it after restart."
        : `Change rejected: ${message.error || "invalid value"}`, !message.ok);
    } else sendKnob(knob);
    refreshSave();
  }

  byId("open-tuning").addEventListener("click", () => {
    drawer.showModal(); byId("open-tuning").setAttribute("aria-expanded", "true");
  });
  drawer.addEventListener("close", () => {
    byId("open-tuning").setAttribute("aria-expanded", "false"); byId("open-tuning").focus();
  });
  drawer.addEventListener("click", (event) => {
    const bounds = drawer.getBoundingClientRect();
    if (event.target === drawer && event.clientX < bounds.left) drawer.close();
  });

  byId("save-settings").addEventListener("click", () => {
    if (window.MissionVision.send({ cmd: "save_settings" })) {
      saving = true; refreshSave(); feedback("Saving active settings…");
    }
  });

  const canvas = byId("waveform"), context = canvas.getContext("2d");
  function drawWaveform(samples = []) {
    const width = canvas.width, height = canvas.height;
    context.clearRect(0, 0, width, height);
    context.lineWidth = 1; context.strokeStyle = "#222";
    for (let x = 0; x <= width; x += width / 10) {
      context.beginPath(); context.moveTo(x, 0); context.lineTo(x, height); context.stroke();
    }
    for (const y of [height / 4, height / 2, height * 3 / 4]) {
      context.beginPath(); context.moveTo(0, y); context.lineTo(width, y); context.stroke();
    }
    context.strokeStyle = samples.length ? "#60cbd4" : "#555";
    context.lineWidth = 2; context.beginPath();
    if (samples.length) {
      samples.slice(-128).forEach((sample, index, all) => {
        const x = index / Math.max(1, all.length - 1) * width;
        const y = height / 2 - Math.max(-1, Math.min(1, sample)) * height * 0.44;
        index ? context.lineTo(x, y) : context.moveTo(x, y);
      });
    } else { context.moveTo(0, height / 2); context.lineTo(width, height / 2); }
    context.stroke();
  }

  function logDecision(voice, verdict) {
    const signature = `${voice.lock_state}:${voice.target_track}:${verdict}:${voice.evidence?.source}:${voice.overlap}`;
    if (signature === lastDecision) return;
    lastDecision = signature;
    decisions.unshift({ time: new Date(), verdict: verdict || "IDLE",
      evidence: voice.evidence?.source || "no speech evidence", target: voice.target_track });
    decisions.splice(12);
    renderDecisions();
  }

  function renderDecisions() {
    const list = byId("decision-log"); list.replaceChildren();
    if (!decisions.length) {
      const row = document.createElement("li"); row.className = "helper";
      row.textContent = tr("No decisions yet."); list.append(row);
    }
    decisions.forEach((decision) => {
      const row = document.createElement("li"), time = document.createElement("time"), body = document.createElement("span");
      time.textContent = decision.time.toLocaleTimeString(window.MissionI18n?.language() === "vi" ? "vi-VN" : "en-US");
      const evidence = { asd: "Audio + face", mar: "Mouth activity", voice: "Voiceprint", audio: "Audio" }[decision.evidence] || decision.evidence;
      body.textContent = `${tr(decision.verdict)} · ${tr(evidence)}${decision.target != null ? ` · ${tr(`Face ${decision.target}`)}` : ""}`;
      row.append(time, body); list.append(row);
    });
  }

  function render(snapshot) {
    const voiceState = snapshot?.voice;
    const voice = connected && voiceState?.status === "live" ? voiceState.data : null;
    const freshAudio = voice?.audio && finite(voice.audio.ts) && Math.abs(Date.now() / 1000 - voice.audio.ts) < 1.5;
    const audio = freshAudio ? voice.audio : null;
    const freshVerdict = voice && finite(voice.verdict_ts) && Math.abs(Date.now() / 1000 - voice.verdict_ts) < 1.5;
    const rawVerdict = freshVerdict ? String(voice.verdict || "").toLowerCase() : "";
    const verdict = ["accept", "uncertain", "reject"].includes(rawVerdict) ? rawVerdict : "idle";
    byId("verdict").dataset.state = verdict;
    text("verdict-label", verdict === "idle" ? (voice ? "LISTENING" : "STANDBY") : verdict.toUpperCase());
    const reasons = { accept: "Customer speech accepted by the speaker gate.", uncertain: "Ambiguous speech. The backend applies safe handling.", reject: "Speech rejected by the speaker gate." };
    text("verdict-reason", reasons[verdict] || (voice ? "Waiting for fresh speaker evidence." : voiceState?.status === "stale" ? "Voice telemetry is stale. Waiting for fresh data." : "Start a voice session on the kiosk."));
    text("identity-mode", voice ? `${voice.identity} mode` : "Awaiting session");
    text("lock-state", voice ? String(voice.lock_state).replaceAll("_", " ").toUpperCase() : "--");
    text("lock-target", voice?.target_track != null ? `Face ${voice.target_track}` : "--");
    text("evidence-source", freshVerdict && voice.evidence?.source ? ({ asd: "Audio + face", mar: "Mouth activity", voice: "Voiceprint", audio: "Audio" }[voice.evidence.source] || voice.evidence.source) : "--");
    text("voiceprint-status", voice ? (voice.voice_ready ? "Ready" : "Enrolling") : "--");
    text("voice-similarity", voice ? percentage(voice.voice_similarity) : "--");
    text("overlap-status", voice ? `${voice.overlap ? "Overlap" : "Solo"} · TSE ${voice.tse_ready ? "ready" : "not ready"}` : "--");
    text("audio-db-value", audio && finite(audio.rms_dbfs) ? audio.rms_dbfs.toFixed(1) : "--");
    byId("audio-meter").value = audio && finite(audio.rms_dbfs) ? audio.rms_dbfs : -96;
    text("raw-db", audio ? db(audio.raw_rms_dbfs) : "--");
    text("audio-status", audio ? (voice.bot_speaking ? "Bot speaking · mic live" : "Microphone live") : "Awaiting microphone");
    text("noise-status", voice ? (voice.enhancer_effective === "rnnoise" ? "RNNoise active" : voice.enhancer_requested === "rnnoise" ? "Raw fallback" : "Off") : "Waiting");
    text("mask-status", voice ? (voice.stt_mask ? "Enabled" : "Off") : "Waiting");
    renderMonitor(voice, voice ? voiceState.session_id : null);
    drawWaveform(audio && Array.isArray(audio.waveform) ? audio.waveform.filter(finite) : []);
    const asd = connected ? snapshot?.asd : null;
    const sameTarget = !voice?.locked || asd?.track_id === voice.target_track;
    const probability = sameTarget ? asd?.probability : null;
    text("asd-score", percentage(probability));
    byId("asd-meter").value = finite(probability) ? probability : 0;
    text("asd-note", finite(probability) ? `Face ${asd.track_id} · synchronized speech probability`
      : asd?.status === "disabled" ? "Light-ASD is disabled."
      : asd?.status === "unavailable" ? "Light-ASD is unavailable."
      : asd?.active ? "Collecting synchronized evidence…" : "Waiting for microphone audio.");
    const target = snapshot?.tracks?.find((track) => track.id === (voice?.target_track ?? snapshot.nearest_id));
    text("mouth-score", connected ? percentage(target?.mouth_activity) : "--");
    text("asd-use", voice ? percentage(voice.asd_effective_use) : "--");
    text("asd-late", voice ? voice.asd_late : "--");
    text("masked-count", voice ? voice.stt_masked_no_verdict_frames : "--");
    text("bargein-count", voice ? voice.bargein_blocked : "--");
    byId("target-tag").hidden = !voice?.locked;
    if (voice?.locked) text("target-tag", `TARGET LOCKED · FACE ${voice.target_track}`);
    byId("voice-dot").className = `dot${voice ? "" : " off"}`;
    text("voice-connection", voice ? "Kiosk voice connected · observations live" : voiceState?.status === "stale" ? "Voice data stale" : "Waiting for a kiosk voice session");
    byId("voice-knobs").disabled = !voice;
    text("voice-tuning-note", voice ? "Changes apply to this voice session. Save to persist." : "Available during a kiosk voice session.");
    if (voice) {
      if (currentSession !== voiceState.session_id) {
        currentSession = voiceState.session_id; decisions.length = 0; lastDecision = "";
      }
      loadValues("voice", voice.settings, voice.bounds); logDecision(voice, verdict === "idle" ? "" : verdict.toUpperCase());
    }
    refreshSave();
  }

  window.addEventListener("vision:connection", (event) => {
    connected = event.detail;
    if (!connected) {
      canSave = false; saving = false; lastSnapshot = null;
      knobs.forEach((knob) => {
        clearTimeout(knob.timer); knob.pending = knob.inFlight = null; knob.input.disabled = true;
      });
      feedback("Disconnected. Waiting to reconnect.", true);
      clearMonitorRequest(); monitorError = "";
    }
    render(lastSnapshot);
  });
  window.addEventListener("vision:message", (event) => {
    const message = event.detail;
    if (message.event === "info") {
      canSave = message.can_save === true; loadValues("vision", message.live, message.bounds);
      feedback(canSave ? "Connected. Changes apply live." : "Connected. No writable configuration was selected."); refreshSave();
    } else if (message.event === "monitor") {
      lastMessage = Date.now(); lastSnapshot = message;
      if (message.live) loadValues("vision", message.live);
      text("last-update", "Telemetry live · 15 Hz"); render(message);
    } else if (message.event === "voice_set_result" && message.key === "target_audio_monitor") onMonitorResult(message);
    else if (["set_result", "voice_set_result"].includes(message.event)) onSetResult(message);
    else if (message.event === "save_result") {
      saving = false;
      if (message.ok) feedback(message.voice?.skipped ? "Vision settings saved. No active voice session to save." : "Vision and voice settings saved.");
      else {
        const states = ["vision", "voice"].map((scope) => `${scope === "vision" ? "Vision" : "Voice"}: ${message[scope]?.ok ? "saved" : message[scope]?.error || "failed"}`);
        feedback(states.join(" · "), true);
      }
      refreshSave();
    }
  });
  window.addEventListener("vision:language", () => {
    const stale = lastMessage && Date.now() - lastMessage > 1500;
    render(stale ? null : lastSnapshot);
    text("last-update", lastMessage ? (stale ? "Telemetry stale" : "Telemetry live · 15 Hz") : "No telemetry yet");
    text("tuning-feedback", lastFeedback);
    renderDecisions();
  });
  setInterval(() => {
    if (lastMessage && Date.now() - lastMessage > 1500) {
      text("last-update", "Telemetry stale"); render(null);
    } else if (lastSnapshot) render(lastSnapshot);
  }, 500);
  drawWaveform();
})();
