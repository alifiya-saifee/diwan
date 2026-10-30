// Talk to the Marketing lead: a side panel for typing or talking, with uploads. Used by the Studio and the Marketing floor.
// Talking: one click starts a conversation; the microphone streams to Muse Voice Transcribe, each finished sentence goes to
// the lead, the answer is spoken by the browser, and listening goes on (the microphone is held while it speaks) until Stop.
import { h, api, post, toast } from "./app.js";

const CSS = `
.mchat { position: fixed; top: 0; right: 0; bottom: 0; width: min(440px, 100vw); z-index: 60; display: flex; flex-direction: column;
  background: var(--bg-2, #0f141d); border-left: 1px solid var(--line, #273041); box-shadow: -12px 0 40px rgba(0,0,0,.35); color: var(--ink, #e8e4da);
  padding-top: env(safe-area-inset-top, 0px); padding-bottom: env(safe-area-inset-bottom, 0px); font-size: 14px; }
.mchat[hidden] { display: none; }
.mchat .mh { display: flex; align-items: center; gap: 8px; padding: 14px 16px; border-bottom: 1px solid var(--line, #273041); }
.mchat .mh b { flex: 1; font-size: 15px; }
.mchat .mh small { display: block; font-weight: 400; color: var(--muted, #9aa1b2); font-size: 12px; }
.mchat .msgs { flex: 1; overflow-y: auto; padding: 12px 16px; display: flex; flex-direction: column; gap: 10px; }
.mchat .m { max-width: 88%; padding: 8px 12px; border-radius: 12px; line-height: 1.45; white-space: pre-wrap; }
.mchat .m.person { align-self: flex-end; background: var(--gold-soft, #3a2f17); }
.mchat .m.lead { align-self: flex-start; background: var(--raise, #1a2130); border: 1px solid var(--line, #273041); }
.mchat .m.note { align-self: center; color: var(--muted, #9aa1b2); font-size: 12px; background: none; }
.mchat .yesno { display: flex; gap: 8px; margin-top: 6px; }
.mchat .up { border-top: 1px solid var(--line, #273041); padding: 10px 16px; display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.mchat .up[hidden] { display: none; }
.mchat .up .wide { grid-column: 1 / -1; }
.mchat .up input, .mchat .up select { width: 100%; min-width: 0; }
.mchat .bar2 { display: flex; gap: 8px; padding: 10px 16px; border-top: 1px solid var(--line, #273041); align-items: center; }
.mchat .bar2 input { flex: 1; min-width: 0; }
.mchat .live { padding: 6px 16px; font-size: 12.5px; color: var(--gold, #e3b95c); min-height: 22px; }
.mchat .voicerow { display: flex; flex-wrap: wrap; gap: 6px 8px; align-items: center; padding: 8px 16px; border-bottom: 1px solid var(--line, #273041); font-size: 12.5px; }
.mchat .voicerow select { flex: 1 1 160px; min-width: 0; }
.mchat .voicerow .hint { flex-basis: 100%; color: var(--muted, #9aa1b2); font-size: 11.5px; }
.mchat .talk.on { background: var(--bad, #b03a2e); color: #fff; }
`;

let root, session, getRef = () => null, ws = null, ctx = null, stream = null, speaking = false;

function el(id) { return root.querySelector(`#${id}`); }
function add(who, text, extra) {
  el("mc-msgs").append(h("div", { class: `m ${who}` }, text, ...(extra ? [extra] : [])));
  el("mc-msgs").scrollTop = 1e9;
}
function live(t) { el("mc-live").textContent = t || ""; }

function show(r) {
  const extra = r.pending ? h("div", { class: "yesno" },
    h("button", { class: "primary", onclick: (e) => { e.target.parentNode.remove(); send("Yes, go ahead."); } }, "Yes"),
    h("button", { onclick: (e) => { e.target.parentNode.remove(); send("No, leave it."); } }, "No")) : null;
  add("lead", r.reply, extra);
  if (r.upload) el("mc-up").hidden = false;
  if (ws) speak(r.reply);
}

async function send(text) {
  text = (text || "").trim(); if (!text) return;
  add("person", text);
  live("The Marketing lead is thinking…");
  try { show(await post("/api/marketing/chat", { session, text, ref: getRef() })); } catch (e) { add("note", e.message); }
  live(ws ? "Listening…" : "");
}

// The most natural voice this computer has: the downloadable "Premium"/"Enhanced" and neural voices sound like a person;
// the basic ones sound robotic. The person can pick another in the panel; the choice is remembered on this computer.
const QUALITY = [/premium/i, /enhanced/i, /natural|neural/i, /^google/i, /siri/i];
function voices() { return speechSynthesis.getVoices().filter((v) => /^en/i.test(v.lang)); }
function bestVoice() {
  let pick = "";
  try { pick = localStorage.getItem("mchat-voice") || ""; } catch {}
  const vs = voices();
  return vs.find((v) => v.name === pick) || QUALITY.map((q) => vs.find((v) => q.test(v.name))).find(Boolean)
    || vs.find((v) => /samantha|ava|allison|daniel|karen|serena/i.test(v.name)) || vs[0];
}
function fillVoices() {
  const sel = root && el("mc-voice"); if (!sel) return;
  const cur = bestVoice();
  sel.replaceChildren(...voices().sort((a, b) => QUALITY.findIndex((q) => q.test(b.name)) - QUALITY.findIndex((q) => q.test(a.name)))
    .map((v) => h("option", { value: v.name, selected: cur && v.name === cur.name }, `${v.name}${QUALITY.some((q) => q.test(v.name)) ? " ★" : ""}`)));
}
speechSynthesis.onvoiceschanged = fillVoices;

function speak(text) {
  speechSynthesis.cancel();
  // sentence by sentence, at a conversational pace: one long utterance runs flat and some voices cut it off
  const parts = text.match(/[^.!?]+[.!?]*\s*/g) || [text], v = bestVoice();
  speaking = true; live("Speaking…");
  parts.forEach((t, i) => {
    const u = new SpeechSynthesisUtterance(t.trim());
    if (v) u.voice = v;
    u.rate = 1.02; u.pitch = 1;
    if (i === parts.length - 1) u.onend = u.onerror = () => { speaking = false; live(ws ? "Listening…" : ""); };
    speechSynthesis.speak(u);
  });
}

async function talk() {
  if (ws) { stop(); return; }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
  } catch { toast("The microphone was not allowed. You can type instead."); return; }
  ctx = new AudioContext({ sampleRate: 16000 });
  const src = ctx.createMediaStreamSource(stream), proc = ctx.createScriptProcessor(4096, 1, 1);
  const q = new URLSearchParams({ session, ref: getRef() || "" });
  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/marketing/chat/audio?${q}`);
  ws.binaryType = "arraybuffer";
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.partial) live(`You: ${d.partial}`);
    if (d.heard) { add("person", d.heard); live("The Marketing lead is thinking…"); }
    if (d.reply) show(d);
    if (d.stop) setTimeout(stop, 2500);  // let it finish saying goodbye
  };
  ws.onclose = (e) => { if (e.reason) add("note", e.reason); stop(); };
  proc.onaudioprocess = (ev) => {
    if (ws?.readyState !== 1 || speaking) return;  // held while the lead speaks, so it doesn't hear itself
    const f = ev.inputBuffer.getChannelData(0), pcm = new Int16Array(f.length);
    for (let i = 0; i < f.length; i++) pcm[i] = Math.max(-1, Math.min(1, f[i])) * 0x7fff;
    ws.send(pcm.buffer);
  };
  src.connect(proc); proc.connect(ctx.destination);
  el("mc-talk").textContent = "Stop"; el("mc-talk").classList.add("on");
  live("Listening… just talk; say stop or press Stop to end.");
}

function stop() {
  if (ws && ws.readyState === 1) { ws.send("end"); ws.close(); }
  ws = null; ctx?.close(); ctx = null; stream?.getTracks().forEach((t) => t.stop()); stream = null;
  speechSynthesis.cancel(); speaking = false;
  if (root) { el("mc-talk").textContent = "Talk"; el("mc-talk").classList.remove("on"); live(""); }
}

async function upload() {
  const fs = el("mc-files").files; if (!fs.length) return toast("Pick a video or picture");
  const fd = new FormData(); fd.append("session", session); fd.append("ref", getRef() || "");
  for (const k of ["kind", "whose", "likes", "comments"]) fd.append(k, el(`mc-${k}`).value);
  for (const f of fs) fd.append("files", f);
  add("person", `Uploaded ${[...fs].map((f) => f.name).join(", ")}`);
  live("Reading it: the speech, the cuts and a few frames…");
  el("mc-up").hidden = true;
  const r = await fetch("/api/marketing/chat/upload", { method: "POST", body: fd });
  show(await r.json()); live(ws ? "Listening…" : "");
  el("mc-files").value = "";
}

function build() {
  const style = document.createElement("style"); style.textContent = CSS; document.head.append(style);
  root = h("aside", { class: "mchat", hidden: true, "aria-label": "Talk to the Marketing lead" },
    h("div", { class: "mh" }, h("b", {}, "Marketing lead", h("small", {}, "Marketing only: content, competitors, scripts, ads")),
      h("button", { id: "mc-talk", class: "talk", onclick: talk, title: "Talk: one click, then just speak" }, "Talk"),
      h("button", { onclick: close, "aria-label": "Close" }, "×")),
    h("div", { class: "voicerow" }, h("label", { for: "mc-voice" }, "Voice"),
      h("select", { id: "mc-voice", onchange: (e) => { try { localStorage.setItem("mchat-voice", e.target.value); } catch {} speak("This is how I sound now."); } }),
      h("span", { class: "hint" }, "★ sound most natural. More in System Settings → Accessibility → Spoken Content → Manage Voices.")),
    h("div", { class: "msgs", id: "mc-msgs" }),
    h("div", { class: "live", id: "mc-live", role: "status" }),
    h("div", { class: "up", id: "mc-up", hidden: true },
      h("input", { type: "file", id: "mc-files", class: "wide", accept: "video/*,image/*", multiple: true, "aria-label": "A reel, a post or a screenshot of its comments" }),
      h("select", { id: "mc-kind", "aria-label": "What it is" }, ...["", "reel", "post", "carousel", "comments screenshot"].map((k) => h("option", { value: k }, k || "What is it? (optional)"))),
      h("input", { id: "mc-whose", placeholder: "Whose? @account or us" }),
      h("input", { id: "mc-likes", placeholder: "Likes (if you know)", inputmode: "numeric" }),
      h("input", { id: "mc-comments", placeholder: "Comments (if you know)", inputmode: "numeric" }),
      h("button", { class: "primary wide", onclick: upload }, "Send it to the Marketing lead")),
    h("div", { class: "bar2" },
      h("button", { onclick: () => { el("mc-up").hidden = !el("mc-up").hidden; }, "aria-label": "Upload a file", title: "Upload a reel, a post or a screenshot of its comments" }, "＋"),
      h("input", { id: "mc-text", placeholder: "Ask, or say: search @account's posts from 1 to 15 Oct", onkeydown: (e) => { if (e.key === "Enter") { send(e.target.value); e.target.value = ""; } } }),
      h("button", { class: "primary", onclick: () => { send(el("mc-text").value); el("mc-text").value = ""; } }, "Send")));
  document.body.append(root);
  fillVoices();
}

function close() { stop(); root.hidden = true; }

export async function openChat(opts = {}) {
  if (opts.ref) getRef = opts.ref;
  if (!root) build();
  try { session = sessionStorage.getItem("mchat") || ""; } catch { session = ""; }
  if (!session) { session = `S${Date.now().toString(36)}`; try { sessionStorage.setItem("mchat", session); } catch {} }
  root.hidden = false;
  if (!el("mc-msgs").children.length) {
    const r = await api(`/api/marketing/chat/${session}`);
    for (const m of r.messages) add(m.who, m.text);
    if (!r.messages.length) add("lead", "Hi, I'm the Marketing lead. Ask me about our posts, competitors or scripts, upload a reel or post you want me to read, or press Talk and just speak.");
  }
  el("mc-text").focus();
}
