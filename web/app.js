// Shared helpers for every Diwan screen. Text from the server always goes on the page through textContent.
export const NAMES = { layla: "Layla", omar: "Omar", priya: "Priya", joseph: "Joseph", ahmed: "Ahmed" };
export const AGENTS = {};

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

export async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
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
  const pages = [["office3d.html", "Office"], ["index.html", "Nova"], ["inbox.html", "Inbox"], ["studio.html", "Studio"], ["meeting.html", "Meeting"], ["knowledge.html", "Knowledge"],
                 ["graph.html", "Memory"], ["team.html", "Team"], ["settings.html", "Settings"]];
  const status = h("div", { class: "status" });
  api("/api/health").then((s) => {
    const p = (on, label) => h("span", { class: "pill" }, h("span", { class: `dot ${on ? "on" : ""}` }), label);
    status.append(p(s.providers.meta, "Muse Spark"), p(s.voice, "Voice"), p(s.whatsapp, "WhatsApp"),
                  p(s.providers.baseten || s.providers.fireworks || s.providers.modal, "Open weights"),
                  h("span", { class: "pill meta-badge" }, "Built with Meta Muse"));
  }).catch(() => {});
  const brand = h("a", { class: "brand", href: "office3d.html" });
  brand.innerHTML = LOGO;
  brand.append(h("span", { class: "word" }, "Diwan"), h("span", { class: "tag" }, "The office you can correct"));
  document.body.prepend(h("header", { class: "top" }, brand,
    h("nav", {}, pages.map(([href, label]) => h("a", { href, class: href === active ? "on" : "" }, label))), status));
}
