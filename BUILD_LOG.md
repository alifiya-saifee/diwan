# Build log

Everything in this repository was written during the Meta Global AI Developer Hackathon building period
(27 Oct to 4 Nov 2026). An earlier private prototype explored the idea; none of its code is in this repository.

## 27 Oct 2026

- Agent roster: 22 chartered agents (16 in the hackathon set). Each charter states the job, allowed sources, what the
  agent does alone, what needs a person, and what it never does.
- One output shape for every agent (the pack): verdict, exact quotes with their source, what is missing, next steps,
  proposed actions. Quotes not found word for word in their source are removed and recorded.
- Authority: every proposed action is allowed, sent to a person for approval, or refused, by the agent's charter.
  Anything a charter does not list is refused.
- Providers: Meta Model API, Baseten, Fireworks and Modal behind one client. Compliance agents run on open weights
  and never move to a hosted API unless that is switched on on purpose.
- Tapes: live replies can be recorded and replayed offline, always marked as recordings.
- Append-only event log; every event names its agent.

## 27 Oct 2026 (afternoon): Nova and the office graph

- Office graph rebuilt from the event log: people, deals, facts with exact quotes, tasks, approvals, deck slides and open
  cards, linked by who said what, who pays, what rests on which fact, and which fact replaced which. Rewinds to any event.
- Correction engine on the graph: compliance hears first, then only what rested on the old statement is withdrawn,
  sent back, or returned to the person who approved it. The execution guard refuses approvals resting on replaced facts.
- Two live statements that contradict each other go to the broker side by side; money work on that point waits.
- Nova answers from graph records (Muse Spark when plugged in, plain sentences otherwise), always citing record ids;
  an answer no record supports is not shown. Routes instructions through the right lead to a specialist (Form F clerk
  returns a field plan; Submit waits for Joseph). Refuses what only people do. Asks back when the deal or team is unclear.
  Briefs each person at 07:00 Dubai with what needs them, each line citing its records.

## 27 Oct 2026 (evening): the Scribe and live voice

- Meetings with a consent gate: nothing is heard or kept before the customer agrees.
- Scribe: each finished turn becomes facts with exact quotes (Muse Spark with a strict schema when plugged in; a rules
  reader for plain English otherwise: amounts in words or digits, who pays, family, income, deposits).
- One correction can replace several statements ("forget my brother" takes back both the brother's part and his
  paying). Hypothetical statements are kept but change nothing. An unclear correction asks the broker.
- Muse Voice Transcribe realtime client (diarization, partial and finished turns).

## 27 Oct 2026 (night): the front door

- Company knowledge (typed by a person: confirmed; pulled from a document: waits for confirmation) and listings in the
  office graph. A listing without a permit number is kept but never advertised.
- Rania, the receptionist on WhatsApp: greets, learns the buyer's brief, answers from listings and confirmed knowledge
  with the ref, books viewings in the broker's free slots (or offers the next free ones), hands over for payment
  methods, discounts, returns or anything outside her charter, without saying why.
- Every WhatsApp message goes through the same Scribe as meetings: a budget or "my brother will pay" typed at midnight
  is the same quoted fact, with the same corrections.
- Inbox semantics: a person replying takes the chat; Rania then only suggests replies; handing back resumes her. A
  model reply naming an amount not on any listing is not sent.
- WhatsApp Cloud API adapter: webhook verification, signature check, message parsing, sending.

## 27 Oct 2026 (night): screens

- Office: one box for Nova (questions and instructions), per-person briefings that can be read aloud, a live feed of
  every agent's work, and a one-click demo of Karim's correction.
- Inbox: WhatsApp-style conversations with Rania's replies and the records she used, take over / hand back, Rania's
  suggested replies while a person has the chat, the facts the Scribe heard, booked viewings, and a sandbox phone.
- Knowledge: company items (confirmed or waiting), paste-a-document, listings with advertised / not advertised.
- Memory graph: the deal's graph from the log, click any node for its record and links, rewind slider.
- Team: the org chart from the charters, each agent's charter and latest work.
- Meeting: consent first, typed turns or the microphone through Muse Voice Transcribe.

## 27 Oct 2026 (late): the Records team and the 3D office

- Records team: the Archivist files and finds contracts, invoices, bills and receipts; the Data analyst answers about
  sales, commission, spending and pipeline by counting records in code (a model never produces a number), listing every
  record it counted. No period named: it asks which. Nova hands these questions over visibly.
- Nova keeps a conversation's subject, so follow-ups ("and what changed?") stay on the deal just discussed.
- 3D office: a room per team and a named robot per agent, driven by the live event log. Work travels between agents as
  glowing orbs along the causal chain; each agent says what it did; Compliance flashes when a payment changes; filed
  documents fill the Records cabinets; the analyst walks to the archive to answer. Talk to Nova: she reads your
  briefing aloud, listens, answers by voice and keeps listening until you say thanks.

## 28 Oct 2026: the front desk as a PA

- Briefing time per person ("brief me at 9:30", or the time box). Thirty minutes before the earliest one, Nova does her
  rounds: every department lead hands her an update built from its records, and in 3D she walks room to room.
- Play briefing: a greeting by the clock, what needs you (cards, Lobby requests, late work, finished work), then each
  department's update (the owner hears all; others hear their own), then she listens.
- Lobby board: "Tell Priya I need the Karim review ready by this evening" is read back with the person and due time;
  only a yes posts it, through the Compliance lead to Priya. No deadline: she asks by when. Chased an hour before due,
  marked late after (the asker hears), and the asker hears when it is done. Shown on a board in the 3D lobby.

## 28 Oct 2026: the Inbox, AiSensy and Settings

- Inbox rebuilt as a working broker inbox: stage bar with counts; My inbox / All / New leads / Waiting; conversation rows
  with interest chips (buy or rent, area, size, budget, each from the buyer's own words or a fact), waiting time, who is
  replying, booked viewing, failed sends; chat with an AI auto-reply switch, stage picker, viewing and 24-hour-window
  banners, quick replies from confirmed knowledge, approved templates with variables and preview; a lead panel with
  what the office learned, replaced statements and open work.
- Stages move by themselves only forward (a stated budget: Qualified; a booked viewing: Viewing booked).
- WhatsApp from a known customer joins their existing deal instead of opening a new lead.
- AiSensy: session messages and templates through the Project API, template list, webhook with a private token,
  delivery failures shown on the message. Free text after 24 hours is refused; a template is offered instead.
- Settings: choose the WhatsApp line (AiSensy, Meta Cloud API, sandbox), enter keys (stored in the local .env, never
  shown again), test the AiSensy connection, copy the webhook address.

## 28 Oct 2026: autonomy, lessons and the content studio

- Autonomy per agent: autopilot, review key actions (anything a customer, portal or the public would see waits for a
  person), or review everything. It only ever takes authority away; the charter's "never" list holds at every level.
  Rania on review writes suggestions for the broker and books nothing. Set it on the Team page or by telling Nova.
- Lessons: "Rania, never mention the transfer fee" is read back, saved as a dated rule, added to the agent's
  instructions, and for "never" lessons enforced in code: a reply containing the phrase is not sent.
- Content studio: 26 chartered agents in five rooms and a library (research, planning, copy, art, publishing, script
  library), shown on the Team page and as a room in the 3D office. Chartered and visible; not yet working.

## 28 Oct 2026 (evening): departments you can walk into

- HQ floor shows departments only: each room has its lead, a wall screen with live numbers (agents, tasks in hand,
  waiting for people, latest work) and "N agents · enter". Work between departments flies between their leads.
- Enter a department and it becomes its own floor: the lead on a dais, the department's memory in front of it (the
  brand brain for Marketing, the rule book for Compliance…), its teams on pads clockwise in the order work moves, each
  agent at a desk whose screen shows its latest real work, team tags with what they are doing or how many things need
  a person, walls with live records, and a guided tour (arrow keys, Tour button).
- Marketing walkthrough: one listing goes research → planning → scripting → editing → publishing → owner approval,
  and the reel comment comes back to Rania in the Inbox room. Steps that need the Meta key (web research, other
  people's transcripts, covers) are sample work and marked so on every screen; the permit check, lanes, schedule
  rule, copy with the permit number, and Rania's reply are real.

## 28 Oct 2026 (night): the studio, for real

- Every marketing step now does real work or stops with a `step.blocked` saying exactly what it needs. The sample
  walkthrough is gone.
- Instagram Graph API: our posts and insights; competitors' public posts through business discovery; reel publishing
  after the owner approves (needs a public video address); comments by webhook to Rania, replies posted back.
- Analysis: KPIs per account (followers, posts a week, average likes and comments, engagement rate, formats, best day
  and hour, outliers at 2x the account's median) and "why their best posts win" as measured differences between
  outliers and other posts, each with example links. What Instagram does not give (others' views, reach, stories) is
  stated, not guessed. Competitor suggestions come from Muse Spark web search and wait for a person to confirm.
- Meta models: Muse Spark web search for trends (cited sources only), Voice Transcribe for outlier videos and our own
  takes, Muse Image for covers, Muse Spark for ideas and scripts (invented card ids and amounts not on the listing are
  rejected; a template is used instead and labelled).
- Footage upload: the take is checked against the script, captions are drawn and overlaid with ffmpeg, a cover frame
  is cut. Permit check counts only money as prices (unit and permit numbers are not prices).
- Studio page: competitors, KPI table, findings, top posts, the line step by step, what it made, footage, approval.
