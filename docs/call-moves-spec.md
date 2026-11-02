# A promised call nobody makes, and when a card reaches the Pool (approved 2 Nov 2026)

The client was told a name; if that person doesn't call, the client hears the new name, and the call never bounces back to
someone who already missed it (loop guard L1 in the Do First list).

## Calls
- [x] After the call limit, the call moves to the free broker with the fewest leads who hasn't missed it.
- [x] It moves at most twice; after that the Sales lead has it ("two brokers missed it: please call, or give it to someone").
      The lead's broker stays the last one it moved to.
- [x] With nobody else on shift it waits, and moves as soon as someone is.
- [x] Each move, Rania tells the client: "Sorry for the wait, Ali. Hamza will call you instead, in the next 10 minutes."
      (Inside their 24 hours; after it, the card is the broker's to call.)

## The Pool
- [x] A card due later than usual from the start (a follow-up date the broker set, an owner to ask, a call at a time the
      client chose) reaches the Pool an hour after it is due, not an hour after it was raised.
- [x] A promised call that moved keeps the Pool an hour after the client first asked, as before.

## Checks
- [x] Tests offline: `tests/test_call_moves.py`.
