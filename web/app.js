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

export function header(active) {
  const pages = [["office3d.html", "Office"], ["index.html", "Nova"], ["sales.html", "Sales"], ["inbox.html", "Inbox"], ["studio.html", "Studio"], ["meeting.html", "Meeting"], ["deal.html", "Deals"], ["knowledge.html", "Knowledge"],
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
  if (SESSION.person || !SESSION.auth) paBox();
}

/** The chat box on every page: the signed-in person's own PA (Nova for the owner). */
function paBox() {
  const session = `page-${SESSION.person || "layla"}`, me = SESSION.person || "layla";
  const log = h("div", { class: "pa-log" });
  const input = h("input", { placeholder: "Ask your PA", "aria-label": "Ask your PA" });
  const panel = h("div", { class: "pa-panel", hidden: true });
  const add = (text, cls, kids = []) => { log.append(h("div", { class: `pa-m ${cls}` }, text, ...kids)); log.scrollTop = 1e9; };
  const send = async (text) => {
    if (!text.trim()) return;
    add(text, "me");
    try {
      const r = await post("/api/pa/say", { text, person: me, session });
      if (r.kind === "silent") return;
      add(r.text, r.kind || "", (r.options || []).map((o) => h("button", { onclick: () => send(o) }, o)));
    } catch (e) { add(e.message, "refused"); }
  };
  input.onkeydown = (e) => { if (e.key === "Enter") { const t = input.value; input.value = ""; send(t); } };
  const who = SESSION.owner ? "Nova" : `${SESSION.name || "Your"}'s PA`;
  panel.append(h("div", { class: "pa-head" }, who, h("button", { "aria-label": "Close", onclick: () => { panel.hidden = true; } }, "✕")), log, input);
  document.body.append(panel, h("button", { class: "pa-open", title: `Ask ${who}`, onclick: () => { panel.hidden = !panel.hidden; if (!panel.hidden) input.focus(); } }, "✦ Ask your PA"));
}

const TAB = { company: "Company", answer: "Approved answer", project: "Project", area: "Area", people: "People", brand: "Brand", listing: "Listing" };

/** The header search: knowledge and the catalog in one box (the same search Rania uses, but every status). "/" focuses it. */
function search() {
  const box = h("input", { type: "search", placeholder: "Search knowledge and listings", "aria-label": "Search knowledge and listings", autocomplete: "off" });
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
