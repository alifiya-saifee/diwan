"""What the PAs know about the app itself: true, never a key, and only what each person may see."""
import pytest

from diwan import app_guide


@pytest.fixture
def clean(monkeypatch):
    for k in ("WHATSAPP_PROVIDER", "WHATSAPP_TOKEN", "WHATSAPP_PHONE_ID", "AISENSY_PROJECT_ID", "AISENSY_PROJECT_API_PWD", "AISENSY_API_KEY",
              "IG_ACCESS_TOKEN", "IG_USER_ID", "ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET", "PERSONAL_WHATSAPP_TOKEN", "PERSONAL_WHATSAPP_PHONE_ID"):
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


def test_a_named_line_without_its_keys_is_not_connected(clean):
    clean.setenv("WHATSAPP_PROVIDER", "cloud")
    s = app_guide.status()
    assert not s["whatsapp"]["connected"] and s["whatsapp"]["named_not_ready"]
    said = app_guide.answer("Is the WhatsApp line connected?", "layla")
    assert "not connected" in said and "keys are missing" in said and "Settings, WhatsApp line" in said


def test_no_key_is_ever_said(clean):
    secret = "sk-very-secret-123456"
    clean.setenv("IG_ACCESS_TOKEN", secret)
    clean.setenv("IG_USER_ID", "1789")
    clean.setenv("ZOOM_CLIENT_SECRET", secret)
    text = "\n".join(app_guide.lines("layla")) + str(app_guide.status())
    assert secret not in text and "1789" not in text
    assert app_guide.answer("Is Instagram connected?", "layla") == "Instagram is set up."


def test_staff_hear_only_what_is_theirs(clean):
    clean.setenv("DIWAN_AUTH", "on")
    owner, broker = "\n".join(app_guide.lines("layla")), "\n".join(app_guide.lines("omar"))
    for private in ("AI spend this month", "personal WhatsApp", "Logins:"):
        assert private in owner and private not in broker
    owner_pages, broker_pages = "\n".join(app_guide.page_lines("layla")), "\n".join(app_guide.page_lines("omar"))
    assert "App page Settings" in owner_pages and "App page Settings" not in broker_pages  # a page they can't open isn't described to them
    assert "App page Sales" in broker_pages
    assert app_guide.answer("How much have we spent on AI?", "omar") is None
    assert app_guide.answer("Is my personal WhatsApp connected?", "omar") is None


def test_the_owner_hears_both_lines_for_my_whatsapp(clean):
    said = app_guide.answer("Is my WhatsApp connected?", "layla")
    assert "sales WhatsApp line" in said and "personal WhatsApp" in said


def test_where_things_are(clean):
    assert "+ Add a lead" in app_guide.answer("Where do I add a lead?", "layla")
    assert "Settings, Logins" in app_guide.answer("How do I give Omar a login?", "layla")
    assert "Settings, Video" in app_guide.answer("How do I connect Zoom?", "layla")
    assert app_guide.answer("What is the Studio page for?", "layla").startswith("Studio is marketing")
    assert app_guide.answer("How much have we spent on the AI this month?", "layla").startswith("AI spend this month")


def test_questions_about_clients_are_left_alone(clean):
    for q in ("where is Karim's deal", "what's the status of Karim", "how is the Marina deal going", "who is paying for 1204?",
              "What did we spend last month?", "how much did the office cost us in October?"):
        assert app_guide.answer(q, "layla") is None, q


def test_sign_in_on_is_not_the_same_as_having_a_login(clean):
    clean.setenv("DIWAN_AUTH", "on")
    s = app_guide.status()
    s["logins"] = {"layla": True, "omar": False}
    line = app_guide.facts(s)["logins"]
    assert "Layla can sign in" in line and "Omar have no password yet" in line
