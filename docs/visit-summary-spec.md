# Part 4: after the visit (approved 30 Oct 2026)

The client's side first: they told the broker what they liked and what worried them, and the next message should show
we listened. Each line is checked in the browser like a user before it is ticked.

**Checked in the browser 30 Oct, 7/7** (`e2e/visit_flow.py`, rules mode, a scratch database) and once on live Muse Spark
($0.025: the summary kept only the client's words; the follow-up answered the kitchen worry). Tests: `tests/test_followup.py`
(+3), `tests/test_calendar.py` (+1). Tested through the API only, not the browser: "Done with notes" (Done opens after the
appointment time, and Rania never books in the past, so a fresh demo has no past appointment to mark).
The microphone itself was not used in this check (the turns were typed on the same page); live voice was checked
by the Deal desk session. Notes are the broker's words, not the client's, so a follow-up built on notes never quotes them back to the client.

## Getting the client's words
- [x] Recording: from the appointment, "Record the visit" opens the meeting page for that deal. Nothing is recorded until
      the client agrees; the broker can use the microphone (Muse Voice Transcribe) or type what was said.
- [x] No recording: the broker types a few lines on the appointment ("loved the view, kitchen too small, will talk to
      his wife") when marking it Done.

## The visit summary (an agent, never a guess)
- [x] Made when the recorded meeting ends, or when the broker marks the appointment Done with notes.
- [x] It says: how keen they seemed (keen / thinking it over / not for them), what they liked, what worried them, any
      change of budget, and the next step. Each point carries the words it came from; a point whose words are not in
      the recording or the notes is dropped. Muse Spark writes it when connected; plain rules otherwise.
- [x] It shows on the lead in the Inbox and on the appointment in the calendar.

## The follow-up uses it
- [x] The follow-up drafted after the visit answers their worry ("you mentioned the kitchen is small: I'll send two with
      bigger kitchens") and names the next step they agreed. Never a word about compliance.
- [x] "Not for them": the follow-up thanks them and asks what to change, and does not push the same property.

## Not in this part
Agreement to keys (part 5).
