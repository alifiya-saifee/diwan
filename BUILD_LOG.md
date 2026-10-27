# Build log

Everything in this repository was written during the Meta Global AI Developer Hackathon building period
(27 Oct to 4 Nov 2026). An earlier private prototype explored the idea; none of its code is in this repository.

## 27 Oct 2026

- Agent roster: 22 chartered agents (16 in the hackathon set). Each charter states the job, allowed sources, what the
  agent does alone, what needs a person, and what it never does.
- One output shape for every agent (the pack): verdict, exact quotes with their source, what is missing, next steps,
  proposed actions. Quotes not found word for word in their source are removed and recorded.
- Authority: every proposed action is allowed, sent to a person for approval, or refused, by the agent's charter.
  Anything a charter does not list is refused.
- Providers: Meta Model API, Baseten, Fireworks and Modal behind one client. Compliance agents run on open weights
  and never move to a hosted API unless that is switched on on purpose.
- Tapes: live replies can be recorded and replayed offline, always marked as recordings.
- Append-only event log; every event names its agent.
