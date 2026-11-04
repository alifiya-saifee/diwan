"""After the brief is approved, the scripts are written: the Studio shows that progress, not "nothing is waiting"."""
from diwan.agents import studio

from .test_eventpost import office  # noqa: F401  the same studio office


def _run_to_brief(o, ref="JOB-introduce"):
    studio._pack(o, "mkt", f"New informational video for Meet Diwan Realty ({ref}).", kind="assign")
    studio._pack(o, "mcopy", f"Approve the brief for {ref}: \"Meet Diwan Realty\"", kind="draft")
    return ref


def test_waiting_on_the_brief_is_ready_for_a_person(office):
    ref = _run_to_brief(office)
    assert studio.progress(office, ref)["state"] == "ready"


def test_writing_after_the_brief_shows_as_running(office, monkeypatch):
    ref = _run_to_brief(office)
    monkeypatch.setitem(studio.RUNNING, ref, "2026-11-04T20:00:00+00:00")
    office.log.append("agent.started", actor="mscript", agent="mscript", content={"task": f"Writing the who-we-help script for {ref} with the model"})
    p = studio.progress(office, ref)
    assert p["state"] == "running" and not p["steps"][-1]["done"] and "who-we-help" in p["now"]


def test_writing_that_died_after_the_brief_shows_as_stopped_not_ready(office):
    ref = _run_to_brief(office)
    office.log.append("agent.started", actor="mscript", agent="mscript", content={"task": f"Writing the say-hello script for {ref} with the model"})
    assert studio.progress(office, ref)["state"] == "stopped"  # the office restarted mid-way: Start again, never "nothing is waiting"


def test_the_pick_card_is_ready(office):
    ref = _run_to_brief(office)
    office.log.append("agent.started", actor="mscript", agent="mscript", content={"task": f"Writing the say-hello script for {ref} with the model"})
    studio._pack(office, "mcopy", f"Pick a script for {ref} (3 checked by the Copywriter)", kind="draft")
    assert studio.progress(office, ref)["state"] == "ready"
