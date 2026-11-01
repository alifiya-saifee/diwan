// The live floor (Part 7): everything here moves because of a message from /ws/floor, and every message says what caused it.
// The alive layer (breathing, blinks, head drift) always plays and never pretends to be work.
import { api } from "./app.js";

const D2R = Math.PI / 180;
const PRIORITY = ["blocked", "waiting", "fallback", "handing", "receiving", "typing", "checking", "comparing", "reading", "working", "idle"];
const BLEND = { typing: .15, checking: .15, idle: .4 };
const HOLD = 3.2;      // an event that was done in a moment stays on show this long, so it can be seen
const MIN_STATE = .3;  // a robot changes working state at most this often
const MAX_REDRAW = 8, MAX_CARDS = 24;
const REST = [[-.34, .92, .6], [.34, .92, .6]], KEYS = [[-.16, .94, .72], [.16, .94, .72]];
// lean / side / yaw / pitch in degrees (+pitch looks down, toward the desk); hands in the robot's own metres
const POSE = {
  idle:      { lean: 0, side: 0, yaw: 0, pitch: 0, hands: REST, ring: null, ringI: .5 },
  working:   { lean: 4, side: 0, yaw: 0, pitch: 4, hands: REST, ring: null, ringI: 1 },
  reading:   { lean: 8, side: 0, yaw: 0, pitch: 10, hands: REST, ring: null, ringI: 1.1 },
  typing:    { lean: 10, side: 0, yaw: 0, pitch: 12, hands: KEYS, ring: null, ringI: 1.6 },
  checking:  { lean: 6, side: 0, yaw: 0, pitch: 6, hands: [REST[0], [.24, 1.08, .62]], ring: null, ringI: 1.3 },
  comparing: { lean: 8, side: 0, yaw: 0, pitch: 8, hands: REST, ring: null, ringI: 1.3 },
  waiting:   { lean: 0, side: 0, yaw: 30, pitch: -4, hands: [REST[0], [.42, 1.78, .24]], ring: 0xf0b35e, ringI: 2 },
  handing:   { lean: 0, side: 0, yaw: 0, pitch: 0, hands: [REST[0], [.2, 1.1, .78]], ring: null, ringI: 1.6, rise: .06 },
  receiving: { lean: 0, side: 0, yaw: 15, pitch: 2, hands: [REST[0], [.36, 1, .66]], ring: null, ringI: 1.6 },
  blocked:   { lean: -6, side: 4, yaw: 0, pitch: 15, hands: [[-.26, .7, .3], [.26, .7, .3]], ring: 0xf27d7d, ringI: 1.8 },
  fallback:  { lean: 0, side: 0, yaw: 0, pitch: 0, hands: REST, ring: 0x8b92a3, ringI: 1 },
};
const CHIP = { working: "⚙", reading: "📖 reading", typing: "✍ writing", checking: "☑ checking", comparing: "⇄ comparing", waiting: "✋ needs a person", handing: "→ handing off",
  receiving: "← received", blocked: "! blocked", fallback: "⟲ fallback rules" };
const CARD = { quote: ["#f6f0dd", "#2a2415", "SAID"], task: ["#2c4a86", "#eaf1ff", "TASK"], doc: ["#eef0f4", "#1a1f2a", "DOCUMENT"], money: ["#1f6b45", "#e7fff1", "MONEY"],
  compliance: ["#8e2730", "#ffe9e9", "COMPLIANCE"], stamp: ["#b8913c", "#201703", "APPROVAL"], folder: ["#a06a2c", "#fff4e0", "CASE"], phone: ["#1e7a57", "#e7fff1", "CALL"],
  envelope: ["#30384a", "#ece8df", "MESSAGE"], note: ["#30384a", "#ece8df", "MEETING"], stuck: ["#5d6476", "#ece8df", "STUCK"] };
const seeded = (id) => { let h = 7; for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h; };
const wrapLines = (x, text, w, max) => {
  const out = []; let line = "";
  for (const word of String(text || "").split(/\s+/)) {
    const t = line ? `${line} ${word}` : word;
    if (x.measureText(t).width > w && line) { out.push(line); line = word; if (out.length === max) break; } else line = t;
  }
  if (out.length < max && line) out.push(line);
  else if (out.length === max && line) out[max - 1] = out[max - 1].replace(/.{0,2}$/, "…");
  return out;
};

export function attachFloor(ctx) {
  const { THREE, scene, DEPTS, AG, hqRooms, deptOf, label } = ctx;
  const stats = { messages: 0, refused: [], cards: 0, ripples: [], states: [], reduced: false, redraws: 0, maxRedraw: 0, stacks: 0 };
  const live = {};  // agent id -> what it is really doing now
  const flights = [], props = [], dirty = new Set();
  const reduced = () => stats.reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const handGeo = new THREE.SphereGeometry(.085, 14, 10);
  const shellMat = new THREE.MeshStandardMaterial({ color: 0xe9ebf1, roughness: .35, metalness: .15 });
  let stuckItems = [], stuckMark = null;

  const agent = (id) => live[id] || (live[id] = { state: "idle", until: 0, title: "", preview: null, changed: 0, done: null });
  function setState(id, state, secs = HOLD, title = "") {
    if (!id) return;
    const a = agent(id), now = performance.now() / 1000;
    if (PRIORITY.indexOf(state) > PRIORITY.indexOf(a.state) && now < a.until) return;  // something more urgent is on
    a.pending = state; a.pendingUntil = now + secs; a.pendingTitle = title || a.title;
    if (now - a.changed >= MIN_STATE) applyPending(a, now);
  }
  function applyPending(a, now) {
    if (a.pending === undefined) return;
    a.state = a.pending; a.until = a.pendingUntil; a.title = a.pendingTitle; a.changed = now; a.pending = undefined;
    stats.states.push(a.state); if (stats.states.length > 200) stats.states.shift();
  }

  // ---------- the feed ----------
  function connect() {
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/floor`);
    ws.onmessage = (m) => { const d = JSON.parse(m.data); (d.pulses || []).forEach(pulse); (d.messages || []).forEach(take); };
    ws.onclose = () => setTimeout(connect, 1500);
  }
  function pulse(p) {
    if (!p.caused_by) return stats.refused.push(p);
    const st = { read: "reading", write: "typing", check: "checking", fallback: "fallback" }[p.step] || "working";
    setState(p.agent, st, p.step === "write" ? 60 : p.step === "fallback" ? 6 : 1.2, p.title);
  }
  function take(m) {
    if (!m.caused_by) { stats.refused.push(m); console.warn("floor: no cause, not animated", m); return; }
    stats.messages++;
    if (m.agent) applyToAgent(m);
    if (m.ripple) { setTimeout(() => playRipple(m.ripple), 400); return; }
    if (m.in_ripple || document.hidden) return;  // a hidden tab keeps its state; it doesn't queue up flights
    if (m.count > 1) stats.stacks++;
    if (m.stuck) return fallToStuck(m);
    if (reduced()) { (m.to || []).forEach((r) => ctx.flash(r)); return; }
    for (const r of m.to) fly(m, m.from, r);
    if (!m.to.length && m.from) fly(m, m.from, null);  // leaves by the door
  }
  function applyToAgent(m) {
    const a = agent(m.agent), now = new Date(m.at || Date.now());
    if (m.preview) { a.preview = { ...m.preview, at: now }; dirty.add(m.agent); }
    if (m.type === "agent.run_started") setState(m.agent, "working", 60, m.text);
    else if (m.type === "agent.run_finished") { a.state = "idle"; a.until = 0; a.done = now; a.pending = undefined; dirty.add(m.agent); }
    else if (m.type === "agent.fallback") setState(m.agent, "fallback", 6, m.text);
    else if (m.type === "agent.blocked") setState(m.agent, "blocked", 8, m.text);
    else if (m.preview) setState(m.agent, { checklist: "checking", compare: "comparing", form: "typing", typing: "typing" }[m.preview.kind] || "working", HOLD, m.text);
    else if ((m.to || []).some((r) => r !== m.from)) setState(m.agent, "handing", 1, m.text);
    else setState(m.agent, "working", HOLD, m.text);
  }

  // ---------- cards: from the room that made it to each room that takes it, along the corridors ----------
  const ROWS = [5.5, -5.5, -16.5], OUT = new THREE.Vector3(0, 2, 24);
  const at = (k) => { const d = DEPTS[k]; return d ? new THREE.Vector3(d.x, 2, d.z) : null; };
  function hqPath(a, b) {
    const pts = [a.clone()];
    const row = ROWS.reduce((best, z) => Math.abs(z - (a.z + b.z) / 2) < Math.abs(best - (a.z + b.z) / 2) ? z : best, ROWS[0]);
    if (Math.abs(a.x - b.x) > 1 && Math.abs(a.z - b.z) > 1) pts.push(new THREE.Vector3(a.x, 2.6, row), new THREE.Vector3(b.x, 2.6, row));
    else pts.push(a.clone().add(b).multiplyScalar(.5).setY(3.2));
    pts.push(b.clone());
    return new THREE.CatmullRomCurve3(pts, false, "centripetal");
  }
  function cardCanvas(m, { mark = null, big = false, struck = false } = {}) {
    const c = document.createElement("canvas"), W = big ? 640 : 320, H = big ? 300 : 180; c.width = W; c.height = H;
    const x = c.getContext("2d"), [bg, fg, kind] = CARD[m.card] || CARD.note;
    x.fillStyle = mark === "amber" ? "#c7883a" : bg; x.beginPath(); x.roundRect(4, 4, W - 8, H - 8, 18); x.fill();
    x.strokeStyle = "rgba(0,0,0,.25)"; x.lineWidth = 3; x.stroke();
    x.fillStyle = fg; x.globalAlpha = .7; x.font = `700 ${big ? 22 : 16}px Inter, system-ui`; x.fillText(kind, 20, big ? 40 : 30); x.globalAlpha = struck ? .55 : 1;
    x.font = `600 ${big ? 40 : 30}px Inter, system-ui`;
    const lines = wrapLines(x, m.card === "quote" ? `"${m.text}"` : m.text, W - 40, big ? 5 : 3);
    const lh = big ? 48 : 36, top = big ? 90 : 72;
    lines.forEach((l, i) => x.fillText(l, 20, top + i * lh));
    x.globalAlpha = 1;
    if (struck) { x.strokeStyle = "#d33"; x.lineWidth = big ? 5 : 3; lines.forEach((l, i) => { const y = top + i * lh - (big ? 11 : 8); x.beginPath(); x.moveTo(18, y); x.lineTo(22 + x.measureText(l).width, y); x.stroke(); }); }
    if (m.count > 1) { x.fillStyle = "#101520"; x.beginPath(); x.roundRect(W - 92, 12, 78, 36, 12); x.fill(); x.fillStyle = "#fff"; x.font = "700 22px Inter, system-ui"; x.fillText(`×${m.count}`, W - 80, 38); }
    return c;
  }
  function sprite(canvas, width) {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), transparent: true, depthTest: false, toneMapped: false }));
    s.scale.set(width, width * canvas.height / canvas.width, 1); s.renderOrder = 30;
    return s;
  }
  const dropSprite = (s) => { scene.remove(s); s.material.map?.dispose(); s.material.dispose(); };
  function fly(m, from, to) {
    if (ctx.where() !== "hq") return flyOnFloor(m, from, to);
    if (flights.length >= MAX_CARDS) return;
    const a = from ? at(from) : OUT.clone(), b = to ? at(to) : OUT.clone();
    if (!a || !b) return;
    const local = a.distanceTo(b) < 1, curve = local ? null : hqPath(a, b);
    const s = sprite(cardCanvas(m), 5); s.position.copy(a); s.userData.record = m.record; scene.add(s);
    flights.push({ s, curve, a, t: 0, dur: local ? 1.1 : Math.min(1.6, Math.max(.8, a.distanceTo(b) / 20)), to, kind: m.card, local });
    stats.cards++;
  }
  function flyOnFloor(m, from, to) {
    const f = ctx.floor(), room = ctx.where();
    if (!f || (from !== room && to !== room) || flights.length >= MAX_CARDS) return;
    const wp = (id) => f.stations[id]?.g.getWorldPosition(new THREE.Vector3()).add(new THREE.Vector3(0, 2.2, 0));
    const door = new THREE.Vector3(14, 2, 14), lead = wp(DEPTS[room].lead) || new THREE.Vector3(0, 2.2, 0);
    const a = from === room ? (wp(m.agent) || lead) : door, b = to === room ? (from === room ? new THREE.Vector3(-9, 4.4, -9) : lead) : door;
    const s = sprite(cardCanvas(m), 2.6); s.position.copy(a); s.userData.record = m.record; scene.add(s);
    flights.push({ s, curve: new THREE.CatmullRomCurve3([a, a.clone().add(b).multiplyScalar(.5).setY(5), b]), a, t: 0, dur: 1.1, to: null, kind: m.card });
    stats.cards++;
  }
  async function loadStuck() {
    try { stuckItems = (await api("/api/floor/stuck")).items; } catch { return; }
    if (stuckMark) { ctx.hq.remove(stuckMark); stuckMark = null; }
    if (!stuckItems.length) return;
    stuckMark = label(`Stuck · ${stuckItems.length}`, { size: 34, accent: "#f0b35e", prio: 3 });
    stuckMark.position.set(0, 1.4, 5.5); stuckMark.userData.stuck = true; ctx.hq.add(stuckMark);
  }
  function fallToStuck(m) {
    if (ctx.where() === "hq" && !reduced() && m.from) {
      const a = at(m.from), s = sprite(cardCanvas(m), 2.6); s.position.copy(a); scene.add(s);
      flights.push({ s, curve: new THREE.CatmullRomCurve3([a, new THREE.Vector3(a.x / 2, 3, (a.z + 5.5) / 2), new THREE.Vector3(0, .3, 5.5)]), a, t: 0, dur: 1.4, to: null, kind: "stuck" });
    }
    loadStuck();
  }
  function openStuck() {
    document.getElementById("floorstuck")?.remove();
    const w = document.createElement("div"); w.id = "floorstuck";
    w.style.cssText = "position:fixed;left:50%;top:14%;transform:translateX(-50%);width:min(520px,90vw);max-height:62vh;overflow:auto;background:#0d121b;border:1px solid #3a3f55;border-radius:14px;padding:16px 18px;z-index:60;color:#ece8df;font:14px Inter,system-ui";
    const head = document.createElement("div"); head.style.cssText = "display:flex;justify-content:space-between;margin-bottom:10px;font-weight:600"; head.textContent = `Stuck · ${stuckItems.length}`;
    const close = document.createElement("button"); close.textContent = "Close"; close.onclick = () => w.remove(); head.append(close); w.append(head);
    for (const i of stuckItems) { const a = document.createElement("a"); a.href = i.record; a.textContent = i.text; a.style.cssText = "display:block;padding:7px 0;border-top:1px solid #1e2534;color:inherit"; w.append(a); }
    document.body.append(w);
  }

  // ---------- the correction ripple: the numbers are the Deal desk's own ----------
  const wait = (s) => new Promise((ok) => setTimeout(ok, s * 1000));
  function pin(canvas, pos, width, secs) {
    const s = sprite(canvas, width); s.position.copy(pos); scene.add(s);
    props.push({ s, life: secs, age: 0, grow: true });
    return s;
  }
  function thread(a, b, color, secs) {
    const c = new THREE.QuadraticBezierCurve3(a, a.clone().add(b).multiplyScalar(.5).setY(7), b);
    const geo = new THREE.BufferGeometry().setFromPoints(c.getPoints(40)); geo.setDrawRange(0, 0);
    const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: .95, toneMapped: false, depthTest: false }));
    line.renderOrder = 28; scene.add(line); props.push({ line, life: secs, age: 0, draw: .7 });
  }
  function tick3D(pos, text, color, secs) { const s = label(text, { size: 34, color, prio: 4 }); s.position.copy(pos); scene.add(s); props.push({ s, life: secs, age: 0, label: true }); }
  async function playRipple(fact) {
    if (stats.ripples.some((r) => r.fact === fact)) return;
    let r;
    try { r = await api(`/api/floor/ripple/${fact}`); } catch (e) { console.warn("floor: ripple", e); return; }
    stats.ripples.push(r);
    if (document.hidden || reduced()) { (r.rooms || []).forEach((k) => ctx.flash(k, 0xf0b35e)); return counter(r); }
    if (ctx.where() !== "hq") { ctx.leave(); await wait(1.5); }
    const oldPos = new THREE.Vector3(-7.5, 9, 3), newPos = new THREE.Vector3(5.5, 9, 3), LONG = 9;
    const quote = { card: "quote", text: r.quote || "A customer changed what they said" };
    pin(cardCanvas(quote, { big: true }), newPos, 11, LONG);
    await wait(.5);
    pin(cardCanvas({ card: "quote", text: r.old?.map((o) => o.quote).join(" ") || "What they said before" }, { big: true, struck: true }), oldPos, 11, LONG);
    thread(oldPos, newPos, 0xe8c77a, LONG);
    await wait(.5);
    const comp = at("comp").setY(.6), lead = agent("comp");
    lead.preview = { kind: "compare", title: "Corrected", old: r.old?.[0]?.quote || "", new: r.quote || "", at: new Date() };
    setState("comp", "comparing", 7, "corrected"); dirty.add("comp");
    pulseTo(at("sales").setY(.6), comp, 0xff4040, 1.2); ctx.flash("comp", 0xff4040, 5 / 4);
    await wait(1.5);
    for (const k of (r.rooms || []).filter((x) => x !== "comp")) { thread(oldPos, at(k).setY(3), 0xf0b35e, 6.5); ctx.flash(k, 0xf0b35e); }
    for (let i = 0; i < r.withdrawn + r.sent_back && i < 4; i++) {
      const room = (r.rooms || []).filter((x) => x !== "comp")[i % Math.max(1, r.rooms.length - 1)] || "fin";
      pin(cardCanvas({ card: "task", text: "based on superseded fact" }, { mark: "amber" }), at(room).setY(5).add(new THREE.Vector3(-2 + i * .5, 0, 0)), 5, 6);
    }
    await wait(.5);
    for (let i = 0; i < r.approvals && i < 3; i++) pin(cardCanvas({ card: "stamp", text: "Approval rests on a replaced statement" }, { struck: true }), at("front").setY(5).add(new THREE.Vector3(i * 5 - 5, 0, 0)), 5, 5.5);
    await wait(.5);
    for (let i = 0; i < r.recalled && i < 3; i++) pin(cardCanvas({ card: "compliance", text: "Recalled" }), at("ops").setY(5).add(new THREE.Vector3(i * 5 - 5, 0, 0)), 5, 5);
    await wait(.5);
    for (const k of r.untouched || []) tick3D(at(k).setY(4.4), "✓ not affected", "#82d99f", 5);
    await wait(.5);
    counter(r);
  }
  function pulseTo(a, b, color, secs) {
    const m = new THREE.Mesh(new THREE.RingGeometry(.3, .8, 24), new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide, transparent: true, toneMapped: false, depthTest: false }));
    m.rotation.x = -Math.PI / 2; m.position.copy(a); m.renderOrder = 27; scene.add(m);
    props.push({ mesh: m, from: a, to: b, life: secs, age: 0 });
  }
  function counter(r) {
    document.getElementById("floorripple")?.remove();
    const w = document.createElement("div"); w.id = "floorripple";
    w.style.cssText = "position:fixed;left:50%;top:84px;transform:translateX(-50%);display:flex;gap:18px;align-items:center;background:rgba(13,18,27,.94);border:1px solid #e8c77a;border-radius:14px;padding:12px 18px;z-index:55;color:#ece8df;font:13px Inter,system-ui;box-shadow:0 12px 40px #000a";
    const rows = [["1", "sentence"], [r.rooms?.length || 0, "rooms alerted"], [r.withdrawn + r.sent_back, "tasks reopened"], [r.approvals, "approvals refused"], [r.recalled, "forms recalled"], [r.other, "other work touched"]];
    for (const [v, l] of rows) { const c = document.createElement("div"); c.style.textAlign = "center"; const b = document.createElement("b"); b.style.cssText = "display:block;font:600 24px Inter,system-ui"; b.textContent = v; c.append(b, l); w.append(c); }
    const x = document.createElement("button"); x.textContent = "×"; x.title = "Close"; x.style.cssText = "background:none;border:0;color:#8b92a3;font-size:18px;cursor:pointer"; x.onclick = () => w.remove(); w.append(x);
    document.body.append(w); w.dataset.counts = JSON.stringify(rows);
  }

  // ---------- the robots: poses toward a target, with the alive layer on top ----------
  function adopt(r) {
    const seed = seeded(r.id), rnd = (i) => ((seed * (i + 1) * 2654435761) >>> 0) / 2 ** 32;
    const hands = [0, 1].map((i) => { const m = new THREE.Mesh(handGeo, shellMat); m.scale.set(1, .7, 1.25); m.position.set(...REST[i]); m.castShadow = true; r.bot.add(m); return m; });
    r.fx = { hands, phase: rnd(0) * 6.28, drift: 6 + rnd(1) * 3, blinkAt: 3 + rnd(2) * 4, blink: 0, lean: 0, side: 0, yaw: 0, pitch: 0, shown: "idle", chip: null, chipKey: "", ringBase: r.ring?.material.color.clone() };
  }
  const stateFor = (r) => {
    const now = performance.now() / 1000;
    const ids = ctx.where() === "hq" ? Object.keys(live).filter((a) => deptOf(a) === deptOf(r.id)) : [r.id];
    let best = "idle", title = "";
    for (const id of ids) {
      const a = live[id];
      if (!a) continue;
      if (a.pending !== undefined && now - a.changed >= MIN_STATE) applyPending(a, now);
      if (a.state !== "idle" && now >= a.until) { a.state = "idle"; dirty.add(id); }
      if (PRIORITY.indexOf(a.state) < PRIORITY.indexOf(best)) { best = a.state; title = a.title; }
    }
    if (best === "idle" && ctx.isWaiting(r.id)) best = "waiting";
    return { state: best, title };
  };
  function chip(r, state, title) {
    const fx = r.fx, text = state === "idle" ? "" : `${CHIP[state]}${title ? " · " + title.slice(0, 28) : ""}`;
    if (text === fx.chipKey) return;
    fx.chipKey = text;
    if (fx.chip) { r.g.remove(fx.chip); fx.chip.material.map?.dispose(); fx.chip.material.dispose(); fx.chip = null; }
    if (!text) return;
    fx.chip = label(text, { size: 26, prio: 2, border: state === "waiting" ? "#f0b35e" : state === "blocked" ? "#f27d7d" : null });
    fx.chip.position.set(0, 2.5, 0); r.g.add(fx.chip);
  }
  function pose(r, dt, t) {
    if (!r.fx) adopt(r);
    const fx = r.fx, { state, title } = stateFor(r), p = POSE[state] || POSE.idle, k = 1 - Math.exp(-dt / ((BLEND[state] || .25) / 3));
    if (fx.shown !== state) { fx.shown = state; r.state = state; }
    chip(r, state, title);
    const breathe = 1 + (Math.sin(t * 1.96 + fx.phase) + 1) * .0075;
    if (r.body) { r.body.scale.set(breathe, 1, breathe); }
    fx.lean += (p.lean - fx.lean) * k; fx.side += (p.side - fx.side) * k;
    let yaw = p.yaw, pitch = p.pitch;
    if (state === "comparing") yaw = Math.sin(t * 2.4 + fx.phase) > 0 ? 15 : -15;
    if (state === "reading") pitch += Math.sin(t * .8 + fx.phase) * 2;
    if (state === "checking") pitch += Math.max(0, Math.sin(t * 5 + fx.phase)) * 3;
    fx.yaw += (yaw + Math.sin(t * (6.28 / fx.drift) + fx.phase) * (state === "idle" ? 8 : 1.5) - fx.yaw) * k;
    fx.pitch += (pitch - fx.pitch) * k;
    r.bot.rotation.x = fx.lean * D2R;
    if (!r.walk) r.bot.rotation.z = fx.side * D2R;
    if (r.headG) { r.headG.rotation.y = fx.yaw * D2R; r.headG.rotation.x = fx.pitch * D2R; }
    if (p.rise) r.bot.position.y += p.rise;
    fx.hands.forEach((h, i) => {
      const tgt = p.hands[i]; let y = tgt[1], x = tgt[0];
      if (state === "typing") y += (Math.sin(t * 26 + i * Math.PI + fx.phase) > 0 ? .02 : 0);
      if (state === "checking" && i === 1) y -= Math.max(0, Math.sin(t * 5 + fx.phase)) * .06;
      if (state === "waiting" && i === 1 && (t % 20) < 3) x += Math.sin(t * 6.28) * .05;
      h.position.lerp(new THREE.Vector3(x, y, tgt[2]), k);
    });
    if ((fx.blinkAt -= dt) <= 0) { fx.blink = .12; fx.blinkAt = 3 + ((seeded(r.id) + Math.floor(t * 10)) % 40) / 10; }
    fx.blink = Math.max(0, fx.blink - dt);
    (r.eyes || []).forEach((e) => { e.scale.y = fx.blink > 0 ? .12 : state === "reading" ? .55 : 1; });
    if (r.ring) {
      r.ring.material.emissiveIntensity = p.ringI * (state === "blocked" ? .7 + Math.sin(t * 3) * .3 : 1);
      const c = p.ring == null ? fx.ringBase : new THREE.Color(p.ring);
      r.ring.material.color.copy(c); r.ring.material.emissive.copy(c);
    }
    if (state === "fallback") (r.eyes || []).forEach((e) => { e.scale.y = .4; });
  }

  // ---------- monitors ----------
  function drawMonitor(st, x, W, H) {
    const a = live[st.id], p = a?.preview;
    if (!p) return false;
    const col = "#" + st.color.toString(16).padStart(6, "0"), state = a.state, name = AG[st.id]?.name || st.id;
    const dim = state === "idle";
    x.fillStyle = "#0b0f18"; x.fillRect(0, 0, W, H); x.fillStyle = col; x.fillRect(0, 0, W, 4);
    x.fillStyle = "#8b92a3"; x.font = "600 12px Inter, system-ui"; x.fillText(`${name} · ${p.title || ""}`.toUpperCase().slice(0, 46), 12, 22);
    x.globalAlpha = dim ? .62 : 1; x.font = "500 13px Inter, system-ui";
    if (p.kind === "compare") {
      const cw = (W - 34) / 2;
      x.fillStyle = "rgba(242,125,125,.14)"; x.fillRect(10, 32, cw, H - 62); x.fillStyle = "rgba(130,217,159,.14)"; x.fillRect(22 + cw, 32, cw, H - 62);
      x.fillStyle = "#f2b0b0"; x.font = "600 11px Inter, system-ui"; x.fillText("BEFORE", 16, 47); x.fillStyle = "#a9e6bd"; x.fillText("NOW", 28 + cw, 47);
      x.font = "500 13px Inter, system-ui"; x.fillStyle = "#ece8df";
      wrapLines(x, p.old, cw - 12, 5).forEach((l, i) => x.fillText(l, 16, 66 + i * 17));
      wrapLines(x, p.new, cw - 12, 5).forEach((l, i) => x.fillText(l, 28 + cw, 66 + i * 17));
    } else if (p.kind === "checklist") {
      let y = 46;
      for (const [i, l] of (p.lines || []).entries()) {
        if (y > H - 34) break;
        x.fillStyle = i ? "#82d99f" : "#f0b35e"; x.fillText(i ? "✓" : "●", 12, y); x.fillStyle = "#ece8df";
        const ws = wrapLines(x, l, W - 44, i ? 1 : 3); ws.forEach((w, j) => x.fillText(w, 30, y + j * 17)); y += ws.length * 17 + 5;
      }
    } else if (p.kind === "form") {
      let y = 44;
      for (const [k, v] of (p.fields || []).slice(0, 5)) {
        x.fillStyle = "#8b92a3"; x.font = "500 11px Inter, system-ui"; x.fillText(String(k).slice(0, 18), 12, y);
        x.fillStyle = v ? "#ece8df" : "#5d6476"; x.font = "500 13px Inter, system-ui"; x.fillText(String(v || "needs a person").slice(0, 32), 112, y); y += 21;
      }
      x.fillStyle = "#f0b35e"; x.font = "600 11px Inter, system-ui"; x.fillText("🔒 Submit stays with a person", 12, H - 34);
    } else {
      x.fillStyle = "#ece8df"; x.font = "500 14px Inter, system-ui";
      (p.lines || []).flatMap((l) => wrapLines(x, l, W - 24, 6)).slice(0, 6).forEach((l, i) => x.fillText(l, 12, 46 + i * 19));
    }
    x.globalAlpha = 1;
    x.fillStyle = state === "waiting" ? "#f0b35e" : dim ? "#5d6476" : "#5ccfb5"; x.font = "600 11px Inter, system-ui";
    const when = (a.done || p.at)?.toLocaleTimeString?.("en-GB", { hour: "2-digit", minute: "2-digit" });
    x.fillText(dim ? `done ${when || ""}` : (CHIP[state] || state), 12, H - 11);
    return true;
  }

  // ---------- each frame ----------
  let clockAt = performance.now();
  function animate(bots, dt, t, redraw) {
    const nowMs = performance.now(), real = Math.min(1, (nowMs - clockAt) / 1000), onHq = ctx.where() === "hq";
    clockAt = nowMs;
    for (const r of bots) pose(r, real, t);
    // at most a few screens a frame, and only the ones in the room being looked at
    let n = 0;
    const f = ctx.floor();
    if (f) for (const id of [...dirty]) { dirty.delete(id); const st = f.stations[id]; if (st?.canvas) { redraw(st); n++; } if (n >= MAX_REDRAW) break; }
    stats.redraws += n; stats.maxRedraw = Math.max(stats.maxRedraw, n);
    for (let i = flights.length - 1; i >= 0; i--) {
      const c = flights[i]; c.t += real / c.dur;
      const k = Math.min(1, c.t), e = k < .5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
      if (c.curve) c.curve.getPoint(e, c.s.position);
      else { c.s.position.copy(c.a).setY(2 + e * 3); c.s.material.opacity = 1 - e * e; }
      if (k >= 1) { dropSprite(c.s); flights.splice(i, 1); if (c.to) ctx.flash(c.to, null, .5); }
    }
    for (let i = props.length - 1; i >= 0; i--) {
      const p = props[i]; p.age += real;
      const left = p.life - p.age, fade = Math.min(1, Math.max(0, left / .6));
      for (const o of [p.s, p.line, p.mesh]) if (o) o.visible = onHq;
      if (p.s) p.s.material.opacity = fade;
      if (p.line) { p.line.geometry.setDrawRange(0, Math.floor(41 * Math.min(1, p.age / p.draw))); p.line.material.opacity = .95 * fade; }
      if (p.mesh) { const k = Math.min(1, p.age / p.life); p.mesh.position.lerpVectors(p.from, p.to, k); p.mesh.material.opacity = 1 - k * .3; }
      if (left <= 0) {
        if (p.s) { if (p.label) scene.remove(p.s); else dropSprite(p.s); }
        if (p.line) { scene.remove(p.line); p.line.geometry.dispose(); p.line.material.dispose(); }
        if (p.mesh) { scene.remove(p.mesh); p.mesh.geometry.dispose(); p.mesh.material.dispose(); }
        props.splice(i, 1);
      }
    }
    // room mood: light follows how many agents are really running
    const running = {};
    for (const [id, a] of Object.entries(live)) if (a.state !== "idle") { const k = deptOf(id); running[k] = (running[k] || 0) + 1; }
    for (const [k, room] of Object.entries(hqRooms)) if (room.light) { const n2 = running[k] || 0, want = n2 >= 3 ? .62 : n2 ? .5 : .34; room.light.intensity += (want - room.light.intensity) * Math.min(1, real * 3); }
  }
  function click(ray, ev) {
    const pick = [...flights.map((f) => f.s)];
    if (stuckMark) pick.push(stuckMark);
    const hit = ray.intersectObjects(pick, false)[0]?.object;
    if (!hit) return false;
    if (hit.userData.stuck) { openStuck(); return true; }
    if (hit.userData.record) location.href = hit.userData.record;
    return !!hit.userData.record;
  }

  connect(); loadStuck();
  return { animate, drawMonitor, click, stats, live, playRipple, take, reload: loadStuck };
}
