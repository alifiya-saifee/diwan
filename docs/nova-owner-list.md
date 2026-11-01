# What Nova should do for the owner

Nova is the owner's chief of staff and PA. This is everything an owner would hand her in a day, and where each one stands.

- **Works**: tested in `e2e/nova_owner_day.py`, a whole owner's day against the real Muse on a private copy of the office.
- **Needs an account**: built or ready, waiting on something outside the office to be connected.
- **Not built**: she says she can't, rather than pretending.

Anything that leaves the office (a client WhatsApp, an email, a calendar change) is read back and waits for a yes. Her own voice can't say yes for you.

## She speaks first

| What | Status |
|---|---|
| Says it out loud on a Live call, or waits in the chat | Works |
| A client who is angry, or mentions a lawyer, a refund or a complaint | Works |
| A client who writes about changing bank details | Works |
| A client who is ready to buy | Works |
| A screening hit, a flagged payment, money marked received, a sale closed | Built, not yet tested with a real one of each |
| A reminder falling due | Works |
| Chases staff on stalled leads and waiting decisions every 30 minutes, and tells you | Works |
| Stays quiet for a "thanks" or an ordinary question | Works |
| Sees stuck deals | Not built |

## Morning and the day

| You say | Status |
|---|---|
| "What do I need to know today?" | Works |
| "What's most important right now?" | Works |
| "What should I focus on first?" | Works |
| "Has anything gone wrong overnight?" | Works |
| "What's the plan for tomorrow?" | Works |

## WhatsApp

| You say | Status |
|---|---|
| "Any new messages?" / "Anything important from clients?" | Works |
| "What did Mona last write?" | Works |
| "Who's waiting for a reply?" | Works |
| "Send Mona a WhatsApp saying we'll call this afternoon" | Works: read back, sent on your yes |

Your own number is a separate pathway from the sales line. See "Your own WhatsApp" below.

## Your own WhatsApp

Sales WhatsApp stays with Rania under Front desk & Sales. Your own number is read by Nova for you alone, shown on the My WhatsApp page, and kept in its own database, never in the office records or the sales Inbox. Nothing crosses between the two, and a reply goes from the number the message came in on.

| What | Status |
|---|---|
| Sees who is writing: family, friends, important people, clients, staff, vendors, strangers | Works on the stand-in phone |
| "That's my mum", "Treat Ahmed as important", "Mute this number", "Stop telling me about Ahmed" | Works |
| Tells you the matter once, never "you received a message", and groups what arrives together | Works |
| Interrupts a meeting only for an emergency, a legal threat or changed bank details | Works |
| Offers a meeting time from your calendar, then books and answers on one yes | Works |
| Suggests a reply in your style, sends only on your yes | Works |
| "Reply to mum saying…", and asks which one if two people share a name | Works |
| "Who do I owe a reply?", "What did my mum say?" | Works |
| Drops it when you answer on your phone, and offers a reminder for a promise | Works, not yet tested with real phone messages |
| Voice notes turned into words | The conversion works; not yet tested with a real note from WhatsApp |
| "Pass Ahmed to Omar": a note to the broker, not your chat | Works |
| One-time codes are never stored | Works |
| Answering plain client questions alone | Not built: she always asks you first for now |
| Group chats | Not built |
| Linking your real number | Needs an account: the WhatsApp Business app and a linking partner, once UAE support is confirmed |
| WhatsApp alerts and giving her orders by WhatsApp | Built: needs a third number |

## Calendar and meetings

| You say | Status |
|---|---|
| "What's on my calendar today / this week?" | Works |
| "Am I free tomorrow at 3?" | Works |
| "Book a meeting with Priya tomorrow at 3 about the audit" | Works, and warns of a clash |
| "Move my meeting with Priya to 5" | Works |
| "Cancel my meeting with Priya" | Works |
| "Block Tuesday afternoon for the dentist" | Works |
| "Take Wednesday off" | Works |
| "Book Ali a viewing tomorrow at 11" | Works |
| "I'm in a meeting" / "Hey Pocket": silent notes, then a summary and action items | Works |
| Invites to the other person, or your Google or Outlook calendar | Needs an account |

## Reminders and to-do list

| You say | Status |
|---|---|
| "Remind me in 2 hours to call the bank" | Works |
| "Remind me tomorrow early morning to…" | Works |
| "Remind me every Monday at 9 to…" | Works |
| "Make that 7am" / "Cancel my reminder" | Works |
| "Note down…" / "Add to my to-do list…" | Works |
| "What's on my list?" / "Tick off the gift" | Works |
| "Remind me of those things tomorrow" | Works: reads your notebook out |

## Travel and looking things up

| You say | Status |
|---|---|
| "How long is the drive to the Marina at 5?" | Works: from the web, not live traffic |
| "When should I leave for my flight?" | Works: an estimate |
| Flights, hotels, visas, weather, time zones, news, general questions | Works, with the source named. Check prices yourself |
| Book or pay for a ticket or hotel | Needs an account: none is connected, and paying stays with you |

## Email

| You say | Status |
|---|---|
| "Email Alif about the launch" | Works up to the send: writes it, reads it back, sends on your yes |
| Actually sending | Needs an account: your mailbox in `.env` |
| Reading your inbox | Needs an account |

## Team and numbers

| You say | Status |
|---|---|
| "What's Omar working on?" / "Who's behind?" | Works |
| "Tell Omar to call Mona back" | Works, with no deadline unless you give one |
| "Chase everyone" / "What have you chased?" | Works |
| Commission, money due, marketing results, ad spend | Works |

## What she will never do

Pay, sign, approve, submit, file, clear a screening, send bank details, change Settings, or tell a client anything about Compliance. People do these. Writing "pay the DEWA bill" on your list is fine.

## Still to build

1. A button to dismiss something so she stops mentioning it.
2. Stuck deals on her watch list.
3. Naming her, and setting her voice and tone.
4. Notices on staff's own WhatsApp.
5. Your own calendar, inbox and a booking account, once connected.
