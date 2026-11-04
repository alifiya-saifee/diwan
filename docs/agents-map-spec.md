# The agents map (Memory → How the office works)

A map of the whole office: every department, its agents, what each one does, and how work passes between them, agent to agent.

## Who uses it

- **The owner:** to understand and explain how the office runs, and to add an agent to a team.
- **Anyone on the team, and judges:** to see who does what and why.

## What changes

1. **Easy to find.** Tabs at the top of Memory: **How the office works** (shown first) · **A deal's story** · **Marketing** · **Knowledge**. `graph.html?deal=…` still opens a deal's story.
2. **Agent-to-agent lines.** Clicking an agent draws lines on the map from that agent to every agent it works with:
   - **Gold, solid:** handoffs the log has seen, thicker when more frequent, with a count.
   - **Grey, dashed:** links in the design: who checks its work (the charter's reviewer) and the lead it reports to.
   - The other agents' rows are highlighted; everything else dims. Clicking it again, or pressing Esc, clears it.
3. **The agent's process card** (side panel) adds four rows to what's there now: **Reports to**, **Checked by**, **Receives from** and **Hands work to**. Each linked agent is clickable, and each link shows what passes and how often.
4. **Department zoom.** A department's panel gets a **Zoom in** button: a focused map with the agents that send work into this department on the left, its own agents in the middle, and the agents or people it hands work to on the right, with every line drawn and labelled. A **Back to the whole office** button returns.
5. **Add an agent** (owner only, the "+" under a department): the form adds **Role** (a short title) and **Deliverables** (what it produces) to Name, What it does, Listens for, Team and Hands its work to. The new agent appears on the map at once, with its own card and lines.

## Rules

- Every line comes from the log or the agents' charters. Nothing is drawn as a sample.
- Custom agents keep their limits: they can't message clients, change facts, approve or move money.
- An empty log still shows the designed links (grey) and says "not seen in the log yet".

## Done checklist

- [x] Code test: the map data includes agent-to-agent links: a handoff seen in the log (with count and kinds), the reviewer link and the reports-to link.
- [x] Code test: adding an agent with a role and deliverables keeps both, and its card shows them as "Produces".
- [x] Department zoom: worked out in the page from the same links, so checked in the browser, not by a code test. Compliance showed 8 lines: inbound from the Scribe and the Follow-up drafter, outbound to Priya and the Devil's advocate.
- [x] Browser: Memory opens on **How the office works**, and the tabs switch views. `?deal=` still opens a deal.
- [x] Browser: clicking the Scribe draws lines to the agents it hands to; the card lists them with counts. Clicking again clears.
- [x] Browser: Compliance → **Zoom in** shows the focused map with labelled lines, and **Back** returns.
- [x] Browser: as the owner, **+ Add an agent here** under Sales with a name, role, deliverables and the rest → the agent appears in Sales, and its card shows the role and deliverables.
- [x] Browser: at phone width the map stacks, and the lines hide without breaking anything.

## Added on 3 Nov, at the owner's request

- **The map shows the office's real rooms.** Front desk (Rania) is separate from Sales, and the Deal room and the Lobby (host plus each room's rep) appear. Every agent sits in the same room as in the 3D office.
- **Heads and reporting lines.** Each department card shows its head first (★), then each agent, with those who report to it indented underneath. The zoom shows the same order.
- **An agent under an agent.** The add form's **Reports to** lets the owner place a new agent under the team's head or under any agent in that team (for example a Scribe intern). An agent from another team is refused.
- **An agent between two teams.** The add form's **Where it sits** offers "Between X and Y" for every pair of teams that pass work to each other. The agent sits on the arrow, listens on the first team's side, and hands its task to a person on the second team (or the owner); anyone else is refused.
- **Scenarios replace Play and the event slider** on this tab: a new WhatsApp lead, a client changes what they said, a meeting ends, a cash payment arrives, the owner asks for something, a screening finds a possible match. Each is the fullest of the latest five real runs in this office's log: the trigger, then every step it caused, who did it and who it went to. Back, Next and Play move through it, lighting each agent and its handoff on the map. A scenario that hasn't happened yet says so, and how to make it happen. A deal's story keeps its own replay.

- [x] Code tests: rooms and heads, a between-team agent and its refusals, an intern under the Scribe and its refusal, scenarios from real runs (and "not run yet").
- [x] Browser, 10 of 10: no slider on this tab, Front desk apart from Sales, heads first, six scenarios, steps lighting the map with handoff lines, a between-team agent on the arrow, an intern under the Scribe, the zoom in reporting order, no page errors.

## Proving every agent works, and a map you can arrange (3 Nov)

- **Self-check** (the last button in the scenario strip, owner only) runs a whole office day through the real code on a throwaway office, in its own process. Your office's data is never touched. The day covers:
  - a WhatsApp lead, a meeting where the client corrects himself, a cash payment, a screening match and a report draft;
  - the owner's instructions to Nova, numbers and documents, the deal converting, a late transfer step, a supplier invoice;
  - the brand, the Lobby's week, and a listing through the studio.
- **It reports every agent** as worked, needs something outside Diwan (and exactly what), or not reached, along with each scene's result. Every row on the map shows its mark (✓, "needs" or ✗).
- **Live run, 3 Nov:** all 12 scenes passed. 48 agents worked; 8 need Instagram, HeyGen or a filmed take. The Brand brain was the only one not reached, because its draft wrote nothing to the log; it now records it.
- **Nova's instructions now do the work** instead of leaving a task queued. Deck, screening, the cash report, payment tracking, the follow-up, invoices, transfer tracking and fact-checking are each connected to the agent's real function.
- **Drag a department by its title** to arrange the map. The lines follow, the layout is saved in this browser, and the last box moved sits on top. **Reset layout** puts everything back.

- [x] Code: the self-check runs every scene, and without a model it reaches every agent except the two that only act through one (Devil's advocate, Brand brain).
- [x] Browser: the self-check button shows the last result, rows carry their marks, the panel lists scenes and agents by state, and Run starts a new check.
- [x] Browser: dragging Compliance moves it 220×250 px; the lines follow, a drag doesn't open the department, it stays after a reload, and Reset puts it back.
