"""A public demo host with no lasting disk: the host's settings give the demo people their logins on each start."""
import importlib

import pytest

from diwan import access
from diwan.people import PEOPLE


@pytest.fixture
def start(tmp_path, monkeypatch):
    monkeypatch.setenv("DIWAN_DATA", str(tmp_path))
    monkeypatch.setenv("DIWAN_DB", str(tmp_path / "diwan.db"))
    monkeypatch.setattr(access, "supabase", lambda: False)
    import deploy.start
    return importlib.reload(deploy.start)


def test_the_owner_and_the_team_get_the_passwords_from_the_settings(start, monkeypatch):
    monkeypatch.setenv("DIWAN_OWNER_PASSWORD", "the owner's password")
    monkeypatch.setenv("DIWAN_TEAM_PASSWORD", "the team's password")
    assert set(start.logins()) == set(PEOPLE)
    assert access.check_password("layla", "the owner's password") and access.check_password("omar", "the team's password")
    access.set_password("omar", "omar changed it")
    assert start.logins() == []  # a login someone set is never overwritten
    assert access.check_password("omar", "omar changed it")


def test_no_team_password_no_team_logins(start, monkeypatch):
    monkeypatch.delenv("DIWAN_TEAM_PASSWORD", raising=False)
    monkeypatch.setenv("DIWAN_OWNER_PASSWORD", "the owner's password")
    assert start.logins() == ["layla"] and not access.has_password("omar")


def test_never_with_supabase_logins(start, monkeypatch):
    monkeypatch.setattr(access, "supabase", lambda: True)
    monkeypatch.setattr(access, "has_password", lambda p: True)
    monkeypatch.setenv("DIWAN_TEAM_PASSWORD", "the team's password")
    assert start.logins() == []


def test_the_start_says_whether_pictures_can_carry_arabic(start, monkeypatch):
    from diwan.agents import eventpost
    monkeypatch.setattr(eventpost, "ARABIC_FONTS", ("/nowhere/NoArabic.ttf",))
    assert start.arabic().startswith("Arabic on pictures: no, no Arabic font")
    monkeypatch.setattr(eventpost, "ARABIC_FONTS", (__file__,))  # any file that exists stands in for a font
    assert start.arabic().startswith("Arabic on pictures: yes") or "shaping" in start.arabic()
