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

## States every section must handle

Empty (no deals; a deal with no money facts; nothing to screen), errors (an action by the wrong person is refused with
who may do it; a missing reference; an unknown approval), and scale (hundreds of deals, dozens of facts per deal).

## Decisions for the product owner

1. **Sanctions lists.** No list is connected, so screening prepares the check and Priya records the result. Connecting
   a real list (UN consolidated, UAE local terrorist list) is a later step.
2. **When Form F starts:** Joseph presses "Prepare Form F" (highlighted at stage Offer or Form F) or asks Nova. Starting
   it automatically on the stage change would need a hook in session 2's stage code; say if you want that.
