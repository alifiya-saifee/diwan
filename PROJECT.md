# Diwan: the brokerage office you can correct

Diwan is an office of AI agents for a Dubai real-estate brokerage. Every agent has a written charter, they all share one
memory, and they work across WhatsApp, Instagram, meetings and the back office. People stay in charge of anything that
is legal, financial or public.

What makes it different: **when a customer changes their story, the whole office changes with it.** Nothing built on
the old statement survives without a person seeing it.

This document covers the problem, the idea, every department and agent, how the work flows, where a person must say
yes, and what is built and tested today versus what is still planned.

---

## 1. The problem

A Dubai brokerage runs on conversations. A buyer tells the broker one thing in a meeting, another thing on WhatsApp at
11 PM, and corrects themselves a week later: *"Actually, forget my brother. I'll pay it all myself."*

That one sentence should change a lot of work:

- **Compliance:** a third-party payer was being screened. Now the source of funds is the buyer's own, which needs
  different proof.
- **Finance:** an expected payment "from the brother, by bank transfer" no longer exists.
- **Operations:** the Form F draft names the wrong payer.
- **Sales:** the deck for the next meeting quotes the old plan.
- **Approvals:** a manager may already have approved something based on the old story.

Today that change lives in one broker's head. The deck goes out wrong, the compliance file is stale, and a payment is
chased from the wrong person. Nobody does anything wrong on purpose; the office simply has no shared memory that
notices when a fact is replaced.

Around that core problem sit the daily costs of running a brokerage:

- **Enquiries at all hours.** WhatsApp messages at night go unanswered, or a junior answers without the facts.
- **Owners can't see the office.** "What did we sell last month?" means asking three people and a spreadsheet.
- **Delegation leaks.** "Tell Priya I need the Karim review by this evening" gets lost in chats.
- **Marketing is expensive and guesswork.** Brokers post when they remember to, copy what competitors do without
  knowing why it worked, and pay for videos before anyone has agreed what they should say.
- **The law is strict.** Every property ad needs its permit number. Payment changes have compliance duties. An AI that
  submits, pays or promises returns on its own is a liability.

## 2. Who it is for

- **The owner** (in the demo, Layla): sees the whole office, gets a morning briefing, approves what matters.
- **Brokers** (Omar): get viewings booked, chats handed over, film lists for listings.
- **Compliance, finance and operations staff** (Priya, Ahmed, Joseph): get prepared work they check and submit.
- **The Marketing manager** (Maya): picks scripts, asks for changes, approves before anything costly happens.
- **Customers:** get fast, accurate answers on WhatsApp and Instagram, from confirmed listings only.

All names and records in the demo are fictional.

## 3. The idea in one picture

```
 customers ── WhatsApp / Instagram ──▶  Rania (receptionist) ─┐
 meetings  ── live transcript ───────▶  Scribe (facts)        ├──▶  ONE MEMORY  ◀──  every department reads and writes
 staff     ── "tell Priya..." ───────▶  Nova (chief of staff) ┘    (append-only event log → knowledge graph)
                                                                      │
              Sales · Operations · Finance · Compliance · Review · Records · Marketing
                                                                      │
                                         a person approves anything legal, financial or public
```

Three principles hold everywhere:

1. **One memory, never edited.** Everything that happens is an event in an append-only log; the database itself refuses
   updates and deletes. The knowledge graph is rebuilt from the log, so the office can be rewound to any moment.
2. **Every claim has its source.** A fact carries the speaker's exact words and where they were said. An agent's answer
   cites record ids; a quote that doesn't appear in its source is rejected.
3. **Agents have charters, and the code enforces them.** Each agent's charter says what it may do alone, what it may
   only propose for a person, and what it must never do. Anything outside the charter is refused and logged.

## 4. The core moment: a correction

In a meeting, Karim says: *"Actually, forget my brother. I'll pay it all myself."*

1. The **Scribe** records the new fact with his exact words and links it to the statement it **replaces**.
2. **Compliance is told first.** The payer changed, so the third-party screening and source-of-funds view are flagged.
3. **Dependent work is withdrawn.** The expected payment from the brother is withdrawn, not silently kept.
4. **Stale approvals are refused.** Anything approved on the old story becomes a decision for a person, and executing it
   is blocked.
5. **Review sends back drafts.** A deck slide built on the replaced fact is returned to the Deck builder.
6. **Nova can explain it.** Ask "Who is paying for Karim?" and she answers from the live fact, citing it.

The old statement is never deleted. It is marked replaced, and its history stays visible in the memory graph.

## 5. The departments and agents

51 agents in eight departments. Each has a charter (job, inputs, sources, output, trigger, reviewer, what it does when
something is missing, what it may do alone, what needs a person, what it must never do).

**Status, as of 28 Oct 2026:**
- **Built:** works today without keys (rules and templates), and uses a model when one is connected.
- **Live model:** runs on a model.
- **Planned:** has a charter, but the work isn't built yet.

### Front desk

| Agent | What it does | A person must |
|---|---|---|
| **Nova**, chief of staff | Morning briefing at each person's chosen time, after doing "rounds" of every department. Answers questions from the records (citing them), routes questions to the right lead, puts jobs on the Lobby board with a read-back ("So: Priya, 'The Karim review', due Wed 6 PM. Shall I send it?"), chases late cards, and learns lessons and autonomy settings by voice or text. | — |
| **Rania**, receptionist (sits in Sales) | Answers WhatsApp and Instagram comments day and night from confirmed listings and company knowledge. Gives prices, matches a buyer's brief to listings, books viewings in the broker's free slots (offering the nearest free times when one is taken), and hands the chat to a person on request or whenever it isn't hers to answer (cash, discounts, crypto, returns). Respects WhatsApp's 24-hour rule. | Take over the chat at any time |

**The Lobby board:** jobs Nova handed to people, with deadline, owner, reminders before the deadline and a "late" mark
after it.

### Sales

| Agent | What it does | Status |
|---|---|---|
| Sales lead | Makes sure every meeting becomes facts, a deck and follow-ups | Built |
| **Scribe** | Turns each finished sentence into facts with the exact words, and notices when one replaces another | Built |
| Rania | (above) | Built |
| Deck builder | Builds the next meeting's deck from live facts only; every slide remembers its facts | Built (live model) |
| Follow-up drafter | Bilingual meeting summary and document requests | Planned |

### Operations

| Agent | What it does | Status |
|---|---|---|
| Operations lead | Turns agreed terms into the paperwork sequence | Built |
| **Form F clerk** | Fills Form F on the portal from live facts and **stops before Submit** | Built |
| Transfer tracker | NOC, trustee, transfer documents | Planned |

### Finance

| Agent | What it does | Status |
|---|---|---|
| Finance lead | What money is expected, received and owed | Built |
| **Payment tracker** | Each expected payment is tied to the exact words it came from, and withdrawn when they're replaced | Built |
| Invoice clerk | Reads supplier invoices, checks VAT/TRN, holds duplicates | Planned |

### Compliance

| Agent | What it does | Status |
|---|---|---|
| Compliance lead | Receives every payer change first; prepares what the law requires | Built |
| Screening analyst | Screens every party, including third-party payers, against sanctions/PEP lists | Built |
| Source-of-funds analyst | Does the deal size fit what the customer said they earn and own? Asks for missing proof | Built |
| Report drafter | Drafts the cash/goAML report; **a person files it** | Built |

Compliance never decides suspicion. It prepares the file; the compliance officer decides.

### Review (independent of every team)

| Agent | What it does | Status |
|---|---|---|
| Review | Checks work against what is true now, before a person sees it | Built |
| Fact checker | Sends back any draft built on a replaced statement | Built |
| Devil's advocate | Argues against the money story, and lists what would prove it wrong | Planned |

### Records

| Agent | What it does | Status |
|---|---|---|
| Records lead | Keeps every document filed and answers business questions from the records | Built |
| Archivist | Files and finds contracts, invoices, bills, receipts and forms | Built |
| Data analyst | "Sales last month: 3 closed, AED 7.85M, AED 157k commission", computed from the records, never estimated | Built |

### Marketing: the content studio (29 agents)

Turns listings into short videos that bring enquiries, and hands every enquiry to Rania and Sales. It is organised like
a real short-form content team, in six rooms plus a library.

| Room | Lead | Agents | What it does |
|---|---|---|---|
| **Research** | Researcher | Trend scout, Competitor watch, Transcript reader | Finds what works: competitor posts scored against their own usual, rising formats with sources, transcripts of the top videos |
| **Planning** | Strategist | Idea generator, Lane balancer, Film list | Picks the idea, keeps the content mix balanced, writes the broker's shot list |
| **Scripting** | Copywriter | Script writer, Video check, Playbook writer | 2–3 scripts on different angles, each checked; checks the filmed take against the script; turns wins into playbook entries |
| **Production** | Producer | Shoot coordinator, AI video producer | The broker films from the list, or an AI presenter (HeyGen) reads the approved script |
| **Editing** | Art director | Captions, Remix, Content writer | Captions burned in from what was said, the post text with the permit number |
| **Publishing** | Publisher | Thumbnail, Permit checker, Scheduler, Cross-publisher | Covers, the legal gate, the best time to post, versions for each platform |
| **Library** | Script library | Playbook, Brand brain, Positioning | What the team writes from: brand knowledge, lessons, approved scripts, playbook (Positioning is planned) |

All marketing agents except Positioning are built and tested end to end in a browser (section 9).

## 6. How the marketing studio works, step by step

1. **Listing in.** A listing without a permit number stops here. Dubai requires the permit on every ad.
2. **Research.**
   - Competitor watch reads competitors' recent posts (Instagram business discovery, or a spreadsheet of real posts
     until Instagram is connected). It scores each post as likes plus comments divided by that account's median; 2x or
     more is an outlier.
   - It explains *why* only with measured differences: a feature that appears in outliers at least 25 points more
     often than in the rest, with links to the example posts.
   - The trend scout keeps only trends with a source. The transcript reader pulls the hook and beats from the top video.
3. **Choose the angles (strategy).** Each angle (price reveal, walk-through, lifestyle, investor facts, market check) is
   measured on *our own* posts against *our* median:

   | Status | Rule | Action |
   |---|---|---|
   | Winning | last 2 posts at 1.2x our median or more | keep it, script it first |
   | Fading | it worked, then fell 3 times in a row and is under our median | shift away |
   | Resting | last 2 posts under 0.8x our median | stop for 30 days |
   | Untested | fewer than 2 posts | candidate for the explore slot |

   Up to 2 scripts come from what works (ours first, then competitors' outliers) and **1 always explores**, so the
   account never rides one idea until it dies.
4. **Write 2–3 scripts.** One per angle: a hook of 12 words or fewer, 5–8 lines, English and Arabic, and only the
   listing's own price. No promised returns. Each is checked by the Copywriter before it's offered.
5. **The Marketing manager picks one, or asks for a change** in plain words ("make the hook shorter, sea view first").
   Only that script is rewritten, checked again and offered again. **Nothing that costs filming time, HeyGen credits,
   editing or image generation starts before a pick.**
6. **Footage.** The broker gets the shot list, or a person clicks "Make AI video" and confirms that the person in the
   avatar agreed to it; the consent is recorded with the footage.
7. **Edit.** The take is transcribed and compared with the script (lines that drifted are named). Captions are drawn
   and overlaid at the time each was said. Post text includes the permit number. Covers are made.
8. **Permit gate.** Permit present, only the listing's price, no banned promises. A hold is traced to whoever caused it:
   if the bad price came from the script, the Script writer fixes it, not the Content writer who noticed.
9. **Schedule and format.** The best hour from our history (or the evening default, said so), cut to each platform's
   limit.
10. **The owner approves publishing.** Then the reel is posted. Comments on it come to Rania like WhatsApp messages.

### Supervision: who checks, who fixes, when a person is told

- Every piece of work is checked by its room lead **the moment it's made**, against written acceptance rules. A rule
  that can't run counts as a failure, never a pass.
- A failure goes back to the agent who made it, with the rule, what was found and the fix. It gets up to two more tries.
- After the third failure, the Marketing lead raises it to the owner with every reason: fix it myself, accept as is, or
  stop this reel.
- A correction a person makes can become a **lesson** ("Script writer, never mention service charges"). Lessons go into
  that agent's instructions, and "never" lessons are enforced in code.
- **Autonomy per agent:** autopilot, review key actions, or review everything.

### KPIs

Each agent has targets, like a person's, measured from the log. A few examples:

- Competitor watch: 100% of competitors covered; at least 1 outlier a week.
- Script writer: 90% or more pass the first check; 80% or more approved without being sent back.
- Content writer: 100% of posts carry the permit number.
- Publisher: 100% published only after owner approval.

All of them are on the Studio page and in the handbook.

## 7. Where a person must say yes

Agents never hold portal or bank credentials. A person always:

- **submits** Form F (the clerk stops before Submit),
- **pays** or approves an expected payment,
- **files** a compliance report,
- **picks the script** before money is spent on video,
- **confirms consent** before an AI face or voice is used,
- **approves publishing** of every post,
- **decides** anything a correction made stale.

## 8. Cost: not paying twice, and a cap

- **Cache:** an identical request (same agent, prompt and format) is answered from its recording at no cost.
- **Ledger:** every live model call is recorded with its tokens and an estimated price, and every cache hit with what it
  saved. Shown on the Studio page.
- **Cap:** at the monthly budget (`DIWAN_BUDGET_USD`, default $25), live calls stop and agents use rules and templates,
  saying so.
- **Order of spend:** research and scripts cost cents. Filming time and HeyGen (paid, about $1 a minute, no free API
  credits) only start after a person picks a script.
- **Models:**
  - Meta's Muse Spark is first.
  - NVIDIA's free Muse Glimmer endpoint stands in during development (fictional data only).
  - Open-weight hosts (Baseten, Fireworks, Modal) run the open tier.
  - Every agent falls back to rules when no model is available, and says so.

## 9. The screens

- **Office (3D):**
  - An HQ of department rooms. Click a room to enter its floor, where its whole team works at desks.
  - Agents show speech bubbles of their latest work; work travels between desks, and room leads walk to the desk
    whose work they are checking.
  - Each floor has a "brain" (Brand brain, Deal memory, Archive, Ledger, Rule book…). Click it to see exactly what that
    department remembers, straight from the knowledge graph.
  - The walls show real listings and competitor posts. Where there are none, the wall says what's missing instead of
    showing samples.
  - Marketing has a Production recording set whose REC light glows while a video is made.
- **Nova:** talk or type; briefings, questions, delegation.
- **Inbox:** WhatsApp and Instagram conversations with stages (New → Won/Lost), takeover, templates, quick replies,
  and a sandbox phone for testing.
- **Studio:** competitors, KPIs, why their posts win, what to post next, the line step by step, script choices,
  footage, approvals, spend.
- **Meeting:** live transcription with a consent gate; facts appear as people speak.
- **Knowledge / Memory / Team / Settings:**
  - Knowledge: company knowledge cards.
  - Memory: the graph and its history.
  - Team: autonomy and lessons per agent.
  - Settings: AiSensy, WhatsApp Cloud API, Instagram, HeyGen and Meta keys (values never shown, only whether set).

## 10. How it is verified

- **144 unit tests** and an **evaluation suite of 78 cases** across Scribe, Rania, Nova, the correction engine, Lobby,
  Records and the Studio (78/78 in rules mode).
- **Browser runs (Playwright)** drive the real screens the way a person would, twice each on one server:
  - **Office flow:** a customer messages the sandbox WhatsApp line and Rania books a viewing; a broker takes over and
    replies, then hands back; a lesson is taught on the Team page and kept in the next reply; an Instagram comment
    arrives; Nova reads a job back, the Lobby card appears, and she answers "what did we sell last month".
  - **Studio flow:** run → 3 scripts → change one → pick → upload footage → captioned cut → publish request.
  - **Floor flow:** enter the Marketing floor, run a listing, measure that robots actually leave their desks, open the
    Brand brain, check each room and the Production set after approval. A video is recorded.
- **Bugs those runs found and fixed:**
  - a viewing asked for 4 PM was booked at 2 PM;
  - "price please?" got an unrelated answer;
  - two threads raced on the database;
  - a fake "sample" competitor wall;
  - "null" printed on screens;
  - raw event codes in captions.

## 11. What is real today, and what is needed to go live

**Works today, offline, with honest labels:** everything above, using rules and templates. Each step that needs a
connection says which one.

| Connection | Unlocks | Status |
|---|---|---|
| Meta Model API key | Muse Spark for answers, ideas, scripts; web research; transcription; cover images | Waiting on Meta |
| Instagram professional account + token | Competitor posts fetched automatically, our insights, publishing, comments to Rania | Needed |
| WhatsApp (AiSensy or Cloud API) test number | Real messages instead of the sandbox | Needed |
| HeyGen key + a consented avatar | AI presenter videos | Optional (paid) |
| Baseten / Fireworks / Modal | Open-weight models | Baseten free credits available |
| A public address for the app | Instagram can fetch the reel when publishing | Needed for publishing |

**Planned, not built:** Follow-up drafter, Transfer tracker, Invoice clerk, Devil's advocate, Positioning.

## 12. Rules we hold ourselves to

- Fictional data only in demos; no real customer data on free model credits.
- Keys live in the local `.env`, are never printed or logged, and screens only show whether each is set.
- No samples presented as real numbers: if something isn't measured yet, the screen says so.
- Agents never hold portal or bank credentials, never promise returns, never decide suspicion.

## 13. The plan

- **Now (hackathon):** Meta Global AI Developer Hackathon. Submission due **4 Nov 2026, 9 PM ET (5 Nov, 6 AM Dubai)**.
  The demo story is the correction moment, the front desk, and a listing going through the studio to an approved,
  captioned reel.
- **Before submitting:**
  - connect the Meta key;
  - record the demo video;
  - choose the track;
  - make the repository public (after removing an old demo backup from its history).
- **After:**
  - the planned agents;
  - real pilots with a brokerage (with consent and real data handling);
  - the same "office you can correct" pattern for other regulated, conversation-heavy businesses.

---

*Repository:* `alifiya-saifee/diwan` (private until submission). *Handbook for the marketing team:* generated from the
code with `python -m diwan doc`. *Run it:* `uvicorn diwan.app:app --port 8030`, then open `/web/office3d.html`.
