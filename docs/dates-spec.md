# Dates Rania understands (approved 2 Nov 2026)

A client books in their own words. A written date is never ignored, and when the words could mean two days Rania asks
which, instead of guessing. Each line is checked before it's ticked.

**Checked 2 Nov:** tests offline (`tests/test_dates.py`, 24); browser `e2e/dates_flow.py` 7/7, and the calendar checks that
used to depend on today's date (`own_time_flow` 18/18, `basics_flow` 17/17).

## 1. Written dates
- [x] "10 Nov", "10th November", "Nov 10", "November 10th", "10/11" (day first, as in the UAE): that date, this year, or
      next year once it has passed.
- [x] "the 10th": that day this month, or next month once it has passed.
- [x] A written date wins over a weekday: "Tuesday 10 Nov at 4pm" is 10 Nov, not the coming Tuesday.

## 2. Times in words
- [x] "noon", "midday" are 12:00; "half past four" is 4:30 PM; "quarter past 4" is 4:15 PM; "quarter to 5" is 4:45 PM;
      "4 o'clock" is 4:00 PM.
- [x] Numbers that count things are never a time ("2 bed", "3 million").

## 3. Days in words
- [x] "this weekend" offers Saturday's free times; "next week" offers from next Monday.
- [x] "busy Tuesday, Wednesday works": a day after "busy", "not", "can't" or "no" is skipped.

## 4. When it could be two days, she asks
- [x] The weekday and the date disagree ("Wednesday 10 Nov", but 10 Nov is a Tuesday): "Just to be sure: do you mean
      Tuesday 10 Nov or Wednesday 11 Nov?"
- [x] "next Tuesday": the coming Tuesday or the one after.
- [x] Today's weekday said on that day ("Monday at 4" on a Monday): today or next Monday.
- [x] "this Tuesday" is the coming one, with no question.
- [x] Their answer ("10 Nov", "Tuesday 10 Nov", "the second one", "the first") carries on with what they first asked
      for: the viewing, the call, the move.
- [x] Arabic clients are asked in Arabic.

## Checks
- [x] Tests offline (`tests/test_dates.py`); the two calendar browser checks that depend on today's date name full dates
      (`e2e/own_time_flow.py`, `e2e/basics_flow.py`).
