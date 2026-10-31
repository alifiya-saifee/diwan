# Deal desk: spec and definition of done

Session 3 (Review, Compliance, Finance, Operations). Contract: `docs/rooms.md` section 3, "Back office". Checklist:
`docs/sessions.md` section 3. This file says what "done" means for each checklist item and how it is checked in the
browser. Written 29 Oct 2026.

## Who uses it

| Person | Role | Comes to the Deal desk to |
|---|---|---|
| Priya | Compliance officer | see what changed about money first; record screening results; read the source-of-funds view; review a cash-report draft |
| Ahmed | Finance | see expected payments with their quotes; mark one received (with a reference); see what is overdue; re-approve or cancel an approval that rests on replaced words |
| Joseph | Transactions officer | read the Form F plan, fill the portal himself, mark it submitted; tick the transfer checklist |
| Omar (broker), Layla (owner) | | see where a deal stands and why something was sent back |

First five actions on the screen: pick a deal (or search for one); read what changed and who must act; answer the
card waiting for me; mark a payment received; open the Form F plan and see which fields come from which words.

## Rules this desk keeps (from rooms.md)

- Money facts reach Compliance before anyone else acts (the `check.raised` is the first event after the fact).
- Nothing an agent prepares is final: people screen-clear, release money, submit Form F and file reports.
- Every expected payment, Form F field, report line and slide names the fact it rests on; when that fact is replaced the
  work is withdrawn or sent back with both quotes.
- No invented results: with no sanctions list connected, screening prepares the check and a person records the result.

## Checklist (sessions.md section 3), with what done means

1. **The correction end to end.** On the demo office, "Actually, forget my brother. I'll pay it all myself." typed at the
   meeting table gives, in order: the new fact replacing F2 and F3 (history kept); a Compliance check with both quotes,
   first; Tariq's payment task and screening withdrawn; Ahmed's approval A1 turned into a card for him; executing A1
   refused with the reason; the deck sent back naming slide 3; Nova answering "who pays" with F7 and "F3, since replaced".
   *Browser:* meeting page → Deal desk shows each of these; Ahmed presses "Execute" on A1 and sees the refusal; he answers
   the card ("Re-approve on the new facts") and the new approval rests on F7 and executes once.
2. **Split by department, behaviour unchanged.** `agents/compliance.py` (money-change check, screening, source of funds,
   cash report), `agents/finance.py` (payment rules, received, overdue), `agents/operations.py` (Form F, transfer),
   `agents/review.py` (send-backs, draft review). `office.py` keeps the engine and calls them. Same event order, all tests
   green. *Code only* (nothing changes on screen).
3. **Compliance.** Every party is screened: the customer once money is first discussed (not on every enquiry, since every
   WhatsApp lead opens a deal), any named party or third-party payer when said; a payer in dispute waits for the broker. A screening card shows name, role, the quote that named them, and what is missing (date of birth,
   nationality); Priya records "clear" or "possible match" with a note; the agent never clears anyone. The
   source-of-funds view puts the deal size, deposit and stated income side by side with their quotes and lists the proof
   still missing (filed documents count as received). A cash payment promise of AED 55,000 or more drafts a cash report
   with every quote, waiting for Priya; it is sent back if the promise is replaced.
   *Browser:* Priya's view of Karim's deal before and after the correction; a cash deposit said in a meeting produces the
   draft; a second correction sends it back.
4. **Finance.** One expected payment per live promise, each with its quote, payer, method and due date ("next week" is
   the fact's date + 7 days; no date said shows "no date said"). Ahmed marks one received with a reference; it moves to
   Received with who and when, and a receipt is filed with Records. Past due and not received shows Overdue. Releasing
   money is an approval only Ahmed gives, and it runs only while its facts are live.
   *Browser:* mark received (empty reference refused); an overdue payment; release refused after a correction.
5. **Operations.** Form F is prepared when Joseph presses "Prepare Form F" on the Deal desk (highlighted once the broker
   sets the stage to Offer or Form F in the Inbox) or when Nova is told "prepare Form F"; nothing starts by itself. The plan lists every field with its value and source fact, or empty with who must fill it, and stops
   before Submit. A replaced fact sends the plan back with the reason and a new plan is made from the live facts; Joseph
   cannot mark a sent-back plan submitted. The transfer checklist lists the steps (Form F signed, developer NOC, manager's
   cheques, trustee appointment, title deed) with who each one waits for; Joseph ticks them.
   *Browser:* plan → correction → plan sent back with the reason → new plan; Submit marked by Joseph; checklist ticked.
6. **Review.** A draft is checked when it is made: one using a replaced fact is sent back at once and never shown as
   ready; otherwise `review.passed`. Every send-back names the slide or field, the old quote and the new one.
   *Browser:* the deck after the correction shows "sent back" with both quotes; a new deck from live facts shows passed.
7. **The Deal desk screen and the floors.** `web/deal.html`: a list of deals (search by customer, property or deal id;
   filter "needs someone"; paged at 50) and one deal's Changes, Compliance, Payments, Paperwork and Review sections, each
   card with its quotes and the person it waits for. "Acting as" decides which buttons a person may press. The 3D floors
   of Compliance, Finance, Operations and Review show their open work from the log.
   *Browser:* 1280 wide and phone width, no sideways scroll; 300 deals in the list still pages and searches; an empty
   office says "No deals yet"; an unknown deal id says so.

## The three views (approved by the product owner 29 Oct, from the mock https://claude.ai/artifact/QhbpjWAm81BRsJnZmwZW5b)

As deals pile up, people work through their own pile and the owner wants totals first, so the desk has three views of
the same deals and one deal opens in a side panel:

- **Overview**: the latest correction and what it set off (Compliance first, tasks withdrawn, approvals back, drafts
  sent back), corrections this week, and four tiles (waiting for people, money in the next 7 days and overdue,
  Compliance, Paperwork). Every number opens exactly the deals or the work behind it. Money expected day by day; deals by stage.
- **My work**: one queue per person across every deal, most urgent first, acted on in the row (Reviewed, Clear,
  Received, I submitted it, Answer…); a row that needs the story opens the deal.
- **Deals**: the pipeline as a sortable, searchable table, 50 a page, with each department's state and who it waits for.
- **Catch-up**: deals recorded before a Compliance rule existed get it when the server starts (adds only what is missing).
- Compliance asks the broker, once, how a purchase is funded when a price or deposit is on the table and the customer
  has not said; the question closes itself when the customer says it.
- The page refreshes live but never while someone is typing.
- **Roles, not names** (product owner, 30 Oct: nothing hard-coded, everything from the database): Compliance, Finance
  and Paperwork work goes to whoever holds the role. The owner assigns holders on the Overview (`setting.changed`,
  person `desk`); until then the team member whose role says so holds it; with nobody in a role the work says so.
  A role's open work moves with the role; a question addressed to a broker stays with that broker.

## Next, in order (approved by the product owner 30 Oct)

8. **Rules as the owner's settings, per kind of deal.** Nothing the office decides lives in code. The owner edits, on the
   Deal desk, with every change kept in the log (`setting.changed`, person `desk`):
   - the cash-report limit (default AED 55,000) and which payment methods count as cash;
   - for each kind of deal (ready sale, off-plan, rental): its stages, its paperwork steps with who each waits on, the
     usual deposit and fee percentages, and its closing checklist. Ready sales start from today's steps; off-plan and
     rentals start from the usual Dubai steps in the mock, which Joseph and Priya confirm before they're switched on;
   - Dubai defaults are filled in once, so a new office starts working and changes only what differs.
   *Done means:* the owner changes the cash limit to AED 50,000 and a 52,000 cash promise drafts a report; a step added
   to a kind appears on the next deal of that kind and not on deals already past it; someone who isn't the owner can't
   change anything; every change shows who made it and when. Rentals and off-plan also need the listing's
   ready/off-plan and furnishing fields (Front desk & Sales) before a deal's kind can be read from its listing; until
   then the broker sets the kind once.

9. **Closing a deal, then Records** (mock approved 30 Oct, the same link). Reaching the last stage doesn't finish a
   deal. It is **Closing** until four items are done, each waiting on its role:
   1. final price and commission (or final rent and agency fee) confirmed by the broker, filled in from the deal's facts
      with their quotes;
   2. commission invoiced and paid (Finance), to the buyer, the developer or the tenant depending on the kind;
   3. every compliance item closed (Compliance): no open screening, proof or cash report;
   4. the documents filed (Paperwork): title deed copy, Form F and receipts; SPA and Oqood; Ejari, contract and inventory.

   Then "Close the deal" records the sale with Records (price, commission, broker, date, kind, source), so the owner
   page, Nova's numbers and Marketing's source report count it. The deal leaves the live pipeline for the archive,
   searchable under "Closed", kept at least five years, and corrected only by a new entry. After closing, what keeps
   running depends on the kind: nothing for a ready sale (Property management if the owner asks); the payment plan to
   handover for off-plan; for a rental, the remaining cheques, a renewal question to the broker 90 days before the end,
   and the deposit refund after the move-out inspection.
   *Done means:* the button stays off until all four items are done; each item shows in its holder's My work; closing
   writes one sale that Records finds and Nova's "what did we sell" counts; the Overview's "After the sale" numbers open
   their deals; a closed rental still shows its lease work. **Needs the Records session's agreement first** on how the
   Deal desk hands them the sale (`office.close_sale`, theirs), written in the changelog before either side builds it.

10. **The deal room plan: every touchpoint after the yes** (approved by the product owner 30 Oct:
    https://claude.ai/artifact/5ofKRkJSPJstsj7NC9L1Mm). Each amount comes from the client's words, a signed document or
    the owner's settings, never typed twice:
    - a deal's **terms** from its signed documents (Form A or B and its rate, another agency and its share under Form I,
      the developer, the tenancy dates and furnishing), recorded by the broker, the transactions officer or the owner,
      and fixed once the commission invoice is drafted;
    - **off-plan:** the owner's developer agreements (rate, and the share of the price paid before the developer owes
      it); the SPA's payment plan becomes instalments into the project's escrow, each due on its day, which must add up
      to the price less the booking already expected; the handover and title deed run on after closing;
    - **rental:** the cheques spread over the year from the contract; after closing, the renewal question to the broker
      the owner's notice days before the end, then the move-out (inspection, deposit refund, Ejari cancelled);
    - **ready sale:** the buyer's mortgage, the seller's loan and the handover as steps; any step can be marked not
      needed with the reason; the DLD fee shown;
    - **KPIs** on the Overview, counted from the log, each opening its deals: yes to closed (per path, against the
      owner's target), stuck (the owner's N days), time per touchpoint, compliance clear before money, corrections
      caught, fall-through with reasons, money overdue by kind, commission billed vs collected, documents missing at
      closing.
    *Done means:* an instalment plan that doesn't add up is refused with the numbers; the developer can't be invoiced
    before its share is paid; an instalment is never ours to release; the commission item waits for the other agency's
    share to be paid; a rental can't close without its dates; every KPI is zero or "—" on an empty office and moves when
    a deal closes. Not in this item: Form C (waiting on the product owner), mortgage amounts, resale before handover.

11. **Stages on the Deal desk, and the agency forms at conversion** (approved by the product owner 30 Oct).
    - **The stage bar** at the top of a deal: Sales' stages (New → Viewed), then the stages of the deal's path, which
      are the owner's settings (ready: Offer, Offer accepted, Form F, Transfer; off-plan: Reservation, SPA, Oqood;
      rental: Offer, Offer accepted, Contract, Ejari, Move-in). Then Closing (from the checklist) and Won. The broker,
      the transactions officer and the owner move it; moving back and Lost need a reason; Won comes only from closing;
      a closed deal doesn't move. The same `stage.changed` the Inbox writes, so both agree.
    - **Conversion** is the path's "converted at" stage (Offer accepted; Reservation for off-plan). Reaching it asks the
      broker once who is on the other side, unless the deal already says: only us (our listing, our buyer), we act for
      the seller and another agency brought the buyer, or we act for the buyer and another agency holds the listing.
      The other agency's name, ORN, agent, BRN and share are kept in the deal's terms. (Front desk & Sales are asked to
      note "came with an agent" at enquiry, so this can be read instead of asked.)
    - **The forms the deal needs** are drafted from the record: on a ready sale, Form A and B for only us, A and I for
      the seller's side, B and I for the buyer's side; on any path, Form I when another agency is on the other side.
      Each is a draft checked by Review, resting on the price the client said; our agency's name and ORN and each
      broker's BRN are the owner's settings; what isn't on file (the seller's name, the title deed number) is printed
      blank with who fills it. The broker downloads it as a **PDF** and shares it with the client or the other agent
      personally, then uploads the signed copy, which Records files. A changed price or changed terms send an unsigned
      form back and a new one is drafted; a signed form fixes the terms it carries.
    - **The gate:** Form F isn't submitted and no commission invoice is drafted while a form waits for its signature.
    - **KPIs:** deals whose forms are all signed, and the forms waiting per broker; one-agency against co-agency deals;
      the commission given to other agencies.
    *Done means:* a non-broker who isn't the transactions officer or the owner can't move a stage; moving back without
    a reason is refused; Won isn't offered; reaching Offer accepted on our listing asks who brought the buyer; "we act
    for the seller" with Bayut Homes drafts Form A and Form I, each downloadable as a PDF that opens and shows the
    price and the other agency; Form F's submit is refused until both are signed; uploading the signed PDF files it with
    Records and the submit then works; a changed price sends both forms back and drafts new ones.

12. **Converting at the agreed price** (approved by the product owner 30 Oct). When the client says yes, the broker
    (or the transactions officer, or the owner) moves the deal to its conversion stage and enters the agreed price,
    filled in with our listing's price. Below it shows as a discount in amber, above it as a premium in green; a
    property that isn't our listing has nothing to compare. A discount above the owner's limit (default 5%) waits for
    the owner, who approves or refuses with a reason the broker hears. The agreed price becomes the deal's price (a fact
    that replaces an earlier one), so commission, the forms and Form F rest on it; the comparison is kept for the KPI
    "price against the listing" per broker. The stage bar can't cross the conversion stage without it.

13. **Signing a form online** (approved by the product owner 30 Oct). Each person who signs a form gets their own link:
    Form A the seller and our broker, Form B the buyer and our broker, Form I our broker and the other agent. The broker
    makes the links and shares each one personally. The page has no login and no Diwan header: the form's lines, then the
    signer's full name, Emirates ID or passport number, a photo of their signature (PNG or JPEG only, checked from its
    content, at most 3 MB, big enough to show) and their agreement to sign electronically. A link works for one person on
    one version, for the owner's number of days (default 14); a form sent back can't be signed ("This version was
    replaced"). When everyone has signed, the signatures and a signing record (name, ID, time, device, address and a
    fingerprint of the form's lines) go on the PDF, which is filed with Records like an uploaded copy. Printing and
    uploading the signed copy stays available. Links reach a client's phone only when `PUBLIC_BASE_URL` is set.

14. **The documents a client sends** (approved by the product owner 30 Oct). At conversion each party on our side (the
    buyer, the seller, the tenant) gets one link for the documents the owner lists for them (buyer and tenant: Emirates
    ID front and back, passport, visa; seller: the same with the title deed; a company: its trade licence). The broker
    copies the link. Each upload is checked at once and a bad one is turned away with what to do and never kept: a real
    JPEG, PNG or PDF under 8 MB; a photo big, light and sharp enough to read; not the same file as another document; the
    details typed well formed (an Emirates ID number 784-YYYY-NNNNNNN-N, an expiry in the future). Things a person should
    look at are flagged, not refused: a check digit that doesn't add up, an expiry within 60 days, a name on the card
    unlike the deal's. The compliance officer compares each photo with what was typed: "It matches" saves the details
    to the client's file and archives the document with Records; "Send back" shows the client the reason on their link.
    Rania reminds the client on WhatsApp every 2 days in the daytime (9:00 to 20:00 Dubai) while anything is missing,
    never mentioning checks; after 3 reminders, or with no WhatsApp on file or no public address for the link, the
    broker is asked to call. Reading the card itself needs a vision provider the owner approves for real IDs; until
    then the client types the details and a person checks them.

15. **Tax invoices and receipts as PDFs** (asked for by the product owner 30 Oct). Sending the commission invoice gives
    it Diwan's next number in one sequence that is never reused (the owner's prefix, the year, a running number:
    INV-2026-0001), unless Finance types the number their own system gave it. The tax invoice prints our agency's name,
    address and TRN (the owner's settings), who it is billed to (the buyer, the tenant or the developer) and their TRN
    if given, what it is for, the amount before VAT, the VAT and the total in dirhams; before it is sent it is marked a
    draft. Every payment and commission marked received has a receipt with its reference. Our accountant confirms the
    layout against the Federal Tax Authority's requirements before invoices go to clients.

16. **Form F signed online, fees, and the IDs given at signing** (asked for by the product owner 30 Oct, "the complete
    flow"). Form F's plan is a PDF too, with who holds the deposit (the owner's setting: the seller's agency, in trust)
    and the usual deposit; the buyer, the seller, our broker and, on a co-agency deal, the other broker each get a
    link. When everyone has signed, the signed Form F is filed with Records and the paperwork step "Form F signed…"
    ticks itself. On every signed form, what a signer gave when signing (their ID or passport number, the seller's name)
    fills their blank lines. The usual fees are the owner's settings per path, each with who pays it (the DLD fee, the
    trustee office fee, Ejari), shown on the commission card; the transactions officer confirms the amounts.

17. **Which property the deal is on** (design approved by the product owner 31 Oct). A deal opened from a WhatsApp,
    Instagram or portal message has only a placeholder ("WhatsApp enquiry"). The box that takes the agreed price also asks
    **whose property it is**, and the answer settles who is on the other side too, so the broker isn't asked twice:
    - **Our listing:** search by ref, name or area and pick one; its price fills the agreed price and the discount check
      runs against it. Asked next: did another agency bring the buyer? If yes, the other agency's details.
    - **Another agency's listing:** the property is typed; the agency, its ORN, its agent, the agent's BRN and its share go
      on the deal's terms as before (we act for the buyer: Form B and Form I on a ready sale). There is nothing to compare
      the price with and nothing of ours to reserve.
    - **From a developer** (off-plan only): the developer comes from the owner's agreements, plus the project and the unit.
      The developer's rate and trigger apply. With no agreements yet the screen says the owner adds them first.
    A ready sale and a rental offer the first two; off-plan offers all three, the developer first. Each agency used once
    is offered again, filling its ORN and agent.
    **The same form opens on the deal** for a deal already converted (it replaces the "other side" question) and to
    change the property. Who may: the broker, the transactions officer, the owner.
    **A change is recorded, never overwritten** (`setting.changed`, key "property", with who and when). Unsigned forms and
    an unsigned Form F plan go back and are redrafted. A signed form, a signed or submitted Form F, a drafted commission
    invoice or a closed deal fixes the property. On a converted deal, picking one of our listings compares it with the
    price already agreed; a discount above the owner's limit needs the owner to do it.
    **The listing follows the deal:** converting marks our listing reserved, so Rania stops offering it and no other deal
    can pick it; changing the property or marking the deal Lost releases it; coming back from Lost takes it again if it
    is still free; closing marks it sold, or let on a rental.
    *Done means:* (1) a placeholder deal can't convert without a property; (2) picking our listing shows it on the deal
    list, the Inbox, the forms and the closed sale, and compares the price; (3) a listing reserved by another deal is
    not offered and is refused if sent; (4) an empty search says so, and search works at thousands of listings;
    (5) another agency's listing drafts Form B and Form I with no "other side" question, and refuses a missing agency or
    share; (6) a second deal offers that agency again, details filled; (7) a developer unit sets the developer's rate,
    and an unknown developer is refused; (8) a rental doesn't offer the developer; (9) Ali-style deals already converted
    get the form, which closes their open question; (10) a change sends back unsigned forms and redrafts them, and a signed
    form refuses it; (11) Lost releases, closing sells; (12) someone else can't set it; the phone width has no sideways
    scroll. Deals that already name one of our listings keep working unchanged.

18. **The four rooms closed up** (asked for by the product owner, 31 Oct; from [closed-loop-spec.md](closed-loop-spec.md) and the
    room lists in [closed-loop-checklist.md](closed-loop-checklist.md); decisions taken are in
    [open-questions.md](open-questions.md)).
    **Compliance gates the deal.** A clearance (`compliance.cleared`, `compliance.needs_info`, `compliance.blocked`) is the
    officer's, pinned to the live money and party facts, and goes stale when one is replaced. Nothing binding happens
    without it: Form F links, Form F submit, a paperwork tick, a release of money, closing. A possible match is a hit
    (`screening.hit`) that stays open as a hold until the officer resolves it. Risk is rated low, medium or high; high risk or a
    PEP needs the owner's sign-off. Price and finance corrections reach Compliance first. Needing more information asks
    the client through their link, never saying why; a client is never told about a check. A marked payment is checked
    for cash, a third party, a split, crypto and a mismatch with the words. Drafts: cash report and suspicious transaction
    report, for the officer to file.
    **Finance.** Mark received takes amount, date, method, reference, payer and an optional proof; a proof that disagrees
    is flagged before saving; part payments leave the balance open; every mark can be undone with a reason, never deleted.
    Cash at the limit or a third-party payer goes to Compliance and the receipt waits. Otherwise the client gets the receipt.
    Invoices are drafted at the owner's trigger, carry a due date and move through draft, sent, overdue, part paid, received
    or written off. Reminders on the owner's days. Broker commission and other agencies' shares become a payout list for
    the owner. A Finance view shows cash this month, outstanding, the next 30 days, by broker.
    **Deal.** The checklist follows the deal: a cash buyer has no mortgage steps, a seller with no mortgage no liability
    letter, and the party's type picks the documents (resident, non-resident, GCC, company, offshore company, power of
    attorney). Signatures are drawn on screen or photographed; a selfie, a document, a blank page and one line are refused.
    Each upload is answered at once and on WhatsApp. The ladder is 24, 48, 72 hours (nudge, broker call, owner). Expired
    links can be renewed. A gates panel shows Compliance, Finance, Review, Paperwork and the owner; `deal.ready_for_transfer`
    needs all of them on the current facts. A board shows deals by stage. Lost has a reason from the owner's list.
    **Operations.** Forms sent carry their version and are recalled with a short client message when a correction replaces
    them. Each official step (NOC, trustee, Ejari, permit) has a draft listing exactly what to enter, from the record, and a
    person submits and records the reference. `transfer.booked` carries date and place and tells the client what to
    bring; `transfer.completed` is marked by a person and starts the handover; closing emits `case.closed`. Every task shows
    what it waits on and for how long. An Operations view shows all of it.
    **Not real yet, by nature:** no portal is driven (a person types the draft in), no sanctions list or PEP database is
    connected (a person checks and records), IDs and cheques are not read by a vision provider (a person compares), the
    signature check is a first filter on the picture, and messages stay in the sandbox until a WhatsApp line is connected.
    *Done means:* tests for each rule, and `e2e/deal_flow.py` plus a new `e2e/rooms_flow.py` passing in the browser.

## States every section must handle

Empty (no deals; a deal with no money facts; nothing to screen), errors (an action by the wrong person is refused with
who may do it; a missing reference; an unknown approval), and scale (hundreds of deals, dozens of facts per deal).

## Decisions for the product owner

1. **Sanctions lists.** No list is connected, so screening prepares the check and Priya records the result. Connecting
   a real list (UN consolidated, UAE local terrorist list) is a later step.
2. **When Form F starts:** Joseph presses "Prepare Form F" (highlighted at stage Offer or Form F) or asks Nova. Starting
   it automatically on the stage change would need a hook in session 2's stage code; say if you want that.
