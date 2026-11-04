"""The public demo (DIWAN_TEAM_PASSWORD set) never lets a visitor change the keys or the logins, not even signed in as
the owner. Reset still works, and Settings still shows which keys are set."""
import pytest

from .test_access import signed_in, web  # noqa: F401  the same signed-in test client


@pytest.fixture
def demo(web, monkeypatch):
    monkeypatch.setenv("DIWAN_TEAM_PASSWORD", "the team's password")
    signed_in(web, "layla")
    return web


@pytest.mark.parametrize("path,body", [("/api/auth/password", {"person": "omar", "password": "a new password"}),
                                       ("/api/auth/password", {"person": "omar", "password": ""}),
                                       ("/api/integrations", {"values": {"ZOOM_CLIENT_SECRET": "x"}}),
                                       ("/api/integrations/aisensy/test", {})])
def test_the_owner_cannot_change_keys_or_logins_in_the_public_demo(demo, path, body):
    r = demo.post(path, json=body)
    assert r.status_code == 403 and "Locked in the public demo" in r.text


def test_reset_and_reading_which_keys_are_set_still_work(demo):
    assert demo.get("/api/integrations").status_code == 200
    assert demo.post("/api/demo/reset").status_code == 200


def test_without_the_team_password_the_owner_still_can(web, monkeypatch):
    monkeypatch.delenv("DIWAN_TEAM_PASSWORD", raising=False)
    signed_in(web, "layla")
    assert web.post("/api/auth/password", json={"person": "omar", "password": "another good one"}).status_code == 200
