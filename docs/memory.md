# The Memory screen: what it is, how to read it, what should happen

The Memory screen draws the office's memory as a map. Every dot is something the office knows or is doing, and every line says why. Its one job is to answer **"why does the office believe this, and what rests on it?"** Everything in Diwan leads back to the words a customer actually said.

Page: `web/graph.html` (Marketing session's file). Data: `/api/graph`, built by `diwan/graph.py` from the event log.

## 1. What it really is (the deeper idea)

Most office software keeps the *current answer*: "payer: Tariq". When the customer changes their mind, someone overwrites the field. Nobody knows that the payment task, the compliance check, the manager's approval and the slide in the deck were all built on the old answer. Those keep going, quietly wrong. In a brokerage that is a money-laundering, compliance and trust problem.

Diwan keeps something else: **who said what, and what was built on it.**

- **Nothing is overwritten.** Every change is a new event in an append-only log. The graph is rebuilt from that log every time.
- **Every piece of work points at the statements it rests on.** A task, an approval or a slide is linked to the facts behind it, and a fact is linked to the person who said it, with their exact words.
- **So a correction can travel.** When a statement is replaced, the office follows the lines out from it and finds everything resting on it:
  - the work is withdrawn, sent back, or turned into a decision for a person;
  - nothing is silently changed.

The Memory screen makes that visible. It's the proof behind the tagline "the office you can correct":
- **For the owner:** "why did Finance expect money from Tariq?" → click the task, see the fact, see Karim's words.
- **For compliance:** the slider rewinds to any moment: who knew what, and when. Rewinding is safe because the log is never edited.
- **For the agents:** they read the same memory. Each node has a one-line "record", the only line an agent may quote, with the customer's words in it. The memory isn't a picture of the office; it is the office's working memory, drawn.

## 2. The controls

| Control | What it does |
|---|---|
| **The dropdown** (top left) | Which part of memory to draw: **Agents · how the office works**, **Marketing & brand**, **Knowledge & catalog**, or one **deal** (listed newest first). |
| **Find a deal** | Type a customer's name or the property; the deal opens. With hundreds of WhatsApp leads, nobody scrolls a list. The Inbox and Deals pages can also open a deal here with `graph.html?deal=<id>`. |
| **▶ Play** | Plays the history from the start by itself, like a short film of the office, and stops on the present. Press again to pause. |
| **The slider** | Rewinds to any moment. Drag left: the picture is rebuilt as it was then. Drag back to the end: it goes live again and updates as events happen. |
| **"step 23 of 23 in this deal"** | In a deal, the slider steps through that deal's own events only, so every step changes something. The other views count the whole log. |

## 3. A deal, read as a story (left to right)

A free-floating graph piles up into a knot as a deal grows, so a deal is drawn in four columns that read like a sentence:

| **Who** | **What they said** | **What the office built on it** | **Checks and decisions** |
|---|---|---|---|
| the customer first, then third parties they named | each statement with the customer's own words in quotes | tasks, approvals, the deal deck (its slides under it), the chat, viewings | compliance checks, questions, decisions waiting for a person |

- **Lines only go forward:** from a person to what they said, from a statement to the work resting on it, from work to the check about it. A replaced statement sits **right under** the one that replaced it, joined by a red dashed arc.
- **Click anything** and only its own lines stay lit; everything else dims. Click again to clear. The Record panel shows its one line (what an agent may quote) and its links in words.
- **Long labels** are shortened to fit their column; hover for the full record.
- **It scales:** a bigger deal just adds rows. Each deal is drawn on its own, so the number of deals in the office never makes this picture busier.

**Marks:**
- **Faded with ✕:** replaced, withdrawn or refused. It's kept, never deleted.
- **"Deal deck ✕ sent back":** the Fact checker returned it.
- **Orange dashed ring and ⚠:** work that still rests on a replaced statement, waiting for a person.

**Colours:** blue person · green statement · orange task · purple approval · pink deck and slides · red check or decision · orange question.

## 4. The expected flow: Karim's correction, step by step

The demo deal shows the moment Diwan is built for. Karim said his brother would pay the deposit, and the office built on that. Then he takes it back.

**Before:**
1. Karim: "We're looking at two point six million for the Marina unit." → *Deal terms* → slide "AED 2.6M".
2. Karim: "My brother Tariq is helping with the deposit." → *Who is involved*; Tariq appears in **Who**.
3. Karim: "Tariq will send the deposit from his account." → *Who pays*.
4. Karim: "Two hundred sixty thousand deposit, by bank transfer, next week." → *Payment promise*.
5. The office builds on 3 and 4:
   - Finance's task "Expect AED 260,000 from Tariq";
   - Compliance's task "Screen Tariq Haddad" (a third party paying must be screened);
   - Ahmed's approval "Accept the deposit from Tariq";
   - the deck's deposit slides.

**The correction:** Karim says "Actually, forget my brother. I'll pay it all myself."

| # | What the office does (by itself) | On the screen |
|---|---|---|
| 1 | The Scribe records the new statement with Karim's exact words | a new *Who pays: "Actually, forget my brother…"* |
| 2 | It replaces the two old statements (history kept) | the old *Who pays* and *Who is involved* move under it, faded ✕, joined by red dashed arcs |
| 3 | **Compliance hears first:** "Payment arrangement changed", with both quotes | a red check in **Checks and decisions** |
| 4 | Tariq's screening is withdrawn; Karim is screened instead | "Screen Tariq…" ✕; "Screen Karim Haddad, the buyer" |
| 5 | Finance's expected payment from Tariq is withdrawn; one from Karim is created | the old task ✕; "Expect AED 260,000 … from Karim" |
| 6 | Ahmed's approval rested on the replaced statement: it becomes a decision for him, and executing it is blocked | the approval gets ⚠; a red decision "Your approval … rests on a replaced statement" |
| 7 | The Fact checker sends the deck back | "Deal deck ✕ sent back"; the Tariq slide gets ⚠ |
| 8 | Ask Nova "who pays the deposit?": she answers Karim, citing the new statement | (Nova screen) |

Drag the slider back about 9 steps to see "before", or press ▶ Play and watch the office rewire itself. That is the demo moment.

## 5. A WhatsApp lead

Find it by the customer's name. You see:
- the customer;
- what they told Rania, in their words (budget, area…);
- the WhatsApp conversation;
- the work it started: screening, the funding question, a booked viewing.

Qualification answers and Attention cards live on the deal and are shown in the Inbox.

## 6. Agents · how the office works

The office as departments that talk to each other, not 51 loose dots.

**The layout, left to right, the way work moves:**

**Nova** (top) · **Customers** → **Marketing studio** → **Front desk & Sales** → the deal desk (**Compliance**, **Finance**, **Review**, **Operations**) → **Records** and **People in control**

**Each card says:**
- what the department does for the office;
- its agents, with how many actions each has taken (or "planned");
- Marketing's agents, grouped by room (Researcher, Strategist, Copywriter, Producer, Art director, Publisher, Script library).

**Numbered arrows** match the "How work flows" list under the map:

| # | From → to | What passes |
|---|---|---|
| 1 | Customers → Front desk & Sales | a message or meeting: Rania answers, the Scribe keeps their exact words |
| 2 | Marketing → Front desk & Sales | a comment or DM on a post opens a lead tagged with the post (planned) |
| 3 | Front desk & Sales → Marketing | leads and viewings per post and angle, for the strategy (planned) |
| 4 | Front desk & Sales → Compliance | payer, party and money statements reach Compliance first |
| 5 | Front desk & Sales → Finance | a payment promise becomes an expected payment |
| 6 | Front desk & Sales → Review | every deck and draft is checked against live words |
| 7 | Review → Front desk & Sales | work resting on a replaced statement is sent back with both quotes |
| 8 | Front desk & Sales → Operations | terms agreed: Form F and the transfer checklist (planned) |
| 9 | Front desk & Sales → People | a qualified lead goes to its broker with a call card |
| 10 | Compliance → People | checks and reports wait for the compliance officer |
| 11 | Review → People | an approval resting on a replaced statement becomes a decision |
| 12 | Operations → Records | a closed sale and its documents go to the ledger (planned) |
| 13 | Records → Nova | numbers come from records, citing sale ids |
| 14 | Finance → People | payments are marked received by a person; money moves only with a person |

**Arrow styles:**
- **Gold:** the event log shows it happening; thicker means more often, and the list says how many times.
- **Grey:** built, but not in this log yet.
- **Dashed:** planned.

The counts are real: they come from which agent's event caused which.

**Click a department:** what it does, what it **sends** and **receives** (by number), and every agent with its job.

**Click an agent:**
- what it does, what it listens for, what it reads and produces;
- what it does alone, what needs a person, and what it never does;
- what it runs on, and how many actions it has taken.

**Adding an agent (owner only):** press "+ Add an agent here" on the team's card and give:
- its name and what it does;
- what it listens for (a lead qualifies, a customer takes something back, a viewing is booked…);
- the person it hands its work to.

From then on, each time that happens, it writes what its job asks for (Muse Spark) and hands that person a task. It appears in its team's card, with its count. It **never acts alone:** it can't message a customer, change a fact, approve or move money, so it can't get round the office's safety rules.

- **Pause, resume and remove** apply to the owner's own agents. Removing keeps the history; a resumed agent starts from now.
- **Built-in agents** carry the safety duties (screening, the fact check), so they are not removed or paused here; their autonomy is set on the Team page.

## 7. The other two views

- **Knowledge & catalog:**
  - every item the agents may know;
  - the versions an edit replaced (red dashed);
  - retired items, dimmed;
  - changes waiting for an owner.

  This is how you prove Rania only says what is confirmed and current.
- **Marketing & brand:**
  - the brand and what it was drafted from;
  - the research each idea built on;
  - every script with its angle;
  - who picked it or sent it back.

## 8. What it is not

- Not an editor: you change things on their own screens (Inbox, Knowledge, Catalog, Deals); the memory shows the result.
- Not a guess: every dot comes from a logged event, every statement carries a real quote.
- Not the whole office at once: one deal, or one view, so the story stays readable however big the office gets.

## 9. Changed 29 Oct (approved by the product owner; checked in the browser, 32/32)

1. A deal is drawn as a left-to-right story instead of a free-floating graph. Lines start after the words, never through them. Click to light up one item's links.
2. "Find a deal" by name, and deals listed newest first.
3. Replaced statements are faded under their replacement; "Deal deck ✕ sent back"; ⚠ on work resting on a replaced statement.
4. ▶ Play, and a deal's slider steps through its own events.
5. The Agents view: departments, 14 numbered flows counted from the log, every agent's job; owners add, pause and remove their own agents.
6. Fixed: the Marketing view crashed after a portal feed update.
7. Fixed: the demo reset left SQLite's journal files behind, so the next database could fail with "disk I/O error" or "malformed".
