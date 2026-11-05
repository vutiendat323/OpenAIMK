"use strict";
/* Live console for the vision service.  Same port as the presence stream:
   sends {"cmd":"monitor"}, then receives "info" once, telemetry JSON and the
   camera frame (binary JPEG) at the track-loop rate, and may send
   {"cmd":"set"} for face_ipd_m / distance_threshold. */
const $ = (id) => document.getElementById(id);
const tr = (value) => window.MissionI18n ? window.MissionI18n.t(value) : value;

const FONT = "Barlow, Arial, sans-serif", GREEN = "#76b900", RED = "#ff4d4d", GREY = "#9a9a9a";
const HIST = 180, GATES = 48;          // 12 s of telemetry at 15 Hz; gate meter segments
const st = { ws: null, conn: false, tele: null, frame: null, fw: 640, fh: 480, thr: 1, hist: [], gates: [], tick: 0, targetTrack: null };
const bodies = () => (st.tele && st.tele.bodies) || [];
const nearestBody = () => bodies().reduce((a, b) => (a && a.dist <= b.dist ? a : b), null);

/* the face the kiosk cares about; the server's Scene decides which one */
function nearest(m) {
  return m ? m.tracks.find((t) => t.id === m.nearest_id) || null : null;
}
function stateOf(t) {
  if (!t) return bodies().length ? ["warn", "Present, not facing"] : ["", "No face"];
  if (t.gate === false) return ["warn", "Holding"];
  if (!(t.dist > 0)) return ["", "Measuring"];
  return t.dist < st.thr ? ["crit", "Too close"] : ["ok", "In range"];
}

/* ---------- connection ---------- */
function connect() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const url = location.protocol.startsWith("http") ? `${protocol}//${location.host}` : "ws://localhost:9876";
  const ws = new WebSocket(url);
  ws.binaryType = "blob";
  st.ws = ws;
  ws.onopen = () => { st.conn = true; ws.send(JSON.stringify({ cmd: "monitor" })); paint(); window.dispatchEvent(new CustomEvent("vision:connection", { detail: true })); };
  ws.onclose = () => {
    st.conn = false; st.tele = null; st.targetTrack = null; st.hist = []; st.gates = [];
    if (st.frame) { st.frame.close(); st.frame = null; }
    paint(); drawFeed(); setTimeout(connect, 2000);
    window.dispatchEvent(new CustomEvent("vision:connection", { detail: false }));
  };
  ws.onmessage = (e) => {
    if (typeof e.data !== "string") {
      createImageBitmap(e.data).then((bmp) => {
        if (st.ws !== ws || !st.conn) { bmp.close(); return; }
        if (st.frame) st.frame.close();
        st.frame = bmp; st.fw = bmp.width; st.fh = bmp.height;
        drawFeed();
      }).catch(() => {});
      return;
    }
    let m;
    try { m = JSON.parse(e.data); } catch { return; }
    if (m.event === "info") onInfo(m);
    else if (m.event === "monitor") onTelemetry(m);
    else if (m.event === "set_result" && !m.ok) console.warn("set rejected", m);
    window.dispatchEvent(new CustomEvent("vision:message", { detail: m }));
  };
}

function onInfo(m) {
  $("camera").textContent = m.camera;
}

function onTelemetry(m) {
  st.tele = m;
  st.thr = m.threshold;
  const voice = m.voice && m.voice.status === "live" ? m.voice.data : null;
  st.targetTrack = voice && voice.locked ? voice.target_track : null;
  const t = nearest(m);
  st.hist.push({ filt: t && t.dist > 0 ? t.dist : null, raw: t ? t.raw : null });
  if (st.hist.length > HIST) st.hist.shift();
  if (t && t.gate != null && ++st.tick % 3 === 0) {
    st.gates.push(t.gate);
    if (st.gates.length > GATES) st.gates.shift();
  }
  paint();
}

/* ---------- panel ---------- */
const faceRow = (t) => {
  const spoof = t.spoof_flag ? tr(`Spoof ${t.spoof.toFixed(2)}`) : "";
  const dist = t.dist > 0 ? t.dist.toFixed(2) + "<small>m</small>" : "--";
  return `<div class="fx"><span class="t">${tr(`Face ${t.id}`)}</span>${spoof ? `<span class="s warn">${spoof}</span>` : ""}<span class="v${spoof ? " warn" : ""}">${dist}</span></div>`;
};
function paint() {
  $("conn-dot").className = "dot" + (st.conn ? "" : " off");
  $("conn-text").textContent = tr(st.conn ? "Live" : "Disconnected");
  $("camera-dot").className = "dot" + (st.conn ? "" : " off");

  const tracks = st.tele ? st.tele.tracks : [];
  const t = nearest(st.tele);
  const [cls, label] = stateOf(t);
  $("t-name").textContent = tr(t ? `Face ${t.id}` : bodies().length ? "Person" : "No target");
  $("t-state").className = "state " + cls;
  $("t-state").textContent = tr(st.conn ? label : "Disconnected");
  $("t-dist").className = "num" + (cls === "crit" ? " crit" : "");
  $("t-dist").innerHTML = (t && t.dist > 0 ? t.dist.toFixed(2) : "--") + "<small>m</small>";
  $("t-live").className = "v" + (t && t.spoof_flag ? " warn" : "");
  $("t-live").textContent = !t || t.spoof == null ? "--" : t.spoof_flag ? tr("Spoof") : Math.round((1 - t.spoof) * 100) + "%";
  $("t-raw").innerHTML = t && t.raw != null ? t.raw.toFixed(3) + "<small>m</small>" : "--";
  const nb = nearestBody();
  const body = (t && t.body_m != null) ? t.body_m : (nb ? nb.dist : null);
  $("t-body").innerHTML = body != null ? body.toFixed(2) + "<small>m</small>" : "--";
  const others = tracks.filter((x) => x !== t);
  $("face-count").textContent = tr(`${others.length} tracked`);
  $("faces").innerHTML = others.length ? others.map(faceRow).join("") : `<div class="fx"><span class="s">${tr("None")}</span></div>`;

  $("gate").innerHTML = Array.from({ length: GATES }, (_, i) => {
    const g = st.gates[i - (GATES - st.gates.length)];
    return `<i${g ? ' class="on"' : ""}></i>`;
  }).join("");
  $("gate-pct").textContent = st.gates.length ? Math.round(st.gates.filter(Boolean).length / st.gates.length * 100) + "%" : "--";

  const tele = st.tele;
  $("m-fps").textContent = tele ? Math.round(tele.fps) : "--";
  $("m-track").textContent = tele ? tele.timing_ms.track.toFixed(1) + " ms" : "--";
  $("m-spoof").textContent = tele && tele.timing_ms.spoof ? Math.round(tele.timing_ms.spoof) + " ms" : "--";
  $("feed-dot").className = "dot" + (!st.conn ? " off" : !t ? (bodies().length ? " warn" : " off") : t.gate === false ? " warn" : "");
  $("feed-state").textContent = tr(!st.conn ? "Disconnected"
    : !t ? (bodies().length ? "Body only" : "Idle") : t.gate === false ? "Head turned" : "Tracking");
  drawSpark();
}

/* ---------- camera ---------- */
const feed = $("feed"), fx = feed.getContext("2d");
function drawFeed() {
  const k = 2;                                   // draw at 2x the frame for crisp overlay lines
  if (feed.width !== st.fw * k || feed.height !== st.fh * k) { feed.width = st.fw * k; feed.height = st.fh * k; }
  const W = feed.width, H = feed.height;
  fx.fillStyle = "#000"; fx.fillRect(0, 0, W, H);
  if (!st.frame) {
    fx.fillStyle = GREY; fx.textAlign = "center"; fx.font = `500 34px ${FONT}`;
    fx.fillText(tr(st.conn ? "Waiting for camera" : "Vision service not reachable"), W / 2, H / 2);
    fx.textAlign = "left";
    return;
  }
  // Mirror the preview; draw labels normally so their text stays readable.
  fx.save();
  fx.translate(W, 0);
  fx.scale(-1, 1);
  fx.drawImage(st.frame, 0, 0, W, H);
  fx.restore();
  if (!st.tele) return;
  const s = W / st.fw;
  const screenBox = ([x1, y1, x2, y2]) => [W - x2 * s, y1 * s, W - x1 * s, y2 * s];
  const t = nearest(st.tele);
  bodies().forEach((b) => {          // thin white outline: presence, not the target
    const [x1, y1, x2, y2] = screenBox(b.box);
    fx.lineWidth = 2; fx.strokeStyle = "rgba(255,255,255,.4)";
    fx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    fx.font = `500 22px ${FONT}`; fx.fillStyle = "rgba(255,255,255,.75)";
    fx.fillText(`${b.dist.toFixed(2)} m`, x1 + 6, y2 - 10);
  });
  st.tele.tracks.forEach((o) => {
    if (o === t) return;
    const [x1, y1, x2, y2] = screenBox(o.box);
    fx.lineWidth = 2; fx.strokeStyle = o.spoof_flag ? "#f0a828" : "rgba(255,255,255,.55)";
    fx.strokeRect(x1, y1, x2 - x1, y2 - y1);
  });
  const locked = st.tele.tracks.find((o) => o.id === st.targetTrack);
  if (locked) {
    const [lx1, ly1, lx2, ly2] = screenBox(locked.box);
    fx.lineWidth = 4; fx.strokeStyle = "#60cbd4";
    fx.strokeRect(lx1 - 8, ly1 - 8, lx2 - lx1 + 16, ly2 - ly1 + 16);
    fx.font = `700 22px ${FONT}`; fx.fillStyle = "#60cbd4";
    fx.fillText(tr(`TARGET · ${locked.id}`), lx1, Math.min(H - 10, ly2 + 38));
  }
  if (!t) return;
  const [x1, y1, x2, y2] = screenBox(t.box), bw = x2 - x1, bh = y2 - y1;
  const [cls] = stateOf(t);
  const col = cls === "warn" || cls === "" ? GREY : cls === "crit" ? RED : GREEN;
  fx.lineWidth = 2; fx.strokeStyle = col; fx.strokeRect(x1, y1, bw, bh);
  fx.lineWidth = 5; const c = Math.min(bw, bh) * .14;   // heavier corner ticks read at a glance
  [[x1, y1 + c, x1, y1, x1 + c, y1], [x2 - c, y1, x2, y1, x2, y1 + c],
   [x2, y2 - c, x2, y2, x2 - c, y2], [x1 + c, y2, x1, y2, x1, y2 - c]]
    .forEach((p) => { fx.beginPath(); fx.moveTo(p[0], p[1]); fx.lineTo(p[2], p[3]); fx.lineTo(p[4], p[5]); fx.stroke(); });
  if (t.kps && t.gate) {
    t.kps.forEach(([kx, ky]) => {
      fx.fillStyle = "rgba(0,0,0,.6)"; fx.beginPath(); fx.arc(W - kx * s, ky * s, 5.5, 0, 7); fx.fill();
      fx.fillStyle = "#fff"; fx.beginPath(); fx.arc(W - kx * s, ky * s, 3.2, 0, 7); fx.fill();
    });
  }
  const text = tr(t.gate === false ? "Held" : t.dist > 0 ? `${t.dist.toFixed(2)} m` : "Measuring");
  fx.font = `700 30px ${FONT}`;
  const tw = fx.measureText(text).width + 26, ty = Math.max(y1 - 50, 0);
  fx.fillStyle = "rgba(0,0,0,.72)"; fx.fillRect(x1 - 1, ty, tw, 44);
  fx.fillStyle = col; fx.fillRect(x1 - 1, ty, 4, 44);
  fx.fillStyle = "#fff"; fx.fillText(text, x1 + 14, ty + 32);
}

/* ---------- distance chart ---------- */
const sp = $("spark"), sx = sp.getContext("2d");
function drawSpark() {
  const W = sp.width, H = sp.height, lo = .2;
  const peak = Math.max(0, ...st.hist.flatMap((p) => [p.filt || 0, p.raw || 0]));
  const hi = Math.min(6, Math.max(2.3, peak * 1.1));
  const y = (v) => H - 22 - (v - lo) / (hi - lo) * (H - 36), x = (i) => i / (HIST - 1) * (W - 52) + 46;
  const off = HIST - st.hist.length;
  sx.clearRect(0, 0, W, H); sx.font = `500 18px ${FONT}`; sx.lineWidth = 1;
  const step = hi > 3 ? 1 : .5;
  for (let v = step; v < hi; v += step) {
    sx.strokeStyle = "#1f1f1f"; sx.beginPath(); sx.moveTo(46, y(v)); sx.lineTo(W - 4, y(v)); sx.stroke();
    sx.fillStyle = "#666"; sx.fillText(v.toFixed(1), 4, y(v) + 6);
  }
  sx.setLineDash([8, 6]); sx.lineWidth = 2; sx.strokeStyle = RED;
  sx.beginPath(); sx.moveTo(46, y(st.thr)); sx.lineTo(W - 4, y(st.thr)); sx.stroke(); sx.setLineDash([]);
  const line = (key, color, width) => {
    sx.strokeStyle = color; sx.lineWidth = width; sx.lineJoin = "round"; sx.beginPath();
    let on = false;
    st.hist.forEach((p, i) => {
      if (p[key] == null) { on = false; return; }
      on ? sx.lineTo(x(i + off), y(p[key])) : sx.moveTo(x(i + off), y(p[key]));
      on = true;
    });
    sx.stroke();
  };
  line("raw", "#555", 2);
  line("filt", GREEN, 3.5);
}

/* Console modules share this small transport; the camera owns reconnects. */
window.MissionVision = {
  connected: () => st.conn,
  send: (message) => {
    if (!st.conn || !st.ws || st.ws.readyState !== WebSocket.OPEN) return false;
    st.ws.send(JSON.stringify(message));
    return true;
  },
};
window.addEventListener("vision:language", () => { paint(); drawFeed(); });
connect();
drawFeed();
