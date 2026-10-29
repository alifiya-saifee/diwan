# Diwan: what each department and room must produce

The contract between departments. Each room has a job, the events it reacts to, the output it must produce (as an
event in the log, with its evidence), who picks that output up, and what only a person may do. A session building a
room builds to this contract; a room that produces something not listed here, or skips a listed output, is wrong.

Detail lives elsewhere: marketing in `diwan/agents/studio.py` and the handbook (`python -m diwan doc`); the front
office in `docs/front-office.md`; knowledge and the catalog in `docs/knowledge.md`.

## 1. Rules every agent follows (the mandates between agents)

1. **Agents talk through the log, never by calling each other.** A room writes an event; the next room reacts to that
   event type. That is what lets a correction withdraw exactly the work built on the old words.
2. **Every output is a pack** (`diwan/pack.py`): a verdict, evidence (each quote word for word from a cited source),
   what is missing, the next step, and the actions it proposes. Quotes not found in their source are dropped.
3. **The charter decides authority** (`agents/charters.py`): actions in `alone` are done; actions in `person` become
   an approval card; anything else is refused and logged. A room never does another room's job.
4. **Cite, never invent.** An answer names the record ids it used: a fact (F), knowledge item (K), listing, script (C).
   No source, no claim: say what is missing and hand it to a person.
5. **A blocked step says so.** Missing a key, a connection or the budget means a `step.blocked` event naming what it
   needs, never a silent skip or a made-up result.
6. **One voice to the customer.** Only Rania or a named person speaks to a customer. Every other room's output reaches
   a customer only through Rania, in the brand's voice, or through a person.
7. **Priority when signals clash:** a person's action, then the customer's newest words, then a rule, then the model.
8. **Money facts go to Compliance first.** Any payer, cash, deposit or income fact is seen by Compliance before any
   other room acts on it.
9. **Nothing is overwritten.** Corrections, edits and retirements are new events; the history stays.
10. **Spend is visible and capped** (`diwan/costs.py`). Identical requests come from the saved reply; costly steps
    (video, images) start only after a person says yes.

## 2. The map: who hands what to whom

```
                ┌──────────────── MARKETING ────────────────┐
 listings ─────▶│ research → plan → script → produce → edit → publish │──▶ a published post (listing ref, angle)
 brand ────────▶└───────────────────────────────────────────┘        │
                                                                      ▼ comments, DMs, "PRICE"
 WhatsApp / IG / portals ──▶ FRONT DESK & SALES: Intake → Scribe → Profiler → Rania → Dispatcher → Broker
                                   │ facts            │ qualified lead + brief        │ deal stages
                                   ▼                  ▼                               ▼
                             COMPLIANCE first     Lead desk (cards, Pool)       OPERATIONS (Form F, transfer)
                                   │                                                  │
                                   ▼                                                  ▼
                             REVIEW (stale drafts back)                         FINANCE (expected payments)
                                                     ▲
                    NOVA + RECORDS read everything: briefings, questions, KPIs, the Lobby board
```

## 3. Department by department

### Marketing (the content studio): owned by the Marketing session

| Room (lead) | Reacts to | Must output | Picked up by | Only a person |
|---|---|---|---|---|
| Research (Researcher) | a listing run; once a day | `board.pinned` cards: competitor outliers (score vs that account's median) and trends, each with its source link | Planning | — |
| Planning (Strategist) | board cards, a permitted listing | `content.made` idea for the listing (names the cards it uses); the week's lane gap; the angles to script (strategy: keep / shift / rest / explore) | Scripting | — |
| Scripting (Copywriter) | the idea and angles | 2–3 `content.made` scripts, each passed by review (`qa.passed`), then one `approval.requested` (use_script) | the Marketing manager | pick a script, or ask for a change |
| Production (Producer) | an approved script | a film-list `task.created` for the listing's broker, or `footage.added` from the AI presenter (with recorded consent) | Editing | start an AI video, confirm consent |
| Editing (Art director) | `footage.added` | take check (lines that drifted), captioned cut, post text with the permit number, covers | Publishing | — |
| Publishing (Publisher) | the cut and post text | permit check (holds traced to the agent who caused them), a slot, platform versions, `approval.requested` (publish), then `content.made` published | the owner; Front desk (comments) | approve publishing |
| Library (Script library) | saves, approvals, lessons | the brand profile, approved scripts, playbook entries, lessons the writers must keep | every writer; Rania (sign-off) | set the brand, confirm learned knowledge |

**Marketing hands to Front desk:** every published post carries its listing reference and angle, so a comment or DM
on it opens a lead tagged `source: post <id>, angle <angle>`.
**Front desk hands back to Marketing:** leads and viewings per post and per angle, so the strategy can rank angles by
enquiries, not only likes.

### Front desk and Sales: owned by the Front office session

| Room / agent | Reacts to | Must output | Picked up by | Only a person |
|---|---|---|---|---|
| Intake (code) | every webhook (WhatsApp, Instagram, portals, website) | a verified, de-duplicated, burst-merged `chat.received` on the right lead, with its source tagged; spam to "not a lead" | Scribe, Rania, Dispatcher | rescue a spam-marked chat |
| Scribe | every customer turn, call or meeting | `fact.created` with the exact quote; `fact.superseded` when a statement replaces an earlier one | Profiler; Compliance first for money facts | answer an unclear correction |
| Profiler | each new fact | tags with their quotes; the persona checklist (buyer, tenant, seller, landlord); `qualify.passed` when complete and the customer agreed to be contacted | Rania, Briefer, Dispatcher | edit a tag |
| Rania (receptionist) | `chat.received` when no person holds the chat | `chat.sent` (autopilot) or `chat.suggested` (review mode), citing listings and knowledge from `knowledge.search()`; `appointment.booked`; `chat.handover` on anything that isn't hers | the customer; the Lead desk | take over; negotiate; send templates |
| Dispatcher | a new or qualified lead; a broker away | `lead.assigned` (listing agent, area specialist, then round-robin on shift) | the broker; the Lead desk | reassign |
| Briefer | `qualify.passed` | a 5-line brief from the record only | the broker; the CRM | — |
| Lead desk | handovers, due times | `attention.raised` with a due time; `attention.overdue`; `lead.pooled` after 60 minutes; `notify.sent` | brokers, the Sales manager | clear a card with a recorded action; claim from the Pool |
| Follow-up | hourly | nudges on days 2, 4, 6 (templates after 24 hours), a call task with each; dormant or a lost proposal | the broker | mark Lost |
| Knowledge and catalog | edits, the portal feed | confirmed, versioned items; listings with permit and status; `knowledge.search()` for every agent | Rania, Nova, Marketing | edit (owners), accept proposals |
| Nova (chief of staff) | a person's question or instruction; briefing time | answers citing records; `briefing.ready`; `lobby.posted` jobs with read-back and deadlines; `instruction.given` routed to a lead | people; every department lead | — |

### Back office: today built on rules; owned by the Front office session after its core work

| Department | Reacts to | Must output | Only a person |
|---|---|---|---|
| Compliance (screening, source of funds, reports) | money facts, a changed payer | `check.raised` with both quotes; screening results; a cash-report draft at AED 55,000 or more | judge suspicion; file a report |
| Review (fact checker) | any draft before a person sees it | `review.returned` for a draft resting on a replaced fact; `review.passed` otherwise | — |
| Operations (Form F clerk, transfer) | an accepted offer | Form F filled from live facts, stopped before Submit | submit |
| Finance (payment tracker) | payment facts | expected payments tied to the exact words; withdrawn when those words are replaced | approve, release money |
| Records (archivist, data analyst) | documents; questions about numbers | `document.filed`; answers computed from records (sales, commission), never estimated | — |

## 4. Shared data and who masters it

| Data | Master (writes it) | Readers |
|---|---|---|
| Brand profile, scripts, research board | Marketing | Rania (sign-off), Nova |
| Listings catalog | the portal feed; brokers propose changes | Rania, Marketing, Nova |
| Company knowledge, approved answers, areas, projects | Knowledge owners (Layla, Sales manager, Marketing manager) | every agent, via `knowledge.search()` |
| Leads, chats, facts, tags, cards | Front desk and Sales | Nova, Compliance, Marketing (attribution) |
| Deals, Form F, payments | Operations and Finance | Nova, Records |

## 5. The demo moments each department must be able to show

- **Marketing:** a listing goes from research to 3 scripts, the manager asks for a change, picks one, the take is captioned, and the owner approves the post. The brand profile visibly shapes the scripts.
- **Front desk and Sales:** a WhatsApp enquiry is qualified one question at a time, assigned, briefed and booked; a broker takes over; Nova answers "what did we sell last month" and puts a job on the Lobby board.
- **The correction (everyone):** "forget my brother, I'll pay it all myself": Compliance hears first, the payment is withdrawn, the stale approval is refused, Review sends back the deck, Nova explains it.
