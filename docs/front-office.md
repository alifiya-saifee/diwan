# Diwan front office: how it works, and how we present it

Part A is the operating design: where every lead lands, who does what, how the agents coordinate, and what each lead
ends as. Part B is the presentation: each real problem paired with what Diwan does about it and the moment that shows
it, then the deck and the 3-minute video built from those pairs.

Status marks: ✅ built and tested · 🟡 partly built · 🔨 to build · ⏳ after the hackathon.

---

# Part A: the operating design

## A1. What "done" means for a lead

Every enquiry, from any channel, ends in exactly one of these, with the reason written down:

| Outcome | Means | Who closes it |
|---|---|---|
| **Won** | Form F signed and transfer done; commission recorded | Broker, with Finance |
| **Lost** | With a reason: bought elsewhere, too expensive, not ready, unreachable | Broker (Rania may propose after the follow-ups run out) |
| **Junk / spam** | Not a property enquiry: a sales pitch, a wrong number | Intake, automatically, kept visible |
| **Dormant** | Real, but not now; follow-ups paused with a date to wake | Follow-up agent, after its last nudge |

Along the way, every lead always has:
- **one owner:** a broker, or the Pool;
- **one stage:** see A6;
- **a profile** built from the customer's own words, with tags;
- **a due time** whenever a person must act;
- **a record** (the event log) that explains every step.

## A2. Principles that hold everywhere

1. **One memory.** Every message, fact, assignment, card and sync is an event in the append-only log. Screens, KPIs,
   the 3D office and CRM syncs are all views of it. Nothing is edited; corrections are new events.
2. **The customer's words are the evidence.** A fact, tag or qualification answer carries the exact quote and where
   it was said: WhatsApp, a call, a meeting or a portal form.
3. **One voice to the customer.** Customers only ever talk to Rania, or to a named person. Stages change her
   instructions, not her name.
4. **People own what is legal, financial or public.** Agents prepare and propose. Brokers call, negotiate and send
   templates. Compliance judges. Managers reassign. Code enforces this through charters, not just prompts.
5. **A human beats an agent; a newer statement beats an older one.** When a person acts on a lead, the AI steps back
   at once. When a customer corrects themselves, only what rested on the old words changes.
6. **Honest labels.** Sample data says sample, a rules reply says rules, a blocked step says what it needs.

## A3. The map: where everything lands

```
 SOURCES                      INTAKE (code)                CONVERSATION (Rania + Scribe)          PEOPLE
 ──────────                   ─────────────                ────────────────────────────           ──────
 WhatsApp (AiSensy/Cloud) ─┐  verify signature             Discovery: what do they want?          Broker: calls, views,
 Instagram DM / comment ───┤  drop spam / pitches          Qualification: missing answers,          negotiates, Form F
 Facebook DM / ad / form ──┼─▶ merge bursts (30 s)  ─────▶   one question at a time        ─────▶ Sales manager: pool,
 Property Finder (Atlas) ──┤  detect a human taking over   Qualified: brief the broker,             reassign, escalations
 Bayut / Dubizzle ─────────┤  find or open the lead         keep the customer warm              Compliance: money flags
 Website form / call ──────┘  tag the source               every message → facts + tags         Owner: briefing, KPIs
                                      │                                  │
                                      ▼                                  ▼
             ONE LOG → graph: Lead · Contact · Chat · Fact · Tag · Listing · Card · Task · Notice · CRM link
                                      │
                ┌─────────────────────┼──────────────────────┬───────────────────────┐
                ▼                     ▼                      ▼                       ▼
          Dispatcher            Lead desk               Follow-up agent          CRM clerk
          (owner, area,         (cards, due times,      (2/4/6-day nudges,       (Bitrix: contact, lead,
           round-robin)          overdue, Pool,          agent reminders,          fields, brief, notes,
                                 notices)                escalate, dormant)        stage back from Bitrix)
                                      │
                         Catalog keeper: listings from the portal feed, Bitrix catalog, Property Finder
                         Nova and the Data analyst: briefings, questions, KPIs, the Sales wall
```

### Who is the master of which data

| Data | Master | Mirrors | Rule when they disagree |
|---|---|---|---|
| Conversation, facts, tags, cards | **Diwan log** | Bitrix timeline (summary and notes) | Diwan wins; Bitrix gets a new comment |
| Listings | **Portal feed or Bitrix catalog** (one chosen in Integrations) | Diwan catalog | Source wins; Diwan marks listings that left it as off-market |
| Lead stage after Qualified | **Broker's action** (Inbox or Bitrix) | the other side | The latest *human* change wins; AI never moves a stage backwards |
| Owner (assigned broker) | **Diwan Dispatcher**, or a manager's reassignment | Bitrix `ASSIGNED_BY_ID` | A manager's change wins over a rule |
| Property Finder status (answered or not) | **Property Finder** | Diwan card | Answered on Property Finder clears the Diwan card |

## A4. The agents and their full duties

Each agent has a charter: trigger, inputs, what it does alone, what needs a person, what it never does, and what it
hands on. Below are the front-office agents. ✅/🟡/🔨 marks what exists today.

### 1. Intake (code, no model) 🟡
- **Triggers:**
  - webhooks from WhatsApp (AiSensy, Cloud API), Instagram, Facebook, Property Finder, Bayut, Dubizzle, the website;
  - a message sent from the business phone.
- **Duties:**
  1. Verify every webhook: signature or token. Unsigned means refused and logged. ✅ (WhatsApp, portals)
  2. Ignore duplicates: the same provider message id is never handled twice. 🔨
  3. **Merge bursts:** messages within 30 seconds become one turn, so Rania answers once. 🔨
  4. **Detect a human takeover:** a message sent from the business phone that is not Rania's own echo locks the chat
     to that person. 🔨 (Diwan has a takeover button ✅; the n8n flow shows how to detect it from the phone.)
  5. **Spam filter:** SEO, crypto and recruitment pitches go to a "Not a lead" list, never to a broker. 🔨
  6. **Find or open the lead:** same phone or same customer means the same lead; otherwise a new one. ✅
  7. Tag the **source**: channel, ad, form, portal, listing reference. 🟡
- **Never:** replies, judges intent, deletes anything.
- **Hands to:** Scribe (every message), Rania (unless a human holds the chat), Dispatcher (new leads).

### 2. Scribe: facts from words ✅
- **Trigger:** every customer message, call transcript or meeting turn.
- **Duties:**
  - Facts with exact quotes: budget, who pays, income, deposits, family, timeline.
  - **Corrections:** "actually 2.5 million" replaces the earlier figure; only work resting on the old figure changes.
  - Hypothetical statements are kept, but change nothing.
  - An unclear correction becomes one question to the broker.
  - Money facts reach Compliance first.
- **Never:** guesses, records what was not said, judges suspicion.

### 3. Profiler: tags and the qualification profile 🔨
- **Trigger:** each new fact from the Scribe; a listing linked to the lead; a broker editing a tag.
- **Duties:**
  1. **Dynamic tags,** each with the quote behind it:
     - area, from a UAE gazetteer with nicknames and Arabic (Yas Island, Saadiyat, JVC, "the Palm", جزيرة ياس), plus
       every area in the catalog; a new area becomes a new tag "to confirm";
     - intent: buy, rent, sell, let out;
     - ready or off-plan, type, bedrooms, budget band, cash or mortgage, timeline, purpose (live or invest);
     - language and source.
  2. **The persona's checklist.** What a qualified lead must have:

     | Persona | Required |
     |---|---|
     | Buyer | area, type, budget, timeline, cash or mortgage |
     | Tenant | area, type, monthly or yearly rent, move-in date |
     | Seller | area, type, asking price, occupancy, standout features |
     | Landlord | area, type, expected rent, occupancy |

  3. **Prefill** from a portal listing: a Property Finder lead on a 2-bed in Marina Crest already has area, type,
     bedrooms and price band. Rania never asks what is already known.
  4. **Declare Qualified** when the checklist is complete and the customer agreed to be contacted. This is a
     rule, not a model call.
- **Never:** invents a value; tags from anything but the customer's words, a listing they enquired on, or a person.

### 4. Rania: the one voice to the customer ✅ (her stages are 🔨)
- **Stage 1, Discovery:** greet; find the real reason they wrote; answer from the catalog and confirmed knowledge.
  Don't interrogate. ✅
- **Stage 2, Qualification:** ask **only the missing checklist items, one per message,** in the customer's language.
  Weave answers in (listings that fit, fees, process). 🔨
- **Stage 3, Waiting for the broker:** keep them warm; say who will call and when (the broker's name; phone only
  if asked); take extra details; book viewings in the broker's free slots. 🔨 (booking ✅)
- **Always:**
  - hand over on: a call request, discount, negotiation, cash, crypto, returns, documents or checks, a complaint, or
    anything the sources don't answer;
  - never say why it was handed over;
  - never quote a price that isn't on a listing (code blocks it ✅);
  - keep the lessons the team taught her ✅.
- **Modes per chat:** Autopilot · Suggest (a person sends) · Off. ✅
- **Never:** negotiates, promises returns, discusses compliance, messages first outside WhatsApp's 24-hour window
  without a template.

### 5. Dispatcher: who owns the lead ✅ (area specialists 🔨)
- **Trigger:** a new lead; Qualified; an agent away; a lead claimed from the Pool; a manager's reassignment.
- **Order:**
  1. the listing's agent;
  2. 🔨 the area specialist, from the area tag and the broker's areas;
  3. round-robin among brokers on shift and present, fewest leads today first;
  4. if nobody is on shift, the least busy broker who is not away.
- **Duties:** notify the owner; mirror the owner to Bitrix 🔨; never assign to someone away.

### 6. Briefer: the summary before the call 🔨
- **Trigger:** Qualified, before the broker is told.
- **Duties:** a 5-line brief: who they are, what they want (with quotes), what was offered, what they asked,
  the best time to call. It goes to the Inbox, the broker's notice and the Bitrix timeline.
- **Never:** adds opinion about the customer, or anything not in the record.

### 7. Lead desk: due times and escalation ✅
- **Duties:**
  - Attention cards: a call is due in 15 minutes, a reply in 30.
  - A card closes only with a recorded action.
  - Overdue: the owner hears.
  - Untouched for 60 minutes: the lead goes to the Pool.
  - Claim, reassign, cover a colleague 🔨.
  - Notices on screen, in the browser, and on WhatsApp through an approved template.

### 8. Follow-up agent: nobody falls through 🔨
- **Trigger:** every hour.
- **Duties:**
  - **The customer is silent** → nudges on days 2, 4 and 6. Within 24 hours it's a free-text message; after
    that, an approved template. Every AI nudge also creates a same-day call task for the broker.
  - **The broker is silent** (no action on a qualified lead) → a reminder, then an escalation to the manager after
    3 reminders.
  - **After the last nudge** → Dormant, with a wake date, or a Lost proposal for the broker to confirm.
  - Stops at once when the customer replies or a human acts.
- **Never:** messages a locked chat; sends free text outside the 24-hour window.

### 9. Portal clerk: Property Finder, Bayut, Dubizzle 🔨 (generic signed webhook ✅)
- **Property Finder (Atlas API):**
  - key and secret → token (cached until it expires);
  - subscribe to `lead.created` with the callback URL;
  - on a lead: the phone from `sender.contacts`, the listing from `listing.reference`, the channel
    (WhatsApp, call or email), the customer type from the reference letter;
  - **after 5 minutes, ask Property Finder for the lead's status.** If its agent already answered, the Diwan card
    closes as "answered on Property Finder" and Rania stays out. If not, the broker's call card stays, and Rania
    sends the approved opener template.
  - **Missed call or under 5 seconds:** a "sorry we missed you" template, and a call card.
- **Bayut and Dubizzle:** the leads API or webhook, with the same lead shape.
- **Never:** scrapes; stores portal passwords; messages without a template.

### 10. Catalog keeper: one listing catalog 🟡
- **Sources** (chosen in Integrations): the portal XML feed ✅; the Bitrix catalog smart process 🔨; manual entry ✅.
- **Duties:**
  - Sync every 30 minutes. Listings that left the source become off-market. Manual listings are untouched.
  - **A listing without a permit is kept but never offered** ✅.
  - Map Bitrix dropdowns by reading the field list, not hardcoded IDs 🔨.
  - Each listing shows who enquired about it.

### 11. CRM clerk: Bitrix both ways 🔨
- **Out:**
  - contact: found by phone, otherwise created;
  - lead: title, source, owner, enquiry fields from tags, budget as the opportunity;
  - the contact is linked to the lead;
  - the brief, and later facts, go to the timeline.
- **In** (Bitrix webhook, token checked):
  - a lead made by hand in Bitrix → linked or created in Diwan;
  - a stage or deal change → stage updated;
  - an agent's note → added to the record, and "no answer" counts as a contact attempt;
  - a finished task → the broker is free.
- **Never:** overwrites a newer human change.

### 12. Compliance hooks ✅
The Scribe's money facts (payer, cash, deposits, income) reach the Compliance lead first. A changed payer is
flagged with both quotes. Rania never discusses checks. Cash of AED 55,000 or more → a report draft for the
compliance officer. Sales work continues; anything money-related waits for the officer.

### 13. Nova and the Data analyst ✅ (Sales wall 🔨)
- Morning briefing per person.
- Answers from the records.
- KPIs: response time, on-time %, conversion by area and source, commission, rising star.

### The people

| Person | Uses Diwan for | Only they can |
|---|---|---|
| Broker | Calls, chats, viewings, offers, Form F | Negotiate, send templates, mark Won or Lost |
| Sales manager / owner | The Pool, reassigning, overdue, KPIs | Reassign, close as Lost in bulk, change rules |
| Compliance officer | Money flags, report drafts | Judge, file |
| Marketing manager | Ads and comment funnels feeding leads | Approve campaigns and templates |

## A5. How the agents coordinate

1. **Through the log, never by calling each other.** An agent writes an event; the next agent reacts to that event
   type. This is why a correction can withdraw exactly the work that rested on the old words.
2. **One writer per chat at a time.** Two locks:
   - a **human lock**, from a takeover, a broker's reply or claiming from the Pool;
   - a **turn lock** while Rania composes, released after 10 minutes if it is stale.

   Rania checks both before she speaks.
3. **Timers live in one minute-loop:**
   - burst merging (30 seconds);
   - card due times (15 or 30 minutes);
   - the Pool (60 minutes);
   - the Property Finder recheck (5 minutes);
   - follow-ups (hourly);
   - the catalog sync (30 minutes);
   - Nova's rounds (before briefing time).
4. **Every external call has an idempotency key.** A webhook retried by WhatsApp or Property Finder never makes a
   second lead or a second reply.
5. **Priority when signals clash:**
   1. a human's action;
   2. the customer's newest words;
   3. a rule;
   4. the model.
6. **Failure is visible, never silent:**
   - model slow → the rules answer, and the reply says so;
   - an API down → `step.blocked` with what it needs, and a retry on the next loop;
   - over the model budget → rules and templates.

## A6. The lead's life (stages and side states)

```
New → Discovery → Qualifying → Qualified → Contacted → Viewing booked → Viewed → Offer → Form F → Transfer → Won
                                                                                              ↘ Lost (reason)
Side states at any point: 🔒 human holds the chat · 🕳 in the Pool · 💤 dormant (wake date) · 🚫 junk/spam
```

| Move | Triggered by | Agent |
|---|---|---|
| New → Discovery | the first message | Intake |
| Discovery → Qualifying | genuine property intent | Rania (classification) + Profiler |
| Qualifying → Qualified | checklist complete and consent | Profiler (rule) → Briefer → Dispatcher |
| Qualified → Contacted | the broker's call or message recorded | Lead desk (card cleared) |
| → Viewing booked | a booking in the broker's free slot | Rania or the broker |
| → Offer / Form F / Transfer | the broker, or a Bitrix deal stage | Broker, CRM clerk |
| → Won / Lost | the broker (Lost needs a reason) | Broker |
| any → Dormant | follow-ups exhausted | Follow-up agent (proposes) |

Stages only move forward automatically. Backwards needs a person.

## A7. Scenarios end to end

1. **WhatsApp, new buyer:** *"Hi, looking at something on Yas Island, 2 bed, around 1.8M"*
   - Intake opens the lead; the Scribe records the budget; the Profiler tags Yas Island, 2 bed, AED 1.5–2M and Buy.
   - Rania answers with matching permitted listings, and asks one missing item: cash or mortgage.
   - Once the checklist is complete: Qualified → the Briefer writes the brief → the Dispatcher sends it to the Yas
     Island specialist → a 15-minute call card and a notice → the brief goes to Bitrix.
2. **Property Finder lead, the agent answers fast.** A lead is created → Diwan opens the lead with the listing
   prefilled → the call card goes to the listing agent → after 5 minutes Property Finder says "answered" → the card
   closes as "answered on Property Finder", and Rania never messages.
3. **Property Finder missed call.** The call status is missed → "sorry we missed you" template → a call card due in 15
   minutes.
4. **The customer goes quiet.** Nudges on days 2, 4 and 6 (templates after 24 hours), each paired with a call task →
   no reply → Dormant, with a 30-day wake date.
5. **The broker goes quiet.** The card is overdue → the owner is told → at 60 minutes, the Pool → Hamza claims it →
   ownership moves in Diwan and in Bitrix.
6. **The broker takes over from their phone.** Their message is detected → the chat locks to them → Rania only
   suggests replies → the card clears as "messaged".
7. **The customer corrects themselves.** *"Actually my budget is 2.5M"* → the budget fact is replaced → tags update →
   suggested listings change → the brief is updated in Bitrix. Nothing is deleted.
8. **Money signal.** *"My brother will pay the deposit in cash"* → Compliance hears first, with the quote → Rania says
   the broker will go through payment details → sales continues; anything money-related waits for the officer.
9. **Instagram comment "PRICE" on a reel.** A public reply and a DM with the listing → the conversation continues in
   DM → same flow.
10. **A sales pitch on WhatsApp.** The spam filter puts it on the "Not a lead" list. No broker is disturbed. A person
    can rescue it.

## A8. What it handles, and what it doesn't

**Handles:**
- channels: WhatsApp, Instagram, Facebook, Property Finder, Bayut, Dubizzle, the website;
- Arabic and English;
- buyers, tenants, sellers and landlords;
- booking viewings, handover and escalation, follow-ups, CRM sync, compliance flags, KPIs.

**Doesn't:**
- negotiate, promise returns, or judge suspicion;
- message first outside WhatsApp's rules;
- submit Form F;
- move money;
- scrape portals;
- keep customer data on free model endpoints. Free endpoints are for development, with fictional data only.

## A9. Integrations: where each key lives

One **Integrations** page (today's Settings). Keys are stored in the local `.env`, never shown again, only whether
each one is set.

| Integration | What you enter | What Diwan does with it | Status |
|---|---|---|---|
| WhatsApp (AiSensy or Cloud API) | project or token, webhook | receive, send, templates | ✅ |
| Instagram / Facebook | page token, verify token | DMs, comments, publishing | ✅ / 🔨 (ads and forms) |
| Property Finder | API key + secret | token, subscribe, leads, status, calls | 🔨 |
| Bayut / Dubizzle | leads API key or webhook secret | leads | 🟡 (signed webhook) |
| Listing feed | the feed URL | catalog sync | ✅ |
| Bitrix24 | inbound webhook URL; catalog entity id | catalog import, contact and lead push, events in | 🔨 |
| Meta models | Meta key; Baseten / NVIDIA | Muse Spark; open weights | ✅ |
| Slack (optional) | bot token | manager escalations | ⏳ |

## A10. KPIs (what we measure, from the log)

- **Per broker:**
  - speed to first action (median);
  - % of cards acted on before due;
  - leads lost to the Pool;
  - lead → viewing → offer → won;
  - commission;
  - rising star: improvement against their own last 4 weeks.
- **Rania:**
  - % of chats handled without a person;
  - handovers by reason;
  - model vs rules share;
  - guard blocks;
  - time to first reply.
- **Office:**
  - pipeline by stage and value;
  - expected commission in 30 days;
  - leads and conversion by source and area tag;
  - follow-up recovery rate;
  - deals held by compliance.

## A11. Build order

| # | Piece | Why now | Size |
|---|---|---|---|
| 1 | Profiler: dynamic tags + persona checklists + prefill | Everything after it reads the profile | ½ day |
| 2 | Rania's three stages (discovery, qualification, waiting) | The "one question at a time" experience | ½ day |
| 3 | Property Finder Atlas clerk + the 5-minute status check | The real lead source; the n8n flow has it switched off | ½ day |
| 4 | Catalog page + Bitrix catalog import with automatic field mapping | Full listing view; no hardcoded IDs | ½ day |
| 5 | Briefer + CRM clerk (out: contact, lead, brief; in: stage, notes) | Brokers live in Bitrix | 1 day |
| 6 | Intake hardening: burst merging, idempotency, takeover from the phone, spam list | Real traffic | ½ day |
| 7 | Follow-up agent | No lead falls through | ½ day |
| 8 | Sales wall KPIs | The owner's view; demo | ½ day |

The hackathon cut is 1–4 and 8, plus the existing correction and compliance moment. 5–7 come right after.

---

# Part B: the presentation

## B1. The idea in one line

**Every enquiry gets an answer in seconds, every lead has an owner and a deadline, and when a customer changes their
words, the whole office changes with them, with the quote to prove it.**

## B2. Problem → solution → proof

Each row is one claim. A row is shown only if its proof works live, or is a labelled recording of it working.

| # | The real problem (who feels it) | Evidence | What Diwan does | What we show on screen |
|---|---|---|---|---|
| 1 | Enquiries arrive at night and on weekends; the first agency to answer usually gets the viewing (broker, owner) | Brokers' own experience; to confirm in 3–5 interviews | Rania answers in seconds, in Arabic or English, from permitted listings only | A WhatsApp message at 11 PM; reply in seconds; the listing cited |
| 2 | Leads get lost between people; nobody knows who owns what (owner) | Cosmic CRM tracker: 1-hour pool, "needs attention" rules were built because of this | One owner, a due time, overdue → manager, Pool after an hour | A card counting down; overdue; Hamza claims from the Pool |
| 3 | Portal leads are double-handled: the portal agent and the office both message (customer annoyance) | The n8n Property Finder flow built a 5-minute check (switched off today) | Ask Property Finder after 5 minutes; if answered, stay out | Property Finder status "answered" → the card closes, no message sent |
| 4 | The broker re-asks what the customer already said (customer, broker) | The n8n prefill exists so the AI skips known questions | The profile and tags from the customer's own words; the brief before the call | Tags with quotes on hover; the 5-line brief in the Inbox and Bitrix |
| 5 | Customers change their story; the file, deck and approvals don't follow (compliance, finance) | MoE: 495 brokerage AML breaches, AED 18.5M fines in H1 2025 | Correction engine: compliance first, dependent work withdrawn, stale approvals refused | "Forget my brother, I'll pay myself" → the flag, withdrawals, the refused approval |
| 6 | AI agents are black boxes, so owners don't trust them (owner) | Our premise; the Meta "Verifiable agents" session theme | Every action has a charter, a quote, a record; the 3D office shows only real work | The 3D office: Rania's phone rings on a real message; click it, the real chat opens |
| 7 | Tools are scattered: WhatsApp, portals, CRM, spreadsheets (everyone) | n8n flows across 360dialog, Evolution, Bitrix, Supabase, Slack | One log; Bitrix kept in sync both ways; one Inbox | A lead appears in Bitrix with fields, brief and owner |
| 8 | Owners can't see performance without asking three people | The Data analyst counts from records, never estimates | The Sales wall: speed, on-time %, conversion by area, rising star | The wall in the 3D Sales room, each number clickable to its records |

## B3. How Meta's models fit (the judges' 25%)

| Model | Job in this flow | What breaks without it |
|---|---|---|
| Muse Spark | Rania's replies and stages; the Scribe's facts and corrections; the Briefer | Replies fall back to rules: correct but robotic; no free-text understanding |
| Muse Voice Transcribe | Call recordings and voice notes become facts | Calls stay unrecorded; no quotes from phone conversations |
| Muse Spark Open (Baseten) | Compliance reasoning on open weights; customer money data stays off a hosted API | The open-weights claim and bonus |
| Muse Image | Listing covers for the comment and ad funnels | Manual design |

## B4. The deck (10 slides)

1. **Title:** Diwan, the brokerage front office you can correct.
2. **The night enquiry:** a WhatsApp message at 11 PM, and what happens today (no answer, or a junior guessing).
3. **Where leads die:** no owner, no deadline, portal double-handling, re-asking. One diagram, four red dots.
4. **Diwan in one picture:** the A3 map, simplified: sources → Rania → one log → people.
5. **One lead, start to finish:** scenario 1 as six screenshots: reply, tags, Qualified, brief, card, Bitrix.
6. **Nothing falls through:** due times, the Pool, follow-ups, Property Finder's 5-minute check.
7. **When the story changes:** the correction moment (scenario 5 + 8).
8. **Trust:**
   - charters, quotes, guards (a price not on a listing is blocked);
   - the test console;
   - 78 evals plus tests.
9. **Built on Meta:** the B3 table.
10. **Results and next:**
    - measured speed and on-time numbers from the demo log;
    - real broker quotes (from the interviews);
    - next steps: Bitrix two-way, follow-ups, a pilot brokerage.

## B5. The 3-minute video (shot list)

| Time | On screen | Voice-over |
|---|---|---|
| 0:00–0:15 | A phone at 11 PM, a WhatsApp from a buyer about Yas Island | "Most enquiries arrive when the office is closed." |
| 0:15–0:45 | Rania replies in seconds; tags appear with quotes; one question at a time | "Diwan answers from your own permitted listings, and remembers exactly what was said." |
| 0:45–1:10 | Qualified → the brief → the Yas Island specialist gets a 15-minute call card; the lead lands in Bitrix | "Every lead gets an owner, a deadline and a brief." |
| 1:10–1:35 | A Property Finder lead; at 5 minutes, "answered on Property Finder" → Diwan stays out. A missed call → template + card | "It works with your portals, not over them." |
| 1:35–2:15 | *"Forget my brother, I'll pay it all myself"* → compliance first, work withdrawn, the stale approval refused | "When the story changes, the whole office changes with it, with the quote to prove it." |
| 2:15–2:40 | The 3D office: Rania's phone rings on the real message; the Sales wall; overdue → Pool → claimed | "You can see your office working, and nothing on screen is invented." |
| 2:40–3:00 | Built on Muse Spark, Voice Transcribe, Spark Open; the trust slide | "Built on Meta's models. Verifiable by design." |

**Rules for the recording:** fictional data only; label any replayed run; real model replies (Muse Spark), not rules.

## B6. Open questions to settle before building

1. **Property Finder reference letters:** the n8n parser reads S as Buyer, but its catalog code reads S as Seller.
   Which is right?
2. **Qualified:** does it require the customer's consent to a call, or is a complete checklist enough?
3. **Bitrix:** which side is master for the stage after Qualified, if brokers edit in both places?
4. **Follow-up wording and schedule:** approved templates for days 2, 4 and 6 (needed on AiSensy before sending).
5. **Area specialists:** which broker covers which areas?
