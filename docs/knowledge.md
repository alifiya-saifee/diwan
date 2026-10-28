# Knowledge and catalog: spec and definition of done

What every agent (Rania on WhatsApp, Nova, the marketing writers) is allowed to know and say, how people keep it
correct, and how the listings catalog works at real scale. Status: **to build**. Nothing here is done until every box in
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

## 6. Definition of done (each checked in the browser, with a screenshot)

Knowledge page
- [ ] Tabs for each kind, with counts
- [ ] Search box finds an item by any word in its title or text, across knowledge and the catalog
- [ ] Filters: status, audience, stale, area
- [ ] Add an item (any kind) with audience and review date
- [ ] Edit an item: the new text shows, the old version is in its history
- [ ] Retire an item with a reason; it disappears from the list (and from agents); "show retired" brings it back; restore works
- [ ] A non-owner's edit becomes a proposal the owner can accept or reject
- [ ] Stale items are marked, with a one-click re-confirm
- [ ] Empty state for each tab says what to add and how
- [ ] Usage: "used in N replies" on each item

Catalog (its own page, linked from Knowledge)
- [ ] 1,000 listings load and scroll without lag (paged, 50 at a time)
- [ ] Filters: area, beds, price range, status, agent, has permit
- [ ] Search by reference, building or title
- [ ] Each listing shows a photo (from the feed) or a clear placeholder, price, permit, status and agent
- [ ] A listing without a permit is marked "not advertised" and is never offered by Rania or the studio
- [ ] A broker's price change is a proposal; once the listing owner accepts it, it becomes a new version and Rania quotes the new price at once
- [ ] A price agreed with one customer stays in that deal: Rania never offers it to another customer

Agents
- [ ] After an edit, Rania's next answer uses the new text (checked on the sandbox WhatsApp line)
- [ ] After a retire, no agent cites the item
- [ ] An internal-only item is never said to a customer
- [ ] A question with no matching item is handed to a person

Memory graph
- [ ] An edit shows as version 2 replacing version 1; a retire shows the item dimmed with its reason

## 7. Decisions

- **Listing prices: brokers always propose, never edit.** Decided by the product owner. The catalog price is one price
  for every customer, so changing it is the listing owner's decision. A price agreed with one customer ("2.5M for you")
  is not a catalog change: it lives in that customer's chat and deal, and no agent repeats it to anyone else.
- **Review period, per kind** (recommended, awaiting confirmation): fees and policies 90 days; company basics 180 days;
  area guides 90 days; approved answers 180 days; projects until their valid-until date; listings have no review date
  (the feed is their source) but are flagged when the feed has not updated them for 7 days.
- **Photos** (recommended, awaiting confirmation): from the portal feed first; upload is allowed for listings that are
  on no portal (off-market, pre-launch) and for areas and projects. A feed photo wins over an upload.
