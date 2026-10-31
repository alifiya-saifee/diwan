# Part 5: agreement to keys (proposed 30 Oct 2026, to agree with the Deal desk and Records; nothing built yet)

The client's side first: they have said yes. From here they want to know what happens next, what we need from them,
and when they get the keys, in plain words, without chasing. Nobody pressures them, and nobody promises what only the
seller, the developer or the landlord can decide.

Most of this part is already the Deal desk's (`docs/deal-desk.md` items 8 and 9: rules per kind of deal, and Closing
until the final figures, commission, compliance and documents are done, then the sale goes to Records). This page is
what Front desk & Sales builds around it, and the five places where we meet, which each side agrees before building.

## Where we meet (to agree)

| # | With | Proposal | Why |
|---|---|---|---|
| A | Deal desk | **One list of deal kinds.** The Deal desk's per-kind rules (item 8) key on the ids in `deal_kinds.kinds()` (setting person `sales`, key `kinds`). The deal's kind is the deal prop `kind` (event `lead.kind`). A deal with no kind yet: the broker sets it once in the Inbox (`lead.kind`, actor the broker). | Two lists would drift: a kind added in Settings would have no paperwork steps. |
| B | Deal desk | **One list of stages per kind.** New → Viewed stay Sales'; each kind's stages after Viewed are the Deal desk's setting. The Deal desk gives `deal_desk.stages(g, kind) -> list[str]`; the Inbox and `auto_stage` call it instead of their own copy (today `inbox.STAGES` and `deal_desk.STAGES` repeat the same list). | Off-plan and rental deals don't pass through Form F and Transfer. |
| C | Deal desk | **Won is set by closing, not by hand.** At the kind's last stage the Inbox shows "Closing: 2 of 4 done, waiting on Finance" (read from the Deal desk) and has no Won option. "Close the deal" on the Deal desk logs `stage.changed` Won with `sale` (the Records sale id). | Today a broker can pick Won in the Inbox and nothing reaches Records. |
| D | Deal desk | **What the client may be told.** `deal_desk.client_steps(g, deal)` returns the steps a client should know about: `{"text": "Sign the sale agreement (Form F)", "done": bool, "from_client": "your passport copy" or None, "who": broker id}`. Screening, cash reports and anything internal are never in it. Rania answers "what's next / what do you need from me / when do I get the keys" only from this; anything else goes to the broker. | The client gets a straight answer at any hour; compliance stays internal. |
| E | Records | **The sale carries its kind and source.** `office.close_sale(..., kind=, source=)`. `kind` is the deal kind id; for a rental `price_aed` is the yearly rent and `commission_aed` the agency fee. `source` comes from `leads.source(g, deal)` (Sales): the channel of the client's first message, `propertyfinder`, `bayut`, `post:<content id>`, `instagram` or `whatsapp`. Records decides whether sales and rentals are counted apart in "what did we sell". | The owner page and Marketing's "enquiries to sales per post" need the source; rentals shouldn't inflate sales value. |

## What Front desk & Sales builds after A to E are agreed (each checked in the browser like a client)

- [ ] **An offer in the chat** ("We'd offer 2.5 million"): Rania thanks them, says the broker will take it to the
      seller and come back, and never says it is accepted or comments on the price. The broker gets a card with the
      amount and their words; the Scribe keeps the amount as a fact as today. The stage moves to Offer only when the
      broker sets it.
- [ ] **"What happens next?"**: Rania answers from `client_steps` (D): the next step, what we need from them (once,
      plainly), and who will contact them. If a step needs a document from the client, she asks for it once; no
      reminders from her (the broker follows up).
- [ ] **The Inbox stages per kind** (B, C): the stage list follows the deal's kind; the last stage shows Closing with
      what it waits on; Won only comes from closing. The broker sets a missing kind once (A).
- [ ] **`leads.source(g, deal)`** (E), with a test per channel.
- [ ] **After closing**: quiet-client follow-ups stop (already true for Won); the chat stays open for questions; one
      thank-you message is drafted for the broker to send or drop. No offers or marketing to them from Rania.
- [ ] Arabic for each reply; a phone-width check; tests offline; one live Muse Spark pass with its cost.

## Not in this part
The Deal desk's closing checklist, per-kind paperwork, commission invoicing and after-close lease work (their items 8
and 9); the archive and the ledger (Records).
