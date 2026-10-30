# Diwan

The back office of a Dubai real-estate brokerage, run by a team of chartered agents you can watch and correct.
Tell the business once: a client meeting becomes facts with exact quotes, the facts become work for every team, and
when the client corrects themselves the office flags compliance first, withdraws only the work that depended on the old
statement, and refuses approvals that no longer match the facts.

Built for the Meta Global AI Developer Hackathon. See [BUILD_LOG.md](BUILD_LOG.md) for what was built and when.

## Run

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env           # add whichever keys you have
.venv/bin/python -m diwan check          # what is plugged in and where each agent runs
.venv/bin/python -m diwan check --ping   # one tiny live call per configured provider
.venv/bin/python -m pytest -q
```

## How an agent turn works

charter -> instructions -> model (live, or a marked recording) -> pack -> quote check -> authority check -> event log

| Runs on | Agents |
|---|---|
| Muse Spark (Meta Model API) | Nova, Sales lead, Scribe, Deck builder |
| Muse Spark Open (Baseten, Fireworks or Modal) | Compliance lead, Source-of-funds analyst, Devil's advocate |
| Code | Payment tracker, Screening analyst, Report drafter, Fact checker, leads that only route |
| Browser | Form F clerk (stops before Submit) |

## The content studio

The Marketing side turns what competitors post into reels for the business. It reads their real Instagram posts, says why
the best ones worked, and writes three scripts for a listing, a product or service, or a topic to explain (an
informational video, spoken to camera), each from its own facts. It can read the company's website for its products and
properties, refresh competitor posts every day, and be talked to by text or voice. Everything starts in the Studio's Setup
tab. A person approves every script and every post; nothing is published without that.

Agents never hold portal or bank credentials. A person approves, submits, pays and files.
All people and deals in demos are fictional.
