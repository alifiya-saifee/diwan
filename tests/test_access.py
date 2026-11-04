"""The gate: nobody in without signing in, each person only their department, and everyone acts as themselves."""
import json
import pytest
from fastapi.testclient import TestClient

from diwan import access
from diwan.app import app


@pytest.fixture
def web(monkeypatch):
    monkeypatch.setenv("DIWAN_AUTH", "on")
    monkeypatch.setenv("DIWAN_DB", ":memory:")
    access._fails.clear()
    for who in ("layla", "omar", "maya", "priya", "ahmed"):
        access.set_password(who, "a good password")
    with TestClient(app, follow_redirects=False) as c:
        yield c


def signed_in(web, who):
    r = web.post("/api/auth/login", json={"person": who, "password": "a good password"})
    assert r.status_code == 200
    return r.json()


def test_nothing_without_signing_in(web):
    assert web.get("/api/chats").status_code == 401
    assert web.post("/api/chats/incoming", json={"phone": "1", "text": "x"}).status_code == 401
    r = web.get("/web/inbox.html")
    assert r.status_code == 303 and r.headers["location"].startswith("/web/login.html")
    assert web.get("/").status_code == 303


def test_a_socket_stays_shut_without_signing_in(web):
    with pytest.raises(Exception):
        with web.websocket_connect("/ws/events"):
            pass


def test_what_clients_and_other_companies_reach_stays_open(web):
    assert web.get("/web/login.html").status_code == 200
    assert web.get("/web/sign.html").status_code == 200
    assert web.get("/web/docs.html").status_code == 200
    assert web.get("/web/app.css").status_code == 200
    assert web.get("/api/whatsapp/webhook").status_code != 401
    assert web.get("/api/auth/me").json()["person"] is None


def test_a_wrong_password_gets_nothing_and_many_lock_it(web):
    for _ in range(access.TRIES):
        assert web.post("/api/auth/login", json={"person": "omar", "password": "wrong password"}).status_code == 401
    assert web.post("/api/auth/login", json={"person": "omar", "password": "a good password"}).status_code == 429
    assert web.get("/api/chats").status_code == 401


def test_someone_without_a_login_cannot_sign_in(web):
    assert web.post("/api/auth/login", json={"person": "nadia", "password": "a good password"}).status_code == 401


def test_sales_sees_sales_not_marketing_or_the_owners_pages(web):
    d = signed_in(web, "omar")
    assert d["home"] == "sales.html" and "studio.html" not in d["pages"]
    assert web.get("/api/chats").status_code == 200
    assert web.get("/api/studio").status_code == 403
    assert web.get("/api/marketing/chat").status_code in (403, 405)
    assert web.get("/web/studio.html").headers["location"] == "/web/sales.html"
    for page in ("office3d.html", "index.html", "settings.html", "graph.html", "team.html"):
        assert web.get(f"/web/{page}").status_code == 303


def test_marketing_sees_the_studio_not_the_inbox_or_deals(web):
    d = signed_in(web, "maya")
    assert d["home"] == "studio.html"
    assert web.get("/api/studio").status_code == 200
    assert web.get("/api/chats").status_code == 403
    assert web.get("/api/desk/overview").status_code == 403
    assert web.get("/web/inbox.html").status_code == 303


def test_compliance_and_finance_work_on_the_deal_desk_only(web):
    signed_in(web, "priya")
    assert web.get("/web/deal.html").status_code == 200
    assert web.get("/api/chats").status_code == 403
    assert web.get("/api/studio").status_code == 403


def test_a_new_route_nobody_listed_is_the_owners(web):
    assert not access.may_call("omar", "GET", "/api/something-new")
    assert access.may_call("layla", "GET", "/api/something-new")


def test_the_inbox_learns_the_line_without_seeing_any_address_or_token(web):
    signed_in(web, "omar")
    assert web.get("/api/integrations").status_code == 403
    line = web.get("/api/line").json()
    assert set(line) == {"provider", "aisensy", "cloud"} and set(line["cloud"]) == {"connected"}


def test_the_sales_manager_sees_every_brokers_calendar(web):
    access.set_password("rashid", "a good password")
    signed_in(web, "rashid")
    assert web.get("/api/calendar").status_code == 200


def test_the_owner_sees_everything(web):
    d = signed_in(web, "layla")
    assert d["owner"] and d["pages"] is None
    for path in ("/api/chats", "/api/studio", "/api/desk/overview", "/api/costs", "/api/graph"):
        assert web.get(path).status_code == 200, path


def test_only_the_owner_reads_the_logs_nova_and_settings(web):
    signed_in(web, "omar")
    for method, path in (("get", "/api/graph"), ("get", "/api/costs"), ("get", "/api/integrations"), ("post", "/api/nova/say"), ("post", "/api/demo/reset")):
        assert getattr(web, method)(path).status_code == 403, path


def test_a_screen_cannot_act_as_someone_else(web):
    signed_in(web, "omar")
    assert web.post("/api/rania/recommend", json={"by": "layla", "how_many": 2}).status_code == 403  # owner's; said to be layla, it is omar
    assert web.get("/api/notices/hamza").status_code == 403
    assert web.get("/api/notices/omar").status_code == 200


def test_the_event_stream_shows_only_the_department(web):
    signed_in(web, "maya")
    types = {e["type"] for e in web.get("/api/events").json()}
    assert not any(t.startswith(("chat.", "lead.", "fact.", "check.", "sale.")) for t in types)


def test_a_notice_for_someone_else_is_not_seen(web):
    token = access.USER.set("omar")
    try:
        shown = access.visible([{"type": "notify.sent", "actor": "rania", "content": {"to": "omar"}}, {"type": "notify.sent", "actor": "rania", "content": {"to": "hamza"}}])
    finally:
        access.USER.reset(token)
    assert [e["content"]["to"] for e in shown] == ["omar"]


def test_client_documents_are_for_the_deal_team(web):
    assert web.get("/media/doc-abc-passport.jpg").status_code == 401
    signed_in(web, "maya")
    assert web.get("/media/sig-abc.jpg").status_code == 403


def test_marketings_files_stay_public_for_instagram(web):
    assert web.get("/media/cut-MC-1204-F1.mp4").status_code != 401


def test_signing_out_ends_it_and_a_new_password_ends_every_session(web):
    signed_in(web, "omar")
    assert web.get("/api/chats").status_code == 200
    web.post("/api/auth/logout")
    assert web.get("/api/chats").status_code == 401
    signed_in(web, "omar")
    access.set_password("omar", "another password")
    assert web.get("/api/chats").status_code == 401


def test_only_the_owner_manages_logins(web):
    signed_in(web, "omar")
    assert web.get("/api/auth/people").status_code == 403
    assert web.post("/api/auth/password", json={"person": "hamza", "password": "a good password"}).status_code == 403
    web.post("/api/auth/logout")
    signed_in(web, "layla")
    assert web.post("/api/auth/password", json={"person": "hamza", "password": "short"}).status_code == 400
    assert web.post("/api/auth/password", json={"person": "hamza", "password": "a good password"}).json()["has_login"]
    assert web.post("/api/auth/password", json={"person": "omar", "password": ""}).json()["has_login"] is False
    assert not access.has_password("omar")
    assert web.post("/api/auth/password", json={"person": "layla", "password": ""}).status_code == 400


def test_the_first_password_is_from_this_machine_only(monkeypatch, tmp_path):
    monkeypatch.setenv("DIWAN_AUTH", "on")
    monkeypatch.setenv("DIWAN_DB", ":memory:")
    with TestClient(app, follow_redirects=False) as c:  # the test client is not 127.0.0.1, as a stranger on the internet is not
        assert c.get("/api/auth/me").json()["setup"] is True
        assert c.post("/api/auth/setup", json={"password": "a good password"}).status_code == 403
    assert not access.has_password("layla")


def test_passwords_are_never_kept_as_they_were_typed(web, tmp_path):
    data = (tmp_path / "auth.db").read_bytes()
    assert b"a good password" not in data


# the Deal desk as the people themselves

@pytest.fixture
def desk(web, monkeypatch):
    from diwan import app as appmod, demo
    from diwan.events import EventLog
    from diwan.office import Office
    o = Office(EventLog())
    demo.seed(o)
    monkeypatch.setattr(appmod.S, "office", o)
    for who in ("joseph", "rashid"):
        access.set_password(who, "a good password")
    return o


def hit_on(o, deal="marina-1204", note="UN entry 4411"):
    from diwan.agents import compliance
    t = next(t for t in o.graph().of("task", deal) if t.props["agent"] == "screen")
    compliance.record_screening(o, t.id, "priya", "possible match", note)
    return t


@pytest.mark.parametrize("who,room,ok", [("omar", "compliance", False), ("ahmed", "compliance", False), ("joseph", "compliance", False), ("priya", "compliance", True),
                                         ("omar", "finance", False), ("ahmed", "finance", True), ("priya", "finance", True), ("ahmed", "operations", False), ("joseph", "operations", True)])
def test_each_room_is_its_departments(web, desk, who, room, ok):
    signed_in(web, who)
    assert (web.get(f"/api/desk/rooms/{room}").status_code == 200) == ok


@pytest.mark.parametrize("who", ["omar", "ahmed", "joseph", "rashid"])
def test_outside_compliance_a_hold_is_a_status_and_nothing_behind_it(web, desk, who):
    t = hit_on(desk)
    signed_in(web, who)
    for path in ("/api/desk/deals/marina-1204", "/api/desk/deals", "/api/desk/overview", "/api/desk/board", "/api/desk/work", "/api/events?deal=marina-1204", "/api/events"):
        text = web.get(path).text
        assert "4411" not in text and "Possible match" not in text, path
    v = web.get("/api/desk/deals/marina-1204").json()
    assert v["compliance"]["blockers"] == [] and v["compliance"]["risk"] is None and not v["funds"]["numbers"] and t.id not in {x["id"] for x in v["tasks"]}
    assert web.get("/api/desk/deals?filter=match").json()["total"] == 0  # no filter can point at the deal
    assert web.get("/api/desk/overview").json()["comp"]["match"] == 0


def test_compliance_and_the_owner_still_read_all_of_it(web, desk):
    hit_on(desk)
    for who in ("priya", "layla"):
        signed_in(web, who)
        assert "4411" in web.get("/api/desk/deals/marina-1204").text
        assert web.get("/api/desk/deals?filter=match").json()["total"] == 1


def test_a_blocked_deals_refusal_doesnt_say_why(web, desk):
    from diwan.agents import compliance
    compliance.block(desk, "marina-1204", "priya", "Confirmed match on the UN list")
    assert "UN list" not in str(compliance.public_reason(compliance.state(desk.graph(), "marina-1204")))
    signed_in(web, "omar")
    assert "UN list" not in web.get("/api/desk/deals/marina-1204").text


def test_finance_doesnt_get_client_documents(web, desk):
    signed_in(web, "ahmed")
    assert web.get("/api/desk/deals/marina-1204").json()["documents"] == {"requests": [], "profile": {}}


def test_the_record_says_who_really_did_it_even_for_the_owner(web, desk):
    signed_in(web, "layla")
    assert web.post("/api/desk/deals/marina-1204/compliance/clear", json={"by": "priya", "note": "x"}).status_code == 403
    pay = next(t for t in desk.graph().of("task", "marina-1204") if t.props["agent"] == "pay")
    assert web.post(f"/api/desk/tasks/{pay.id}/received", json={"by": "ahmed", "reference": "X"}).status_code == 403
    r = web.post("/api/desk/roles", json={"by": "layla", "role": "finance", "person": "joseph"})  # naming a person stays hers
    assert r.status_code == 200 and next(x for x in r.json() if x["role"] == "finance")["holder"] == "joseph"


def test_form_f_is_prepared_by_the_deals_people_only(web, desk):
    for who in ("ahmed", "priya"):
        signed_in(web, who)
        assert web.post("/api/desk/deals/marina-1204/formf", json={"by": who}).status_code == 403


def test_funds_proof_files_are_compliances(web, desk):
    from diwan.providers import meta
    meta.MEDIA.mkdir(parents=True, exist_ok=True)
    (meta.MEDIA / "doc-proof-test.pdf").write_bytes(b"%PDF")
    try:
        signed_in(web, "omar")
        assert web.get("/media/doc-proof-test.pdf").status_code == 403
        signed_in(web, "priya")
        assert web.get("/media/doc-proof-test.pdf").status_code == 200
    finally:
        (meta.MEDIA / "doc-proof-test.pdf").unlink()


def test_more_than_expected_asks_first_and_saves_nothing(web, desk):
    from datetime import date
    from diwan.agents import finance
    pay = next(t for t in desk.graph().of("task", "marina-1204") if t.props["agent"] == "pay")
    want = finance.expected(desk.graph(), pay, date.today())["amount_aed"]
    with pytest.raises(finance.ProofMismatch, match="more than"):
        finance.mark_received(desk, pay.id, "ahmed", "X", today=date.today(), amount=want + 1000)
    assert not desk.graph().nodes[pay.id].props.get("payments")
    assert finance.mark_received(desk, pay.id, "ahmed", "X", today=date.today(), amount=want + 1000, confirm=True)


# logins kept in Supabase Auth (diwan/providers/supabase_auth.py), against a stand-in for its API

class FakeSupabase:
    """Supabase Auth's few endpoints the app uses, holding users in memory."""

    def __init__(self):
        self.users, self.down, self.n = {}, False, 0

    def __call__(self, req):
        import httpx
        if self.down:
            return httpx.Response(503, json={"msg": "down"})
        path, body = req.url.path, json.loads(req.content or b"{}")
        admin = req.headers.get("authorization") == "Bearer service-key"
        if path.endswith("/token"):
            u = next((u for u in self.users.values() if u["email"] == body.get("email")), None)
            if not u or u["password"] != body.get("password") or req.headers.get("apikey") != "anon-key":
                return httpx.Response(400, json={"error_description": "Invalid login credentials"})
            return httpx.Response(200, json={"access_token": "t", "user": {k: v for k, v in u.items() if k != "password"}})
        if not admin:
            return httpx.Response(401, json={"msg": "not admin"})
        if path.endswith("/admin/users") and req.method == "GET":
            return httpx.Response(200, json={"users": [{k: v for k, v in u.items() if k != "password"} for u in self.users.values()]})
        if path.endswith("/admin/users") and req.method == "POST":
            if any(u["email"] == body["email"] for u in self.users.values()):
                return httpx.Response(422, json={"msg": "A user with this email address has already been registered"})
            self.n += 1
            uid = f"u{self.n}"
            self.users[uid] = {"id": uid, "email": body["email"], "password": body["password"], "app_metadata": body.get("app_metadata", {})}
            return httpx.Response(200, json={"id": uid})
        uid = path.rsplit("/", 1)[-1]
        if uid not in self.users:
            return httpx.Response(404, json={"msg": "User not found"})
        if req.method == "PUT":
            self.users[uid].update({k: v for k, v in body.items() if k in ("email", "password")})
            return httpx.Response(200, json={"id": uid})
        del self.users[uid]
        return httpx.Response(200, json={})

    def add(self, email, password, person=None):
        self.n += 1
        self.users[f"u{self.n}"] = {"id": f"u{self.n}", "email": email, "password": password, "app_metadata": {"person": person} if person else {}}


@pytest.fixture
def supa(monkeypatch):
    import httpx
    from diwan.providers import supabase_auth
    fake = FakeSupabase()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-key")
    monkeypatch.setattr(supabase_auth, "TRANSPORT", httpx.MockTransport(fake))
    supabase_auth._users.clear()
    fake.add("layla@diwan.example", "the owner's password", "layla")
    monkeypatch.setenv("DIWAN_AUTH", "on")
    monkeypatch.setenv("DIWAN_DB", ":memory:")
    access._fails.clear()
    with TestClient(app, follow_redirects=False) as c:
        yield c, fake


def supa_in(c, who, password):
    return c.post("/api/auth/login", json={"person": who, "password": password})


def test_with_supabase_people_sign_in_by_email_and_still_see_only_their_department(supa):
    c, fake = supa
    assert c.get("/api/auth/me").json()["email"] is True
    assert supa_in(c, "layla@diwan.example", "the owner's password").json()["person"] == "layla"
    r = c.post("/api/auth/password", json={"person": "omar", "password": "omar's password", "email": "Omar@Diwan.example"})
    assert r.json()["has_login"]
    row = next(p for p in c.get("/api/auth/people").json() if p["id"] == "omar")
    assert row["has_login"] and row["email"] == "omar@diwan.example"
    c.post("/api/auth/logout")
    assert supa_in(c, "omar@diwan.example", "omar's password").json()["person"] == "omar"
    assert c.get("/api/chats").status_code == 200
    assert c.get("/web/studio.html").status_code in (302, 303)  # Marketing's, not his
    c.post("/api/auth/logout")
    assert supa_in(c, "omar", "omar's password").json()["person"] == "omar"  # the name still finds his email


def test_with_supabase_a_wrong_password_gets_nothing_and_many_lock_it(supa):
    c, fake = supa
    for _ in range(access.TRIES):
        assert supa_in(c, "layla@diwan.example", "wrong password").status_code == 401
    assert supa_in(c, "layla@diwan.example", "the owner's password").status_code == 429


def test_with_supabase_a_first_login_needs_an_email(supa):
    c, fake = supa
    supa_in(c, "layla@diwan.example", "the owner's password")
    r = c.post("/api/auth/password", json={"person": "hamza", "password": "a good password"})
    assert r.status_code == 400 and "email" in r.json()["detail"]
    assert c.post("/api/auth/password", json={"person": "hamza", "password": "short", "email": "h@diwan.example"}).status_code == 400


def test_a_supabase_user_who_isnt_one_of_ours_gets_nothing(supa):
    """Someone who signed themselves up, or set their own details, is not a Diwan person: Supabase's record says who."""
    c, fake = supa
    fake.add("stranger@example.com", "a good password")
    assert supa_in(c, "stranger@example.com", "a good password").status_code == 401
    fake.add("fake-owner@example.com", "a good password", "somebody")
    assert supa_in(c, "fake-owner@example.com", "a good password").status_code == 401


def test_with_supabase_removing_a_login_or_a_new_password_ends_them_at_once(supa):
    c, fake = supa
    supa_in(c, "layla@diwan.example", "the owner's password")
    c.post("/api/auth/password", json={"person": "omar", "password": "omar's password", "email": "omar@diwan.example"})
    c.post("/api/auth/logout")
    supa_in(c, "omar@diwan.example", "omar's password")
    assert c.get("/api/chats").status_code == 200
    access.set_password("omar", "a newer password")
    assert c.get("/api/chats").status_code == 401
    supa_in(c, "omar@diwan.example", "a newer password")
    access.remove_login("omar")
    assert c.get("/api/chats").status_code == 401
    assert supa_in(c, "omar@diwan.example", "a newer password").status_code == 401
    assert not any(u["email"] == "omar@diwan.example" for u in fake.users.values())


def test_with_supabase_no_password_is_kept_here(supa, tmp_path):
    c, fake = supa
    supa_in(c, "layla@diwan.example", "the owner's password")
    c.post("/api/auth/password", json={"person": "omar", "password": "omar's password", "email": "omar@diwan.example"})
    import sqlite3
    with sqlite3.connect(tmp_path / "auth.db") as db:
        assert db.execute("select count(*) from logins").fetchone()[0] == 0
    assert b"omar's password" not in (tmp_path / "auth.db").read_bytes()


def test_when_supabase_cant_be_reached_nobody_gets_in_and_it_says_so(supa):
    c, fake = supa
    fake.down = True
    r = supa_in(c, "layla@diwan.example", "the owner's password")
    assert r.status_code == 503 and "reached" in r.json()["detail"]
    assert c.get("/api/chats").status_code == 401


def test_marketing_reaches_every_route_the_studio_calls_and_a_broker_does_not(web):
    """The occasions on the Studio's plan belong to Marketing: Maya gets them, a broker doesn't."""
    signed_in(web, "maya")
    assert web.get("/api/occasions").status_code == 200
    import re
    from pathlib import Path
    page = (Path(__file__).parent.parent / "web/studio.html").read_text(encoding="utf-8")
    for p in sorted(set(re.findall(r'["`](/api/[A-Za-z0-9_/-]+)', page))):
        if not p.startswith(access.PUBLIC_API):
            assert access.may_call("maya", "GET", p) or access.may_call("maya", "POST", p), p
    signed_in(web, "omar")
    assert web.get("/api/occasions").status_code == 403



def test_marketing_sees_its_own_agents_at_work_and_no_one_elses():
    """Running now, on the Studio: the Marketing agents' steps reach Maya; Sales' and Compliance's never do."""
    from diwan.access import USER
    evs = [{"type": "agent.pack", "agent": a, "content": {"pack": {"verdict": a}}} for a in ("mscript", "mart", "mwriter", "mkt", "rania", "sof")]
    token = USER.set("maya")
    try:
        assert [e["agent"] for e in access.visible(evs)] == ["mscript", "mart", "mwriter", "mkt"]
    finally:
        USER.reset(token)
    token = USER.set("omar")
    try:
        assert not [e for e in access.visible(evs) if e["agent"] in ("mscript", "mart", "mwriter", "mkt")]
    finally:
        USER.reset(token)
