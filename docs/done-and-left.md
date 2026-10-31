# Front desk & Sales: done and left

Everything the Front desk & Sales session (session 2) has built, what is checked, and what is still to do, as of
29 Oct 2026. The checklist is `docs/sessions.md` section 2; how the parts fit together is `docs/front-desk-status.md`.
Deadline: 4 Nov 2026, 9 PM ET.

**Marks:**
- ✅ checked in the browser like a user;
- 🧪 tested in code only;
- 🟡 partly built;
- ❌ not built.

## At a glance

| | |
|---|---|
| Checklist items done | **2 of 9** (items 1 and 2) |
| Knowledge definition of done | **22 of 22** checks pass |
| Tests | 306 pass offline (run 30 Oct) |
| Evals | 78/78 (rules) |
| Muse Spark spend this month | about $1.76 |
| Committed | **nothing from the last two days**; all of it is in the working tree |

## 1. Checklist (docs/sessions.md section 2)

| # | Item | Status | What's left |
|---|---|---|---|
| 1 | Rania uses `knowledge.search()` only; internal items never reach a customer | ✅ offline and on Muse Spark ($0.02) | nothing |
| 2 | The feed sync keeps a listing's status; an accepted price shows "waiting for the portal" | ✅ offline, with a local feed | reserved/sold is 🧪 only: the Catalog page has no control to set them |
| 3 | Header search box on every screen; Knowledge and Catalog at phone width; commit the knowledge work | ❌ | all of it |
| 4 | Intake: duplicates ignored, bursts merged, spam to "not a lead", source tagged (incl. Marketing posts) | ❌ | all of it |
| 5 | Profiler: tags with quotes, persona checklists, Qualified only when complete **and the customer agreed** | 🟡 qualification answers and per-type questions exist | area/interest tags with quotes; the "customer agreed to be contacted" step |
| 6 | Rania's three stages: discovery, one question at a time, waiting for the broker; booking in free slots; handover | 🟡 discovery, one question, booking and handover work | an explicit "waiting for the broker" stage after qualifying |
| 7 | Dispatcher, Briefer, Lead desk, Follow-up | 🟡 dispatcher, lead desk, overdue and the Pool ✅ | the 5-line brief; follow-up nudges (days 2, 4, 6) |
| 8 | Nova: morning briefing, cited answers, Lobby jobs with read-back and chasing | 🟡 built in earlier sessions | re-check in the browser |
| 9 | Leads and viewings per Marketing post and angle | ❌ | agree the event shape with Marketing in the changelog first, then build |

## 2. Built and working

**Rania (WhatsApp):** ✅ on Muse Spark, a 6-turn conversation and 12/12 labelled cases.
- Answers first, asks at most one question, introduces herself.
- Offers only listings that fit everything the customer said; says so when none fits.
- English and Arabic.
- Books in the broker's free slots.
- Goes quiet and only suggests replies once a person has the chat.

**Safety:**
- Fixed safe replies for cash, crypto, discounts, negotiation and guaranteed returns: the model is not asked. ✅
- Price guard: an amount not on a listing is never sent. 🧪
- "Never" lessons are enforced in code. 🧪
- The knowledge leak is closed (item 1). ✅

**Qualification set by the owner:** ✅ on Muse Spark.
- Questions per customer type (buyer, tenant, seller, landlord, own types), required or "ask only if…".
- Conditions for "qualify when" and "not a fit when", with the owner's polite reply.
- How strict each question is, the owner's choice ✅ (checked in the browser, 14/14):
  - **Must answer:** "not sure" doesn't count. Rania says a rough idea is fine and asks once more; after a second
    "not sure" she stops and the broker gets a call card ("Not sure about Budget, which you require: call to help").
    The lead doesn't qualify until a real answer comes.
  - **"Not sure" is OK:** it counts as the answer; the broker sees "When: Not sure".
  - **Optional:** never holds the lead back.
  - Defaults: budgets and prices are "must answer"; other required questions accept "not sure". A condition on a
    "not sure" answer is skipped, never met or failed.
- A question Rania can't answer while qualifying is kept and shown on the broker's qualified-lead card.
- Versioned, with a Try-it panel (type "not sure" to try the strictness).
- A buyer qualified in 7 messages; a 250k budget got the not-a-fit reply.

**Lead desk:** ✅
- Dispatcher: the listing's agent first, then round-robin among brokers on shift.
- Needs-attention cards: call in 15 min, reply in 30 min. Overdue tells the owner; after 60 min the lead goes to the Pool. Brokers can claim from it; the manager can reassign.
- Notices: ✅ the Inbox bell and browser notifications. The broker's WhatsApp is 🧪 and needs an approved AiSensy template.

**Inbox:** ✅ stages (New → Qualifying → Qualified → … Won / Lost), tabs, takeover, templates, the 24-hour window, a Qualification panel per lead.

**Test Rania:** ✅ talk to her on a private copy of the office.
- Choose Muse Spark, rules or free NVIDIA (NVIDIA is slow).
- See who answered, what she used, what she was told, and what a guard stopped.
- Run her 12 cases in the background.

**3D office:** ✅ Rania's phone on her desk, driven by real chat events; clicking opens that chat.

**Portals:**
- ✅ Property Finder, Bayut and Dubizzle enquiries arrive by signed webhook and become a call card for the listing's agent.
- ✅ The feed sync (item 2).

**Deal kinds (sales desks):** ✅ checked in the browser (12/12), 30 Oct, approved by the product owner.
- The brokerage's deal kinds are data, not code: the owner edits them on Settings (demo: Off-plan, Ready sales,
  Leasing). Each has the customers it serves (a customer type, optionally "when an answer is…"), the listings it covers
  (for sale or rent; ready or off-plan, read from the feed) and its brokers. A CRM's pipelines can fill the same list.
- When a lead qualifies, the first matching kind is its kind: it moves to one of that kind's brokers (logged, with a
  notice), Rania recommends only that kind's listings, and the Inbox shows the kind as a chip.
- With no deal kinds set, everything works as before.

**Pitch deck for the meeting:** ✅ checked in the browser (14/14), 30 Oct.
- Made when a lead turns hot (or when the broker asks): the property; why it fits, in the customer's own words; the
  deal kind's part (an off-plan project's payment plan and handover from Knowledge → Projects; rent and move-in;
  price and viewing); and documents already in the archive (Records' search). Every slide names its sources.
- Missing (no payment plan, no brochure): the slide says so and the broker gets a task to ask the developer.
- The broker approves it from the lead; another broker cannot. "Open for the meeting" shows it full screen, printable.
- The customer changes a statement it rests on → the Fact checker sends it back, the approval goes stale, the
  meeting page warns; "Remake" builds v2 from what stands now.
- Demo data: two fictional off-plan projects and one developer brochure (the other is missing on purpose).

**Follow-up after the meeting:** ✅ checked in the browser (8/8), 30 Oct.
- Drafted when the broker marks the lead Viewed, when a meeting ends (the Meeting page has an "End the meeting"
  button now), or on request: thanks, the property and price, their budget, and the next step for the deal kind;
  in the customer's language. Muse Spark writes it when connected.
- Never a word about compliance (no tipping off): a model draft that mentions it is thrown away, and a broker's edit
  that adds it is refused. Only the deal's broker or the owner sends it; after 24 hours it must be a template.

**The front door:** ✅ checked in the browser (14/14), 30 Oct, approved by the product owner. Spec: `docs/front-door-spec.md`.
- "Just looking" gets a warm reply and no question; the lead moves to 🌱 Nurture (Marketing by default, the owner's
  choice) and the broker's card closes. Rania still answers them. When they show they're ready (a budget, a viewing, a
  call) the lead comes back and the broker is told.
- "Can someone call me?" at any stage: "our team will call you shortly" and a call card; once qualified it is 🔥 hot
  when the owner ticks it. "They qualify" can make a lead hot at once (owner's choice).
- A portal enquiry fills in buying or renting, area, type and bedrooms from the listing (marked so, never the budget),
  sends the owner's chosen template, and Rania asks only what is missing.
- The Inbox has a Nurture tab; Marketing reads `/api/leads/nurture`.

**When a client goes quiet:** ✅ checked in the browser (13/13), 30 Oct. Spec: `docs/quiet-clients-spec.md`.
- Follow-ups on the owner's schedule (default after 20 hours, 3 days, 7 days), only with something useful (a new fit,
  the open question, the door left open), never in quiet hours or Friday prayer, never a word-for-word repeat.
- After 24 hours only the owner's approved template. "Stop" ends it for good. After the last one the lead goes to
  Nurture (or the broker gets one card). The lead shows "1 of 3 sent · next …"; the owner sees who is due next.

**The calendar:** ✅ checked in the browser (12/12), 30 Oct. Spec: `docs/calendar-spec.md`. A demo calendar (Google and
Outlook not connected, decided by the product owner).
- Hours from the owner's setting and each broker's shift and working days (Settings → Team); never a day off, never an
  overlap. Kinds of appointment are the owner's list (site visit, office meeting, video call); Rania books the kind asked.
- Move or cancel in the chat (the one they name); the broker is told. Reminders the day before and two hours before;
  each broker's morning list.
- `calendar.html` (from the Inbox bar): the week; the owner sees all brokers and filters to one, a broker their own;
  Done (→ Viewed, drafts the follow-up) and No-show after the time.

**After the visit:** ✅ checked in the browser (7/7) and on Muse Spark, 30 Oct. Spec: `docs/visit-summary-spec.md`.
- "Record the visit" from the appointment opens the meeting page for that deal; nothing is kept until the client agrees.
  Or the broker types a few lines when marking it Done.
- The Visit summarizer: keen / thinking it over / not for them, what they liked, what worried them, the next step, each
  with the words it came from (a point whose words aren't there is dropped). On the lead and on the appointment.
- The follow-up answers their worry; "not for them" asks what to change and never pushes the same property.

**Checked again, 30 Oct (all five browser checks on fresh databases: 51/51; live Muse Spark over parts 1 to 4: $0.16).**
Found on the live run and fixed: a client in Nurture asking something Rania couldn't answer was handed to a broker (now
kept as a note for the broker, no card); a client who had asked for a call also got a quiet-client follow-up (now none
while the broker has an open card). Found in the browser and fixed: Rania added "are you looking to buy, rent…?" after
"Booked: …"; "I've cancelled Unit 1204" (now "your site visit to Unit 1204").

**Live check, 30 Oct:** one Muse Spark pass over the whole flow (qualify → no listings while qualifying → 3 when asked
→ 3 recommendations → "the second one" → hot lead) and one model follow-up: **$0.077**. Month so far: **$2.34**.

**Recommendations and the hot lead:** ✅ checked in the browser (14/14), 29 Oct.
- While qualifying, Rania doesn't push listings; if the customer asks, she answers within the limit.
- Once qualified, she sends the owner's number of best-fitting properties (closest to the budget, nothing off-brief)
  and asks "which one interests you?". The broker gets a notice, not a call yet.
- The customer picks one ("the second one", its name, "can I see it?"): the broker gets a "🔥 Hot lead, ready to
  close" call card with the property and the customer's words; Rania offers the broker's free times, and a time
  given books the viewing. The Inbox shows 🔥 on the lead.
- Nothing fits: the broker gets the qualified lead to find options.
- The owner's setting (Qualification page): when (after qualifying / as soon as something fits / never), how many
  (1 to 5), and what makes a lead hot (a pick, a viewing request).

**Demo catalog, photos and maps:** ✅ checked in the browser (18/18), approved by the product owner 29 Oct.
- 32 fictional listings across 11 Dubai areas: 25 for sale, 7 for rent, 2 without a permit. They arrive through a
  fictional portal feed (`diwan/demo_feed.xml`), the same path a brokerage's real feed takes.
- The feed reader now takes photos, map location, size and description from any portal feed.
- Photos: 17 free-licence pictures from Wikimedia Commons (`web/img/demo/`). Each shows its author and licence and
  says it is the area or a similar home, not the unit.
- A photo gallery on each listing, a "For sale / For rent" filter, rent shown per year.
- Maps (OpenStreetMap): a small map on each listing and a Map view of the filtered catalog. Pins are colour-coded;
  hover shows the price; clicking a pin opens the listing. Without internet the map says so.
- Found and fixed with the bigger catalog: "Any villa in JVC?" matched the community called "The Villa", and a buyer
  could be offered a yearly rental. Areas are now matched as whole names (JVC, JBR, JLT, the Palm), in one place for
  the search and Rania; buyers see sales, tenants see rentals.

**Memory screen and agents:** ✅ checked in the browser (32/32), approved by the product owner 29 Oct. Redesigned the same
day: a deal reads left to right (who → what they said → what was built on it → checks), and the Agents view shows departments
with 14 numbered flows between them, counted from the log.
- The correction is visible:
  - replaced lines fade;
  - the deck shows "sent back";
  - work resting on a replaced statement gets ⚠;
  - the deal dot has an outline;
  - the slider steps through the deal's own events;
  - ▶ Play runs the history like a film.
- Agents view: the whole team, reporting lines, and the handoffs the log shows (gold arrows), each agent's charter on click.
- The owner adds agents (listen for an event → write → hand a task to a person; never act alone); pause, resume, remove.
  Built-in agents are protected.
- Fixed: the Marketing memory view crashed after a portal feed update.
- What everything on the screen means: `docs/memory.md`.

**Knowledge and catalog:** ✅ 22 of 22 checks.
- Tabs, search, filters, add, edit with history, retire and restore, proposals, stale re-confirm, usage counts.
- 1,000 listings paged, with filters and photos or placeholders.
- Brokers propose prices; they never edit them.

**Docs:**
- `docs/front-office.md`: the design and the presentation.
- `docs/front-desk-status.md`: the flow and coordination.
- This file.

## 3. Not built yet

- Intake hardening: duplicates, bursts, spam, takeover from the broker's phone (item 4).
- Profiler tags and contact consent (item 5).
- The written 5-line brief for the broker and the CRM (item 7).
- Instagram: keep the post a comment came from; a short public reply with details in DM; DMs.
- Leads per Marketing post (item 9).
- The real Property Finder Atlas API. Today: signed webhooks plus a feed URL (which now carries photos and location).
- A reserved/sold control on the Catalog page.
- The header search on every screen and the phone-width layout (item 3).

## 4. Needs your decision

1. ~~No matching knowledge while qualifying~~ decided: finish qualifying first; the question goes on the broker's card.
2. **Reserved/sold control on the Catalog page:** add it before item 3, or leave it?

## 5. Known issues

- Rules mode matches knowledge by shared words: "the chiller fees at Marina Crest?" gets the office's fees answer. Muse Spark answers or hands it over correctly; rules mode is only the fallback.
- Rules mode reads "how much commission do your brokers keep?" as a price question. Nothing leaks, and Muse Spark answers it correctly.
- Permissions trust the "Acting as" name chosen in the browser: fine for the demo, not for real use.
- NVIDIA's free model takes 8 to 24 s per reply because its thinking can't be turned off. Muse Spark is the demo model.
- Nothing is committed. The commit is planned after item 3: own hunks only, under the alifiya-saifee identity.

## 6. Next, in order

1. Item 3: header search, phone width, commit.
2. Item 4: Intake.
3. Item 5: Profiler tags and consent.
4. Item 6: the waiting-for-broker stage.
5. Item 7: the brief and follow-up.
6. Item 8: re-check Nova.
7. Item 9: leads per post, once the event shape is agreed with Marketing.
8. End-of-day report, then one live Muse Spark pass with its cost.
