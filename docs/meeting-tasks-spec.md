# Meeting → tasks (demo Part 6)

When a meeting ends, Diwan lists the work people agreed to at the table. Each item has an owner, a date and the words it came from. One press, **Approve all**, sends each item to its owner's My work. Nobody takes notes, and nobody has to brief the team.

## Who uses it

- **The person who ran the meeting** (usually the broker, or the owner). They read the list, fix it, and approve it.
- **Each owner** (Ahmed, Joseph, Priya, the broker). They find their task in Deal desk → My work, with the quote it came from, and tick it done.

## What the agent does (the Next-step taker)

1. **Reads every turn of the meeting.** Both the broker's and the client's words count. "Ahmed will send you the payment plan by Thursday" is the broker's promise.
2. **Proposes items.** Each item has what, who, by when, and the quote, which must appear word for word in a turn. An item whose quote isn't in the meeting is dropped.
3. **Owner.**
   - A staff member named in the words (a first name, or a role word such as "finance", "compliance" or "the transactions officer"), resolved through the team settings, never hard-coded.
   - "I'll …" said by the broker means the broker.
   - "I'll …" said by the client becomes a chase task for the broker: "Check Karim sent the passport".
   - When nobody can tell who, the item goes under **Not turned into tasks: couldn't tell who**, with the quote and an owner picker.
4. **Date.** Read from the words ("by Thursday", "next week", "tomorrow 10am"), with the same reader the Lobby uses. With no date in the words, there is no date. Nothing is guessed.
5. **Changed by this meeting.** Work withdrawn while the meeting ran (because a statement was taken back) is listed with its reason, e.g. *Expect AED 260,000 from Tariq Haddad: withdrawn, F3 was replaced by F8*.
6. **Model and fallback.** Muse Spark when it's connected. Without it, plain rules read "<name or role> will <do something> (by <when>)" sentences.
7. **Limits.** It never creates a task by itself, never gives work to someone nobody named, never invents a date, and never hands out work that rests on words the client took back.

## The screen (Meeting page, after "End the meeting")

The panel title is **"From this meeting: N tasks"**. Each row shows:

- the action, editable;
- the owner, a picker of the team;
- the due date, editable;
- the quote with its speaker.

**Every row can be:**
- **edited** (the action, owner and date);
- **removed** (✕);
- **added** (a manual row via "Add a task": action, owner, date, and no quote, marked "added by <name>").

**Also on the panel:**
- **Not turned into tasks (k)**, each with the quote and a picker to turn it into a task.
- **Changed by this meeting (k)**: withdrawn work, struck through, with its reason.
- **Approve all** creates every row as a task for its owner. The page then shows *Sent to Ahmed (1), Joseph (1)*, with a link to My work.
- Approving twice creates nothing new.

**Empty state:** "Nothing in this meeting was a task for anyone." The page still shows the follow-up.

**Error state:** if the model fails, the rules list is shown, with the note "Read by plain rules".

**Scale:** a long meeting can produce about 20 items. They're listed in turn order, and nothing pages.

## Where the work lands

- A task for the owner, `agent: steps`. It holds the quote, the meeting id and the due date, and rests on any facts the quote used.
- Deal desk → My work shows it to the owner as **From a meeting**, with the quote and a **Done** button.
- The 3D floor flies a card from the Meeting room to the owner's room when the task is created.

## Done checklist

- [x] Code test: Omar's sentence "Ahmed will send you the payment plan by Thursday, and Joseph will book the trustee for next week" gives 2 items. Ahmed's is due Thursday, Joseph's next week, and each carries its quote.
- [x] Code test: "Someone needs to check the parking" goes under *couldn't tell who*.
- [x] Code test: the client's "I'll send my passport tomorrow" becomes a broker chase task.
- [x] Code test: a quote that isn't in the meeting is dropped; the date is never invented.
- [x] Code test: the Tariq payment task withdrawn during the meeting is listed under *Changed by this meeting*.
- [x] Code test: Approve all creates the tasks once; a second press creates none.
- [x] Code test: edit, remove and add change what's created; a picked owner on an unclear item creates it.
- [x] Code test: the owner comes from the team settings (change the finance holder, and the "finance will…" item goes to the new person).
- [x] Browser, as Layla: run the meeting (consent, Omar's line, Karim's correction), end it. The panel shows 2 tasks, 1 unclear (if said) and 1 withdrawn. Edit one date, then Approve all.
- [x] Browser, as Ahmed: My work shows "Send the payment plan" with Omar's quote; Done closes it.
- [x] Browser, 3D floor: cards fly from the Meeting room on Approve all (checked frame by frame: Priya's card lands in Compliance).
- [x] Browser: a meeting with no promises shows the empty state.
