# Front desk & Sales: how it works, and what is done

How a customer's message moves through the Front desk and Sales agents, how they coordinate, and how the knowledge
graph feeds them, with an honest status for every part. Written 29 Oct 2026 by the Front desk & Sales session. The
checklist this answers to is in `docs/sessions.md` (section 2); the full design is `docs/front-office.md`.

**Status marks:**
- ✅ checked in the browser like a user (with screenshots);
- 🧪 tested in code only;
- 🟡 partly built;
- ❌ not built.

## 1. The flow, end to end

```
 customer ─ WhatsApp / Instagram comment / portal enquiry
     │
     ▼
 INTAKE (code)          verify the webhook, find or open the lead, tag the source
     │  chat.received
     ▼
 SCRIBE                 facts with the customer's exact words; a correction replaces the earlier fact
     │  fact.created / fact.superseded ───────────────▶ Deal desk (Compliance hears money facts first)
     ▼
 RANIA                  reads knowledge.search() + the customer's facts + the conversation
     │                  replies (Muse Spark, or the rules), asks the next qualification question
     │  qualify.type / qualify.answer (each with the customer's words)
     ▼
 QUALIFICATION (code)   the owner's form decides: ASK_QUESTION · PASS_TO_AGENT · NOT_A_FIT
     │  qualify.passed                      qualify.not_fit → the owner's polite reply, lead closed as Lost
     ▼
 DISPATCHER (code)      lead.assigned: the listing's agent, else round-robin on shift
     ▼
 LEAD DESK (code)       attention.raised (call 15 min, reply 30 min) → overdue → the Pool after 60 min
     │  notify.sent (Inbox bell, browser, the broker's WhatsApp via an approved template)
     ▼
 BROKER                 takes the chat, calls, books, negotiates; Rania goes quiet and only suggests
```

**How the agents coordinate:**
- **Through the event log only.** No agent calls another. Each writes an event, and the next reacts to that event's type. Every screen (Inbox, Test Rania, the 3D office, Catalog) is a view of the same log.
- **A human beats an agent.** Once a person has the chat, Rania only suggests replies. She never books a viewing by herself, and a customer writing in raises a card for that person.
- **Code decides, the model writes.** The model writes Rania's words and reads answers out of the conversation. Code decides:
  - whether the lead qualifies, and who owns it;
  - due times;
  - what may be said: prices must be on a listing, "never" lessons are enforced, and cash, crypto, discounts and returns always get a fixed reply.
- **One memory for what the office knows:** the knowledge graph (section 3). Rania reads it only through `knowledge.search()`.

## 2. Each part and its status

| Part | What it does | Status |
|---|---|---|
| **Rania on WhatsApp** | Replies in English or Arabic from permitted listings and customer-facing knowledge; one question at a time; offers only listings that fit everything said; books in the broker's free slots; hands over without saying why | ✅ on Muse Spark (6-turn conversation and 12/12 labelled cases) |
| Fixed safe replies | Cash, crypto, discounts, negotiation, guaranteed returns: the same safe answer every time; the model is not asked | ✅ |
| Price guard | A reply naming an amount that is not on a listing is not sent; the chat goes to the broker | 🧪 |
| Lessons | "Rania, never mention X" is saved and enforced in code | 🧪 (checked in the browser in earlier sessions) |
| **Knowledge leak fix** | Rania sees only confirmed, customer-facing, in-date items; internal ones never reach her | ✅ offline and on Muse Spark |
| **Qualification** | The owner sets the questions per customer type (buyer, tenant, seller, landlord, own types), how strict each is (must answer / "not sure" is OK / optional), "ask only if…", and the conditions (qualify when / not a fit when, with a polite reply); versioned; Try it | ✅ on Muse Spark: a buyer qualified in 7 messages; a 250k budget got the owner's not-a-fit reply |
| **Dispatcher** | Listing's agent first, then round-robin among brokers on shift and not away; manager can reassign | ✅ |
| **Lead desk** | Needs-attention cards with due times; a card closes only with a recorded action; overdue → owner told; 60 min → the Pool; claim | ✅ |
| Notices | Inbox bell and browser notification; the broker's own WhatsApp needs an approved AiSensy template | ✅ on screen; WhatsApp 🧪 (no template yet) |
| **Inbox** | Stages (New → Qualifying → Qualified → … Won / Lost), tabs (Needs attention, Pool, Waiting…), takeover, templates, 24-hour window, a Qualification panel per lead | ✅ |
| **Test Rania** | Talk to her on a private copy of the office; choose Muse Spark / rules / free NVIDIA; see who answered, what she used, what she was told, what a guard stopped; run her 12 cases | ✅ |
| 3D office | Rania's WhatsApp phone on her desk, driven by real chat events; click → that chat in the Inbox | ✅ |
| **Portals** | Property Finder, Bayut, Dubizzle enquiries by signed webhook → a call card for the listing's agent; Rania does not message first | ✅ (signed webhook); the real Property Finder Atlas API ❌ |
| **Demo catalog** | 32 fictional listings in 11 areas through a fictional portal feed, free-licence photos with credits, sale/rent, maps on each listing and a Map view | ✅ |
| **Listing feed sync** | The portal feed keeps the catalog in line without undoing people: a person's status is kept, an accepted price waits for the portal (with a task), the feed wins when the portal itself changes | ✅ (reserved/sold 🧪: the page has no control to set them) |
| Scribe | Facts with exact quotes, corrections, Arabic correction cues | 🧪 (✅ in earlier sessions) |
| Nova | Morning briefing, cited answers, Lobby jobs with read-back | 🟡 built earlier; not re-checked by this session |
| Intake hardening | Duplicates ignored, bursts merged, spam to "not a lead", takeover detected from the broker's phone | ❌ |
| Profiler tags | Area and other tags with quotes; "customer agreed to be contacted" before Qualified | ❌ (qualification answers exist; tags and consent do not) |
| Briefer | A 5-line brief for the broker and the CRM | 🟡 the call card carries the answers; no written brief |
| Follow-up | Nudges on days 2, 4, 6 (templates after 24 hours) with a call task; dormant or lost | ❌ |
| Instagram replies | Keep the post a comment came from; a short public reply and details in DM; DMs | ❌ (comments reach Rania, the post is not kept) |
| Leads per Marketing post | Leads and viewings per post and angle, for the Marketing strategy | ❌ (needs the event shape agreed with Marketing) |

## 3. The knowledge graph (what the office knows)

**How it is built:** every change is an event in the append-only log. The graph is rebuilt from the log, so it can be rewound and nothing is ever overwritten. One store holds:
- **knowledge items:** company, approved answers, areas, projects, people, brand;
- **listings:** the catalog.

Two screens sit on it: the Knowledge page and the Catalog page. One function, `knowledge.search()`, serves every agent and the header search.

**Every item has:**
- a status (proposed / confirmed / retired; listings: available / reserved / sold / off-market);
- an audience (customer-facing or internal);
- a source, a version history, a review date, a valid-until date;
- a "used in N replies" count.

**Who can change it:**
- **Owners** edit and retire their kinds.
- **Anyone else** proposes, and the owner accepts or rejects.
- **Brokers never edit a price;** they propose it.
- **Retire** hides an item from every agent and can be undone.

**How agents read it:** `knowledge.search(g, text)` returns at most 8 items. They are confirmed, customer-facing, in-date knowledge and advertised listings (with a permit, and available) that fit the beds, budget and area the customer named. Rania cites the item ids she used.

**Status against its definition of done** (`docs/knowledge.md` section 6): **all 22 checks pass.**

| Group | Done |
|---|---|
| Knowledge page (tabs, search, filters, add, edit with history, retire and restore, proposals, stale re-confirm, empty states, usage) | ✅ 10 / 10 |
| Catalog (1,000 listings paged, filters, search, photo or placeholder, "not advertised" without a permit, price proposals, a customer's agreed price stays in their deal) | ✅ 7 / 7 |
| Agents: an edit is used at once; a retired item is never cited; an internal-only item is never said to a customer; a question with no matching item reaches a person (after qualifying, on the broker's card) | ✅ 4 / 4 |
| Memory graph: an edit shows as version 2 replacing version 1; a retire shows the item dimmed | ✅ 1 / 1 |

## 4. Open issues, most important first

1. ~~"No matching item → a person" vs qualification~~ **decided 29 Oct: after qualifying.** The question is kept and
   shown on the broker's qualified-lead card ("Asked, not answered yet") and in the Inbox panel.
2. **No search box in every screen's header** for the Catalog and Knowledge pages at phone width. Item 3 on the checklist.
3. **No control to mark a listing reserved or sold** on the Catalog page (only retire).
4. **Rules-mode oddity:** "how much commission do your brokers keep?" is read as a price question and gets "which
   property do you mean?". Nothing is revealed; Muse Spark answers it correctly.
5. **Permissions trust the "Acting as" name** chosen in the browser: fine for the demo, not for real use.
6. **Nothing from the last two days is committed yet.** The Front desk & Sales work and the knowledge work are in the
   working tree; committing is planned after checklist item 3.

## 5. Checks and cost

- **Tests:** 215 pass offline; labelled evals 78/78 (rules).
- **Browser checks** ran on separate test servers, never on `diwan.db`.
- **Muse Spark spend:** about $1.76 so far this month for all of Front desk testing. Today's live pass for the knowledge fix cost $0.02.
- **Checklist** (`docs/sessions.md`, section 2): items 1 and 2 done and checked in the browser; items 3 to 9 open as listed in section 2 above.
