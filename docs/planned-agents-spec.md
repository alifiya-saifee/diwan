# The three planned agents, built

Invoice clerk, Transfer tracker and Positioning were on the map as "planned". This spec builds each one to its charter.

## Positioning (Marketing · rules)

**Charter:** holds who we serve, what we promise and what makes us different. Changed only by the owner (or the Marketing manager); never rewritten alone.

- The brand profile gains **What makes us different**, beside "Who we are" (the promise) and "Who we talk to" (who we serve).
- When any of the three changes, the Positioning agent records the new **positioning sheet** (`positioning.updated`): all three, who changed them, and when. The writers already read the brand profile, so the next script uses it.
- **Studio → Setup → Our brand** shows the new field in "Who we are".

## Transfer tracker (Operations · Muse Spark)

**Charter:** tracks the developer NOC, the trustee appointment and the transfer documents, and chases what is late.

- Every hour, it looks at each open transfer step. A step that has waited longer than the office's limit (`transfer_chase_days`, default 3 days) on its party gets a **chase**:
  - **Muse Spark drafts a short, polite chase** to the party the step waits on (the developer, the trustee office, the bank), naming the step, the property and how long it has waited. Without a model, a plain template.
  - The transactions officer is told, and the draft waits for them: nothing is sent by the agent.
- At most one chase per step per day. A step behind the ready-for-transfer gate isn't chased until the gate opens.

## Invoice clerk (Finance · Muse Spark)

**Charter:** drafts outgoing commission invoices from the live price and the owner's rate (already built, on rules, filed under this agent), and checks supplier invoices: VAT, TRN and duplicates.

- **Finance → Check a supplier invoice:** paste the invoice's text.
- **Muse Spark reads it** into supplier, TRN, invoice number, date, net, VAT and total. Without a model, plain rules read the labelled lines.
- **Rules check every number:**
  - the TRN is 15 digits;
  - VAT is 5% of the net amount (within AED 1);
  - the total equals net plus VAT;
  - it isn't a duplicate (the same supplier and invoice number already checked).
- **The result** is either **a ledger row** (all checks pass) or **a hold** with each reason, plus a task for the person who holds Finance. Nothing is paid: releasing money stays a person's job.

## Done checklist

- [x] Code: saving a new "What makes us different" records a positioning sheet from the Positioning agent, and the writers' brief includes it.
- [x] Code: a transfer step waiting longer than the limit gets one chase a day (draft + notice to the transactions officer); a gated step isn't chased; nothing is sent.
- [x] Code: a clean supplier invoice becomes a ledger row; a wrong VAT, a bad TRN, a total that doesn't add up and a duplicate are each held with their reason, and a hold makes a task for Finance.
- [x] Code: none of the three agents is "planned" any more, and each one acts in the log when its trigger happens.
- [x] Browser: Studio → Setup shows "What makes us different", and saving it lights Positioning on the map.
- [x] Browser: Deal desk → Finance → Check a supplier invoice: a clean one is "In the ledger"; one with wrong VAT is "Held" with the reason.
