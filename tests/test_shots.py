"""A script line becomes a shot before it becomes a picture: a named place is shown as that place."""
from diwan.agents import shots
from diwan.providers import meta


def test_a_named_place_is_recognised_with_what_it_looks_like():
    assert shots.look_of("From Marina and JVC to Business Bay")[0] == "Dubai Marina"  # the first one named, as people say it
    assert shots.look_of("a villa on the Palm Jumeirah")[0] == "Palm Jumeirah" and shots.look_of("life in Jumeirah Village Circle")[0] == "JVC"
    name, looks = shots.look_of("Sunset over Dubai Marina tonight")
    assert name == "Dubai Marina" and "canal" in looks
    assert shots.look_of("the view of the Burj Khalifa")[0] == "Downtown"
    assert shots.look_of("We help first-time buyers") == ("", "")


def test_the_photo_directors_shots_become_the_brief(monkeypatch):
    monkeypatch.setattr(meta, "look", lambda s, t, imgs, sc, **k: {"shots": [
        {"n": 0, "place": "Dubai Marina", "subject": "The Marina canal with yachts", "camera": "promenade, 24mm", "light": "blue hour"}]})
    plan = shots.plan(None, "Meet us", ["Living in Dubai Marina", "We help buyers"], "A Dubai brokerage.")
    assert plan[0]["subject"] == "The Marina canal with yachts" and "canal" in plan[0]["looks"]
    assert plan[1]["subject"].startswith("A real scene that shows: We help buyers")  # not planned: built from the line
    p = shots.prompt(plan[0], about="A Dubai brokerage.", title="Meet us", avoid="too dark")
    assert p.startswith("The Marina canal with yachts.")  # the subject first: image models weigh the first words most
    assert "Place: Dubai Marina" in p and "no invented landmarks" in p and "blue hour" in p and "turned down: too dark" in p
    assert "A Dubai brokerage" not in p and "Meet us" not in p  # the business and the headline invite signs and logos
    assert "Place:" not in shots.prompt(plan[1], about="", title="Meet us")


def test_when_the_photo_director_fails_every_line_still_gets_a_shot(monkeypatch):
    def fail(*a, **k):
        raise meta.MetaError("down")
    monkeypatch.setattr(meta, "look", fail)
    plan = shots.plan(None, "Meet us", ["Homes in JVC", "Call us"], "")
    assert [s["place"] for s in plan] == ["JVC", ""] and all(s["camera"] and s["light"] for s in plan)
