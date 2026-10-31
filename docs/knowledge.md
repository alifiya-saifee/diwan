# Knowledge and catalog: spec and definition of done

What every agent (Rania on WhatsApp, Nova, the marketing writers) is allowed to know and say, how people keep it
correct, and how the listings catalog works at real scale. Status: **built; all 22 checks pass in the browser** (29 Oct 2026). Nothing here is done until every box in
section 6 is ticked by a check in the browser.

## 1. Who uses it, and for what

| Person | Comes here to |
|---|---|
| Owner (Layla) | Set fees, hours and policies; correct anything wrong; see what Rania relies on |
| Sales manager | Confirm approved answers that brokers wrote during takeovers |
| Marketing manager (Maya) | Keep area guides and the brand; confirm what the AI learned from documents |
| Broker (Omar) | Find a listing fast while on the phone; propose a correction |
| Rania, Nova, writers (agents) | Read confirmed, customer-facing items only, and cite the item they used |

## 2. Kinds of knowledge

| Kind | Holds | Expected size | Changes | Owner (can edit) |
|---|---|---|---|---|
| Company | hours, fees, process, policies, contact | 20 to 80 | rarely | Owner |
| Approved answers | question and answer pairs | grows to hundreds | weekly | Sales manager |
| Listings | price, beds, area, permit, photos, agent, status | 100s to 1,000s | daily (portal feed) | Feed / broker |
| Projects | off-plan: developer, payment plan, handover | dozens | monthly | Sales manager |
| Areas | community facts: schools, metro, service-charge range | about 20 | quarterly | Marketing manager |
| People | broker areas, languages, shifts | 5 to 50 | monthly | Owner |
| Brand | voice, words to use and avoid, sign-off | 1 | rarely | Marketing manager |

A customer's own facts stay in their deal and chat; they never become shared knowledge.

## 3. Every item

- **Status:** proposed, confirmed or retired. Agents use confirmed items only.
- **Audience:** customer-facing (Rania may say it) or internal (staff only).
- **Source:** typed by a person, learned from a document (with the quote), synced from the feed, or written by a broker in a chat.
- **Valid until** (optional): an offer or payment plan ends by itself.
- **Review by:** company and area items are re-confirmed every 90 days, or show as stale.
- **Applies to** (optional): a listing, project or area.
- **History:** every version, who made it, when and why.

## 4. Changing things

- **Edit** makes a new version. The old one stays in the history, marked replaced; agents use the new text from that moment; the memory graph shows the replacement.
- **Retire** (the "delete") hides the item from every agent, with a reason, and keeps it in the history. A retired item can be restored.
- **Who:** the kind's owner edits and retires. Anyone else proposes a change, which waits for the owner.
- Nothing is ever overwritten or erased: corrections are new events, like every other correction in Diwan.

## 5. How agents read it

1. The question is matched against confirmed, customer-facing items: listings by beds, area, budget and status; everything else by full-text search. The agent gets the best 5 to 8 items, never all of them.
2. The agent answers only from those items and cites their ids. No item fits: hand over to a person.
3. When a broker answers something Rania could not, that reply becomes a proposed approved answer for the sales manager.
4. Each item shows how often it was used in replies this week, and the last chat that used it.

Wiring this into Rania's replies and the portal feed belongs to the session building WhatsApp and portals; this spec
gives them one search function and one item format to call.

## 5a. One store, two screens

Knowledge stays small (tens to a few hundred items, edited now and then); the catalog grows to thousands of listings
that change daily and are searched while a broker is on the phone. On one page the catalog would bury the knowledge.

- **Knowledge page:** company, approved answers, areas, projects, brand, as tabs.
- **Catalog page:** its own full-width screen for listings: photo grid or table, filters, paging, search by reference or building.
- **The same underneath:** one item format, one set of edit / propose / retire / history rules, one search across both
  (the header search box and Rania's lookup), and links both ways (an area guide lists its listings; a listing shows
  its area's knowledge). The memory graph shows both.

## 5b. The interface for the WhatsApp and portals session

Code: `diwan/knowledge.py` (no other file needed). Tests: `tests/test_knowledge.py`.

**Search** (the only call Rania needs):

```python
from diwan import knowledge
items = knowledge.search(g, question, k=8)   # g = office.graph(); for_customer=True is the default
```

Returns at most `k` items, best first. With `for_customer=True` (the default) it returns only confirmed, customer-facing,
in-date knowledge and advertised listings (with a permit, and available). Listings must fit the beds, budget ("under 2M")
and area the question names; knowledge is matched word by word. **An empty list means nothing fits: hand the chat to a
person.** `for_customer=False` is the staff search (every item, any status), which the header box uses.

**Item format** (each element of the list, and each row on both screens):

| Field | Meaning |
|---|---|
| `id`, `cite` | the id to put in the reply's refs: `K7` or `listing:MC-1204` |
| `tab` | company, answer, project, area, people, brand, or listing |
| `title`, `text` | what may be said (for a listing, `text` is "2 bed apartment in Dubai Marina · AED 2,350,000") |
| `record` | the one quotable line, the same as `graph.record(id)`, for the prompt |
| `status` | confirmed, proposed, retired (listings: available, reserved, sold, off-market, retired) |
| `audience` | customer or internal |
| `usable` | true when an agent may say it to a customer |
| `version`, `valid_until`, `review_by`, `stale`, `applies_to`, `source`, `quote` | as in section 3 |
| `used` | `{"week": n, "total": n, "last_chat": phone}`, counted from the refs on sent messages |
| `listing` | listings only: `ref, community, beds, type, price_aed, permit, advertised, agent, photo, offering` |

**Changes for reception.py** (the WhatsApp session's file; the two unticked checks in section 6 pass once these are in):

1. In `prompt_sources`, replace `out |= {k.id: g.record(k.id) for k in g.of("knowledge", status="confirmed")}` with
   `out |= {i["id"]: i["record"] for i in knowledge.search(g, text) if i["tab"] != "listing"}`.
   Today every confirmed item reaches the model, internal ones included. In the browser check, Rania told a customer
   "our brokers keep 50% of the commission on their own deals", which is an internal-only item.
2. When `search` finds no knowledge item and no listing fits, hand the chat over instead of calling the model. (Rania
   answered the yachts question from "About us" instead of handing it over.)
3. Keep sending citations as `refs`: usage counts read them.
4. When a broker replies in a chat that Rania handed over because she could not answer, call
   `knowledge.propose_answer(office, question, reply, by=broker, chat=phone)`. It waits for the sales manager.

**For the feed** (portals.py, leads.py):

- ~~Add `photos` (a list of image URLs) to `parse_feed`.~~ Done 29 Oct: `photos`, `lat`/`lng` (from `geopoints` or
  latitude/longitude), `size_sqft` and `description` come from the feed; the feed always wins for them. The catalog
  shows `photos[0]` on the card, a gallery and a map on the listing.
- When a listing leaves the feed, `sync_listings` writes `n.props | {...}`, and `n.props` now carries `versions` and
  `retired`. Write the feed fields only.
- Skip listings whose `status` is `retired`: re-adding them would bring back a listing a person retired.
- An accepted broker price differs from the feed until the feed catches up, so the next sync puts the feed price back.
  That is right if the feed is the source of truth. If not, skip `price_aed` while a newer `item.edited` exists.

Events (in `events.py`): `item.edited`, `item.retired`, `item.restored`, `item.reconfirmed`, `change.proposed` and
`change.decided`, folded into the graph by `knowledge.apply`. An edit's old version becomes a `version` node, which the
item `replaces`.

## 6. Definition of done (each checked in the browser, with a screenshot)

Knowledge page
- [x] Tabs for each kind, with counts
- [x] Search box finds an item by any word in its title or text, across knowledge and the catalog
- [x] Filters: status, audience, stale, area
- [x] Add an item (any kind) with audience and review date
- [x] Edit an item: the new text shows, the old version is in its history
- [x] Retire an item with a reason; it disappears from the list (and from agents); "show retired" brings it back; restore works
- [x] A non-owner's edit becomes a proposal the owner can accept or reject
- [x] Stale items are marked, with a one-click re-confirm
- [x] Empty state for each tab says what to add and how
- [x] Usage: "used in N replies" on each item

Catalog (its own page, linked from Knowledge)
- [x] 1,000 listings load and scroll without lag (paged, 50 at a time)
- [x] Filters: area, beds, price range, status, agent, has permit
- [x] Search by reference, building or title
- [x] Each listing shows a photo (from the feed) or a clear placeholder, price, permit, status and agent
- [x] A listing without a permit is marked "not advertised" and is never offered by Rania or the studio (studio part: code test `test_no_permit_no_reel`)
- [x] A broker's price change is a proposal; once the listing owner accepts it, it becomes a new version and Rania quotes the new price at once
- [x] A price agreed with one customer stays in that deal: Rania never offers it to another customer

Agents
- [x] After an edit, Rania's next answer uses the new text (checked on the sandbox WhatsApp line)
- [x] After a retire, no agent cites the item
- [x] An internal-only item is never said to a customer (reception uses `search` since 29 Oct; checked in Test Rania, offline and on Muse Spark)
- [x] A question with no matching item is handed to a person: at once when the lead is not being qualified; while it is, after qualifying, on the broker's qualified-lead card as "Asked, not answered yet" (decided by the product owner 29 Oct; checked in the browser)

Memory graph
- [x] An edit shows as version 2 replacing version 1; a retire shows the item dimmed with its reason

## 7. Decisions

- **Listing prices: brokers always propose, never edit.** Decided by the product owner. The catalog price is one price
  for every customer, so changing it is the listing owner's decision. A price agreed with one customer ("2.5M for you")
  is not a catalog change: it lives in that customer's chat and deal, and no agent repeats it to anyone else.
- **Review period, per kind** (decided): fees and policies 90 days; company basics 180 days;
  area guides 90 days; approved answers 180 days; projects until their valid-until date; listings have no review date
  (the feed is their source) but are flagged when the feed has not updated them for 7 days.
- **Who owns listings** (interpreted while building): the Owner and the Sales manager (Rashid) accept price changes;
  brokers propose. Layla, as Owner, may edit every kind.
- **Maps** (approved by the product owner 29 Oct): OpenStreetMap through Leaflet; a pin per listing from the feed's
  location. Demo photos are free-licence (Wikimedia Commons) pictures of the area or a similar home, each credited.
- **Photos** (decided): from the portal feed first; upload is allowed for listings that are
  on no portal (off-market, pre-launch) and for areas and projects. A feed photo wins over an upload.
