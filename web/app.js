// Shared helpers for every Diwan screen. Text from the server always goes on the page through textContent.
export const NAMES = { layla: "Layla", omar: "Omar", hamza: "Hamza", nadia: "Nadia", priya: "Priya", joseph: "Joseph", ahmed: "Ahmed", maya: "Maya", rashid: "Rashid" };
export const AGENTS = {};

// Like h(), screens may pass null or false for "nothing here"; never print them as text.
for (const m of ["replaceChildren", "append"]) {
  const orig = Element.prototype[m];
  Element.prototype[m] = function (...kids) { return orig.apply(this, kids.filter((k) => k != null && k !== false)); };
}

export function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return el;
}

/** Who is signed in. Screens read this; the server decides what they get either way. */
/** Line icons for buttons and headings, in the text's own colour: one look on every page, instead of emoji. */
const ICONS = {
  phone: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z"/>',
  alert: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5M12 16.5v.01"/>',
  bell: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/>',
  calendar: '<rect x="3" y="4.5" width="18" height="17" rx="2"/><path d="M16 2.5v4M8 2.5v4M3 10h18"/>',
  mobile: '<rect x="6" y="2" width="12" height="20" rx="2.5"/><path d="M11 18h2"/>',
  chat: '<path d="M21 11.5a8.4 8.4 0 0 1-12.2 7.5L3 21l1.9-5.6A8.4 8.4 0 1 1 21 11.5z"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  flame: '<path d="M12 22c4 0 7-3 7-7 0-4-3-6.5-4-10-1.5 2-2 3.5-2 5-1.5-1-2.5-3-2.5-5C7 7.5 5 11 5 15c0 4 3 7 7 7z"/>',
  nocall: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1M5.2 13.1A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8"/><path d="M2 2l20 20"/>',
  bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  template: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
  mic: '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v4"/>',
  swap: '<path d="M7 7h13l-3-3M17 17H4l3 3"/>',
  check: '<path d="M4 12.5 9.5 18 20 6.5"/>',
};
export function icon(name, size = 15) {
  const s = document.createElement("span");
  s.className = "ic";
  s.innerHTML = `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ""}</svg>`;
  return s;
}
export const ICON_SVG = (name, size = 15) => icon(name, size).outerHTML;

export const SESSION = await fetch("/api/auth/me").then((r) => r.json()).catch(() => ({}));
if (SESSION.person && !SESSION.owner) {  // only the owner switches between people: everyone else is themselves
  document.documentElement.classList.add("staff");
  for (const k of ["diwan.inbox.as", "diwan.cal.as", "desk.as", "kn.as", "diwan.memory.as", "diwan.qualify.as", "diwan.settings.as"]) {
    try { localStorage.setItem(k, SESSION.person); } catch {}
  }
}

export async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (r.status === 401 && SESSION.auth) location.href = `/web/login.html?next=${encodeURIComponent(location.pathname)}`;
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || `${r.status}`);
  return body;
}
export const post = (path, data) => api(path, { method: "POST", body: JSON.stringify(data || {}) });

export function toast(text) {
  const t = h("div", { class: "toast", role: "status" }, text);
  document.body.append(t);
  setTimeout(() => t.remove(), 3500);
}

export const time = (iso) => new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

/** Live events from the log. Returns a stop function. */
export function follow(onEvents, after = 0) {
  let last = after, ws, stopped = false;
  const open = () => {
    ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/events?after=${last}`);
    ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.events?.length) { last = d.events.at(-1).id; onEvents(d.events); } };
    ws.onclose = () => { if (!stopped) setTimeout(open, 1500); };
  };
  open();
  return () => { stopped = true; ws.close(); };
}

export async function loadAgents() {
  for (const a of await api("/api/roster")) AGENTS[a.id] = a;
  return AGENTS;
}

export const who = (e) => AGENTS[e.agent]?.name || NAMES[e.actor] || (e.actor || "").replace(/^customer:/, "Customer ");

/** One plain line for any event. */
export function describe(e) {
  const c = e.content || {};
  switch (e.type) {
    case "fact.created": return `heard: "${c.quote}"${c.stance && c.stance !== "asserted" ? ` (${c.stance})` : ""}`;
    case "fact.superseded": return `${c.id} replaced by ${c.by}`;
    case "check.raised": return c.text;
    case "task.created": return `task ${c.id}: ${c.action}`;
    case "task.withdrawn": return `withdrew ${c.id}: ${c.reason}`;
    case "task.done": return `finished ${c.id}: ${c.reason}`;
    case "decision.needed": return `asks ${NAMES[c.who] || c.who}: ${c.question}`;
    case "question.asked": return `asks ${NAMES[c.to] || c.to}: ${c.text}`;
    case "review.returned": return `sent back ${c.draft}: ${c.reason}`;
    case "approval.given": return `${NAMES[c.approver] || c.approver} approved: ${c.action}`;
    case "approval.refused": return `refused ${c.id}: ${c.because}`;
    case "document.filed": return `filed ${c.kind}: ${c.title}`;
    case "review.passed": return `checked ${c.draft}: rests only on live words`;
    case "decision.made": return `answered ${c.card}: ${c.answer}${c.approval ? ` (${c.approval})` : ""}`;
    case "approval.requested": return `needs ${c.reviewer}: ${c.summary}`;
    case "execution.done": return `done: ${c.action}`;
    case "agent.pack": return c.pack.verdict;
    case "agent.refused": return `refused by its charter: ${c.because}`;
    case "agent.started": return `started: ${c.task}`;
    case "instruction.given": return `instruction: ${c.text}`;
    case "chat.received": return `WhatsApp: "${c.text}"`;
    case "chat.sent": return `replied on WhatsApp: "${c.text}"`;
    case "chat.suggested": return `suggested a reply: "${c.text}"`;
    case "chat.handover": return c.mode === "human" ? `chat handed to ${NAMES[c.by] || c.by}` : "chat back with Rania";
    case "lead.assigned": return `lead to ${NAMES[c.to] || c.to} (${c.why})`;
    case "attention.raised": return `${c.kind === "call" ? "call" : "reply"} needed from ${NAMES[c.who] || c.who}: ${c.reason}`;
    case "attention.overdue": return `${c.id} is overdue`;
    case "attention.cleared": return `${c.id} done: ${{ called: "called", messaged: "messaged", no_answer: "no answer", not_needed: `not needed (${c.note})` }[c.action] || c.action}`;
    case "attention.moved": return `the call moved from ${NAMES[c.from] || c.from} to ${NAMES[c.to] || c.to}`;
    case "lead.outcome": return `outcome: ${c.outcome.replace("_", " ")}${c.reason ? ` (${c.reason.replace("_", " ")})` : ""}`;
    case "lead.sweep": return `${NAMES[c.broker] || c.broker}'s list for today`;
    case "nova.arrived": return "came in";
    case "errand.drafted": return `drafted: ${c.title}`;
    case "errand.confirmed": return "approved a draft";
    case "errand.cancelled": return "cancelled a draft";
    case "pocket.started": return "meeting notes started";
    case "pocket.ended": return "meeting notes finished";
    case "lead.pooled": return `lead moved to the Pool: ${NAMES[c.from] || c.from} had not acted`;
    case "lead.claimed": return `${NAMES[c.to] || c.to} claimed the lead from the Pool`;
    case "notify.sent": return `told ${NAMES[c.to] || c.to}: ${c.text}`;
    case "notify.read": return `read ${c.ids?.length || 0} notices`;
    case "listings.synced": return `listing feed: ${c.in_feed} listings, ${c.added} new, ${c.changed} changed, ${c.off_market} off the market`;
    case "appointment.booked": return `booked a viewing of ${c.listing} with ${NAMES[c.broker] || c.broker}`;
    case "knowledge.added": return `knowledge: ${c.title}${c.confirmed ? "" : " (to confirm)"}`;
    case "knowledge.confirmed": return `confirmed ${c.id}`;
    case "listing.added": return `listing ${c.ref}: ${c.title}`;
    case "deal.opened": return `opened ${e.deal}: ${c.property}`;
    case "meeting.started": return `meeting started: ${c.title}`;
    case "consent.given": return "the customer agreed to the recording";
    case "utterance": return `${c.speaker}: "${c.text}"`;
    case "draft.made": return `${c.kind} v${c.version} drafted`;
    case "step.blocked": return `waiting: ${c.needs}`;
    case "post.seen": return `saw @${c.account}'s post: ${c.likes} likes, ${c.comments} comments${c.score ? ` (${c.score}x their usual)` : ""}`;
    case "board.pinned": return `pinned: ${c.title}`;
    case "content.made": return `made the ${c.kind} for ${c.ref}`;
    case "qa.passed": return `checked the ${c.kind} for ${c.ref}: passed${c.attempt > 1 ? ` on try ${c.attempt}` : ""}`;
    case "qa.failed": return `sent the ${c.kind} back to ${(c.returned_to || []).join(", ")}: ${(c.fails || [])[0]?.rule || "failed a check"}`;
    case "qa.escalated": return `the ${c.kind} for ${c.ref} failed review 3 times: raised to a person`;
    case "footage.added": return `footage uploaded for ${c.ref}`;
    case "lesson.added": return `new lesson: ${c.rule}`;
    case "lesson.removed": return `lesson ${c.id} removed`;
    case "autonomy.changed": return `set to ${c.level.replace("_", " ")}`;
    case "stage.changed": return `stage → ${c.stage}`;
    case "lobby.posted": return `posted ${c.id} for ${NAMES[c.to] || c.to}: ${c.text}`;
    case "lobby.done": return `${c.id} done`;
    case "lobby.late": return `${c.id} is late`;
    case "lobby.reminded": return `reminded about ${c.id}`;
    case "rounds.started": return "started the morning rounds";
    case "briefing.ready": return "briefing ready";
    default: return e.type;
  }
}

export const LOGO = `<svg viewBox="0 0 32 32" aria-hidden="true"><defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#f6e2ae"/><stop offset="1" stop-color="#c99a45"/></linearGradient></defs>
  <g fill="none" stroke="url(#lg)" stroke-width="2"><rect x="8" y="8" width="16" height="16" rx="1.5"/>
  <rect x="8" y="8" width="16" height="16" rx="1.5" transform="rotate(45 16 16)"/></g><circle cx="16" cy="16" r="3" fill="url(#lg)"/></svg>`;

/** The PA, one conversation on every page: what was said stays when you change page, and Live keeps her on the line. Live listens
 * with the browser's speech recognition, answers aloud, and listens again; it pauses while she speaks so she doesn't hear herself. */
export const pa = (() => {
  const me = () => SESSION.person || "layla", key = () => `diwan.pa.${me()}`;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let log = [], rec = null, on = false, state = "off", busy = false, playing = false, talking = null, turn = 0, held = null;
  try { log = JSON.parse(localStorage.getItem(key()) || "[]"); } catch { log = []; }
  const subs = new Set(), states = new Set(), hearing = new Set();  // hearing: the words as they are heard, before the sentence ends
  const push = (m) => { log.push(m); log = log.slice(-60); try { localStorage.setItem(key(), JSON.stringify(log)); } catch {} subs.forEach((f) => f(m)); };
  const show = (s) => { state = s; states.forEach((f) => f(s)); };
  const words = (s) => s.toLowerCase().match(/[\p{L}\p{N}']+/gu) || [];
  const MONTHS = { jan: "january", feb: "february", mar: "march", apr: "april", jun: "june", jul: "july", aug: "august", sep: "september", sept: "september", oct: "october", nov: "november", dec: "december",
    mon: "monday", tue: "tuesday", wed: "wednesday", thu: "thursday", fri: "friday", sat: "saturday", sun: "sunday" };
  const nth = (n) => n + (/1[123]$/.test(n) ? "th" : { 1: "st", 2: "nd", 3: "rd" }[n.slice(-1)] || "th");
  const spoken = (text) => {  // the words as the voice says them: "4 Nov" comes out as "the 4th of November"
    const s = new Set(["the", "of", "at", "and"]);
    for (const x of words(text)) { s.add(x); if (MONTHS[x]) s.add(MONTHS[x]); if (/^\d{1,2}$/.test(x)) s.add(nth(x)); }
    return s;
  };
  let recent = [];  // what she said in the last few seconds: the browser can hand it back late
  const echo = (t) => {  // her own voice coming back through the speakers: true, or what they said after it
    const now = Date.now();
    recent = recent.filter((r) => now < r.until);
    const w = words(t);
    if (!w.length) return false;
    for (const r of [...(talking ? [talking] : []), ...recent]) {
      if (!r.until || now > r.until) continue;
      if (w.filter((x) => r.words.has(x)).length / w.length >= 0.6) {  // mostly hers: keep only a tail that isn't
        let i = w.length;
        while (i > 0 && !r.words.has(w[i - 1])) i--;
        const tail = w.slice(i);
        return tail.length >= 1 && i >= 3 ? tail.join(" ") : true;
      }
    }
    return false;
  };
  const hush = () => { if (playing) window.speechSynthesis?.cancel(); };
  const hear = () => {  // the mic stays open while she talks and thinks, so she can be cut off
    if (!on || rec) return;
    rec = new SR(); rec.lang = "en-US"; rec.continuous = true; rec.interimResults = true;
    rec.onresult = (e) => {
      const r = e.results[e.results.length - 1], t = r[0].transcript.trim();
      if (!t) return;
      const back = echo(t);
      if (back === true) return;
      if (typeof back === "string") { if (r.isFinal) heard(back); return; }
      if (words(t).length >= 2) hush();
      hearing.forEach((f) => f(r.isFinal ? "" : t));
      if (r.isFinal) heard(t);
    };
    rec.onerror = (e) => { if (["not-allowed", "service-not-allowed", "audio-capture"].includes(e.error)) { stop(); toast("Allow the microphone for this site to talk to your PA"); } };
    rec.onend = () => { rec = null; if (on) setTimeout(hear, 250); };  // the browser ends it after a silence: she stays on the line
    try { rec.start(); if (!busy && !playing) show("listening"); } catch { rec = null; }
  };
  const mute = () => { if (rec) { rec.onend = null; try { rec.abort(); } catch {} rec = null; } };
  const loaded = () => new Promise((ok) => {  // the browser lists its voices a moment after the page opens
    if (!window.speechSynthesis || speechSynthesis.getVoices().length) { ok(); return; }
    const t = setTimeout(ok, 1000);
    speechSynthesis.addEventListener("voiceschanged", () => { clearTimeout(t); ok(); }, { once: true });
  });
  loaded();
  const talk = async (text) => {
    const clean = text.replace(/\b[A-Z]{1,2}\d+\b/g, "").replace(/https?:\S+/g, "").replace(/[*_#`>|~]/g, "").replace(/\s+/g, " ").trim();
    if (!clean || !window.speechSynthesis) return;
    await loaded();
    return new Promise((done) => {
      const words_ = clean.length > 500 ? `${clean.slice(0, 500).replace(/[^.?!]*$/, "")}` : clean;
      const mine = talking = { words: spoken(clean), until: Infinity };
      playing = true;
      let t, watchdog, started = false, tries = 0;
      const end = () => { clearTimeout(t); clearTimeout(watchdog); if (talking === mine) { playing = false; mine.until = Date.now() + 8000; } recent = [...recent, mine].slice(-3); done(); };
      t = setTimeout(end, Math.min(25000, clean.length * 90 + 4000));  // a browser that never says it finished can't leave her deaf
      const go = () => {
        const u = new SpeechSynthesisUtterance(words_), v = speechSynthesis.getVoices();
        u.voice = v.find((x) => /en/i.test(x.lang) && /natural|online|google/i.test(x.name)) || v.find((x) => /^en/i.test(x.lang)) || null;
        u.onstart = () => { started = true; };
        u.onend = end;
        u.onerror = (e) => {
          if (e.error === "not-allowed") {  // the page came back on its own and the browser wants a click before it makes a sound
            toast("Tap anywhere to hear Nova");
            const again = () => { removeEventListener("pointerdown", again); removeEventListener("keydown", again); speak(clean); };
            addEventListener("pointerdown", again); addEventListener("keydown", again);
          }
          end();
        };
        speechSynthesis.speak(u);
        watchdog = setTimeout(() => { if (!started && talking === mine && tries++ < 1) { speechSynthesis.cancel(); go(); } }, 2500);  // it was dropped: once more
      };
      go();
    });
  };
  let queue = Promise.resolve();  // one voice at a time: nothing she says cuts off what she's saying
  const speak = (text) => { const next = queue.then(() => talk(text)); queue = next.catch(() => {}); return next; };
  let order = Promise.resolve();  // answers come back in the order things were asked, however long each one took
  async function say(text, asked, voice = false) {
    text = (text || "").trim();
    if (!text) return null;
    const mine = ++turn, line = { from: "you", text };
    const before = order;
    let done;
    order = new Promise((ok) => { done = ok; });
    const history = log.slice(-12).map((m) => ({ who: m.from === "you" ? "You" : "Nova", text: m.text }));
    if (!voice) push(line);  // off the open mic it only shows once she knows it was meant for her
    busy = true; hush(); show(on ? "thinking" : "off");
    const wait = on ? setTimeout(() => { if (mine === turn && busy) speak("Let me check."); }, 3500) : null;  // Muse can take a while: she doesn't just go quiet
    let r;
    try { r = await post("/api/pa/say", { text: asked || text, person: me(), session: `pa-${me()}`, voice, history }); }
    catch (e) { r = e.message === "Failed to fetch" ? { kind: "answer", text: "I lost the line for a moment. Say that again?" } : { kind: "refused", text: e.message }; }
    clearTimeout(wait);
    await before;  // an earlier question is answered first
    try {
      if (r.kind !== "silent" && (r.text || "").trim()) {
        if (voice) push(line);
        push({ from: "pa", text: r.text, kind: r.kind, options: r.options || [], cites: r.cites || [], asked: text });
        if (on) { show("speaking"); await speak(r.spoken || r.text); }  // every answer is said: two or three questions in a row each get theirs
      }
    } finally { done(); }
    if (mine === turn) { busy = false; show(on ? "listening" : "off"); }
    return r;
  }
  const heard = (t) => {
    if (t.length < 2) return;
    if (/^(stop listening|go offline|end (the )?call|that'?s all|goodbye nova)\b/i.test(t)) { stop(); return; }
    const over = playing;
    hush();
    if (over && /^(stop|wait|hold on|one (sec|second|moment)|shut up|enough)\W*$/i.test(t)) return;
    say(t, undefined, true);
  };
  function start() {
    if (!SR) { toast("This browser can't listen. Use Chrome or Edge."); return; }
    on = true; try { localStorage.setItem(`${key()}.live`, "1"); } catch {}
    hear();
  }
  function stop() {
    on = false; try { localStorage.removeItem(`${key()}.live`); } catch {}
    mute(); window.speechSynthesis?.cancel(); show("off");
  }
  let timer = null;
  async function watch() {  // she speaks first: what she has chased, and what is still stuck
    if (busy) return;
    let seen = 0, own = 0;
    try { seen = +localStorage.getItem(`${key()}.seen`) || 0; own = +localStorage.getItem(`${key()}.own`) || 0; } catch {}
    let news = [];
    try { news = await api(`/api/pa/heads-up?person=${me()}&after=${seen}&after_private=${own}`); } catch { return; }
    for (const m of news) {
      try { localStorage.setItem(`${key()}.${m.private ? "own" : "seen"}`, m.id); } catch {}
      push({ from: "pa", text: m.text, kind: "answer", options: [], cites: [] });
      if (on && !busy) { show("speaking"); await speak(m.text); if (!busy) show("listening"); }
    }
  }
  const resume = () => {
    try { if (localStorage.getItem(`${key()}.live`)) start(); } catch {}
    if (!timer) { timer = setInterval(watch, 60000); setTimeout(watch, 4000); }
  };
  return { say, start, stop, resume, push, get log() { return log; }, get state() { return state; }, get live() { return on; }, subs, states, hearing,
           clear() { log = []; try { localStorage.removeItem(key()); } catch {} } };
})();

export function header(active) {
  const pages = [["office3d.html", "Office"], ["index.html", "Nova"], ["personal.html", "My WhatsApp"], ["sales.html", "Sales"], ["inbox.html", "Inbox"], ["studio.html", "Studio"], ["meeting.html", "Meeting"], ["deal.html", "Deals"], ["lobby.html", "Lobby"], ["knowledge.html", "Knowledge"],
                 ["graph.html", "Memory"], ["team.html", "Team"], ["settings.html", "Settings"]].filter(([href]) => !SESSION.pages || SESSION.pages.includes(href));
  const status = h("div", { class: "status" });
  api("/api/health").then((s) => {
    const p = (on, label) => h("span", { class: "pill" }, h("span", { class: `dot ${on ? "on" : ""}` }), label);
    status.append(p(s.providers.meta, "Muse Spark"), p(s.voice, "Voice"), p(s.whatsapp, "WhatsApp"),
                  p(s.providers.baseten || s.providers.fireworks || s.providers.modal, "Open weights"),
                  h("span", { class: "pill meta-badge" }, "Built with Meta Muse"));
  }).catch(() => {});
  const brand = h("a", { class: "brand", href: SESSION.home || "office3d.html" });
  brand.innerHTML = LOGO;
  brand.append(h("span", { class: "word" }, "Diwan"), h("span", { class: "tag" }, "The office you can correct"));
  const top = h("header", { class: "top" }, brand,
    h("nav", {}, pages.map(([href, label]) => h("a", { href, class: href === active ? "on" : "" }, label))), search(), status);
  top.insertBefore(h("button", { class: "hsbtn", "aria-label": "Search", onclick: () => { top.classList.toggle("searching"); top.querySelector(".hsearch input").focus(); } }, "Search"), status);
  if (SESSION.auth && SESSION.person) top.append(h("button", { class: "signout", title: `Signed in as ${SESSION.name}, ${SESSION.role}`, onclick: async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    location.href = "/web/login.html";
  } }, `${SESSION.name} · Sign out`));
  document.body.prepend(top);
  if (SESSION.person || !SESSION.auth) {
    const pill = h("button", { class: "live-pill", hidden: true, title: "End the call", onclick: () => pa.stop() });
    const paint = (s) => { pill.hidden = s === "off"; pill.textContent = { listening: "Nova · listening", thinking: "Nova · thinking", speaking: "Nova · speaking" }[s] || ""; pill.dataset.s = s; };
    pa.states.add(paint); top.insertBefore(pill, status); pa.resume();
  }
  // the Office and Nova pages have the PA built in: a second box on top of it would only confuse
  if ((SESSION.person || !SESSION.auth) && !["office3d.html", "index.html"].includes(active)) paBox();
}

/** The chat box on every page: the signed-in person's own PA (Nova for the owner). */
function paBox() {
  const log = h("div", { class: "pa-log" });
  const input = h("input", { placeholder: "Ask your PA", "aria-label": "Ask your PA" });
  const panel = h("div", { class: "pa-panel", hidden: true });
  const add = (m) => { log.append(h("div", { class: `pa-m ${m.from === "you" ? "me" : m.kind || ""}` }, m.text, ...(m.options || []).map((o) => h("button", { onclick: () => pa.say(o) }, o)))); log.scrollTop = 1e9; };
  pa.log.forEach(add); pa.subs.add(add);
  let live = null;
  pa.hearing.add((t) => { if (!t) { live?.remove(); live = null; return; } live ??= log.appendChild(h("div", { class: "pa-m me interim" })); live.textContent = `${t} …`; log.scrollTop = 1e9; });
  input.onkeydown = (e) => { if (e.key === "Enter") { const t = input.value; input.value = ""; pa.say(t); } };
  const who = SESSION.owner ? "Nova" : `${SESSION.name || "Your"}'s PA`;
  panel.append(h("div", { class: "pa-head" }, who, h("span", {}, h("button", { title: "Keep her on the line: talk without clicking", onclick: () => (pa.live ? pa.stop() : pa.start()) }, "🎙 Live"), " ",
    h("button", { "aria-label": "Close", onclick: () => { panel.hidden = true; } }, "✕"))), log, input);
  document.body.append(panel, h("button", { class: "pa-open", title: `Ask ${who}`, onclick: () => { panel.hidden = !panel.hidden; if (!panel.hidden) input.focus(); } }, "✦ Ask your PA"));
}

const TAB = { company: "Company", answer: "Approved answer", project: "Project", area: "Area", people: "People", brand: "Brand", listing: "Listing" };

/** The header search: knowledge and the catalog in one box (the same search Rania uses, but every status). "/" focuses it. */
function search() {
  const box = h("input", { type: "search", placeholder: "Search", "aria-label": "Search knowledge and listings", title: "Search knowledge and listings (press /)", autocomplete: "off" });
  const res = h("div", { class: "hresults", hidden: true });
  let timer, seq = 0;
  const row = (x) => h("a", { href: x.listing ? `catalog.html?q=${encodeURIComponent(x.listing.ref)}` : `knowledge.html?tab=${x.tab}&q=${encodeURIComponent(x.title)}` },
    h("span", { class: "chip" }, TAB[x.tab] || x.tab), !["confirmed", "available"].includes(x.status) ? h("span", { class: "chip warn" }, x.status) : null, " ",
    h("strong", {}, x.listing ? `${x.listing.ref} · ${x.title}` : x.title), h("div", { class: "small muted" }, x.text.slice(0, 140)));
  const go = async () => {
    const q = box.value.trim(), n = ++seq;
    if (!q) { res.hidden = true; return; }
    const r = await api(`/api/search?q=${encodeURIComponent(q)}&k=10`).catch(() => ({ items: [] }));
    if (n !== seq) return;
    res.replaceChildren(...(r.items.length ? r.items.map(row) : [h("div", { class: "small muted", style: "padding:12px" }, `Nothing found for "${q}".`)]));
    res.hidden = false;
  };
  box.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(go, 150); });
  box.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { res.hidden = true; box.blur(); box.closest("header")?.classList.remove("searching"); }
    if (e.key === "Enter") res.querySelector("a")?.click();
  });
  document.addEventListener("click", (e) => { if (!e.target.closest(".hsearch, .hsbtn")) { res.hidden = true; document.querySelector("header.top")?.classList.remove("searching"); } });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !e.target.closest("input, textarea, select, [contenteditable]")) { e.preventDefault(); box.focus(); }
  });
  return h("div", { class: "hsearch" }, box, res);
}
