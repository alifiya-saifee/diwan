"""Who may see what. One gate in front of the whole app (pages, API, sockets, files): nobody gets in without signing in, a
person sees only their department, and what they do is done as themselves, whatever a screen sends. The owner sees all.

Anything not listed here is the owner's: a new route is closed until someone decides who it is for. Passwords live in
their own small database next to the office's, never in the event log, as salted scrypt hashes. With Supabase set up
(SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY) the logins live in Supabase Auth instead and people sign in with
their email (diwan/providers/supabase_auth.py); sessions and everything below stay the same.

DIWAN_AUTH=off turns the gate off, for tests and the browser checks in e2e/, which have their own scratch office.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from contextvars import ContextVar
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from diwan import config
from diwan.config import env
from diwan.people import PEOPLE, name, pid
from diwan.providers import supabase_auth as sb

router = APIRouter()
USER: ContextVar[str | None] = ContextVar("diwan_user", default=None)  # who this request is, None for the owner's own checks
COOKIE = "diwan_session"
HOURS = 12
MIN_PASSWORD = 8
TRIES, LOCK_SECONDS = 5, 300

SALES, MKT, OPS, FIN, COMP = "sales", "mkt", "ops", "fin", "comp"
STAFF = {SALES, MKT, OPS, FIN, COMP}
DEAL_TEAM = {SALES, OPS, FIN, COMP}
HOME = {SALES: "sales.html", MKT: "studio.html", OPS: "deal.html", FIN: "deal.html", COMP: "deal.html"}
OWNER_HOME = "office3d.html"

# no sign-in: what clients and other companies reach, each protected by its own token or signature
PUBLIC_API = ("/api/auth/", "/api/sign/", "/api/docs/", "/api/whatsapp/webhook", "/api/personal/webhook", "/api/instagram/webhook", "/api/aisensy/webhook", "/api/portals/")
PUBLIC_PAGES = {"login.html", "sign.html", "docs.html"}
SENSITIVE_MEDIA = ("doc-", "sig-", "deal-")  # IDs, signatures and signed forms; the rest must be fetchable by Instagram and WhatsApp
FUNDS_PROOF = "/media/doc-proof-"  # source-of-funds proof: the compliance officer's and the owner's only

PAGES = {"lobby.html": STAFF, "sales.html": {SALES}, "inbox.html": {SALES}, "calendar.html": {SALES}, "qualify.html": {SALES}, "meeting.html": {SALES}, "deck.html": {SALES},
         "deal.html": DEAL_TEAM, "studio.html": {MKT}, "catalog.html": {SALES, MKT}, "knowledge.html": STAFF}

# (path prefix, who, method): the first that matches decides
API = [("/api/listings/sync", set(), None), ("/api/lobby-room", STAFF, "GET"), ("/api/lobby-room/propose", {SALES}, "POST"), ("/api/lobby-room/playbooks", {SALES}, "POST"),
       ("/api/pa/", STAFF, None), ("/api/health", STAFF, None), ("/api/people", STAFF, None), ("/api/roster", STAFF, None), ("/api/search", STAFF, None),
       ("/api/events", STAFF, None), ("/ws/events", STAFF, None), ("/ws/floor", STAFF, None), ("/api/floor", STAFF, "GET"), ("/api/team", STAFF, "GET"), ("/api/notices/", STAFF, None),
       ("/api/knowledge", STAFF, None), ("/api/items", STAFF, None), ("/api/catalog", STAFF, None), ("/api/proposals", STAFF, None),
       ("/api/listings", {SALES, MKT}, None), ("/api/line", {SALES}, "GET"), ("/api/sales/rules", set(), "POST"), ("/api/sales", {SALES}, None),
       *((p, {SALES}, None) for p in ("/api/chats", "/api/calendar", "/api/appointments", "/api/attention", "/api/leads", "/api/decks",
                                      "/api/meetings", "/api/qualify", "/api/rania", "/api/templates")),
       ("/api/deals", {SALES}, "GET"), ("/api/deal-kinds", {SALES}, "GET"),
       ("/api/desk/rooms/compliance", {COMP}, None), ("/api/desk/rooms/finance", {FIN, COMP}, None), ("/api/desk/rooms/operations", {OPS, COMP}, None),
       ("/api/desk/", DEAL_TEAM, None),
       *((p, {MKT}, None) for p in ("/api/studio", "/api/marketing", "/api/brand", "/api/products", "/api/topics", "/api/moments",
                                    "/api/requests", "/api/business", "/api/kpis/marketing", "/api/occasions"))]
COMP_AGENTS = ("comp", "screen", "sof", "report")
OWN_PATH = ("/api/notices/",)  # the next part of the path is the person: only their own

LOBBY_EVENTS = ("thread.", "playbook.", "experiment.")  # every room reads the Lobby (the spec's table); counts and reasons, no client data
DEAL_EVENTS = ("task.", "check.", "review.", "draft.", "question.", "decision.", "approval.", "sign.", "docs.", "document.", "sale.", "stage.",
               "fact.", "execution.", "deal.")
EVENTS = {SALES: LOBBY_EVENTS + DEAL_EVENTS + ("chat.", "lead.", "appointment.", "attention.", "followup.", "visit.", "qualify.", "calendar.", "listing", "meeting.",
                                "consent.", "utterance"),
          OPS: LOBBY_EVENTS + DEAL_EVENTS, FIN: LOBBY_EVENTS + DEAL_EVENTS + ("payment.", "invoice."),
          COMP: LOBBY_EVENTS + DEAL_EVENTS + ("payment.", "compliance.", "screening."),
          MKT: LOBBY_EVENTS + ("post.", "photo.", "campaign.", "lead.attributed", "product.", "mchat.", "photos.", "plan.", "competitor", "board.", "content.", "footage.", "step.", "qa.", "topic.", "listing")}


def enabled() -> bool:
    return env("DIWAN_AUTH", "on") != "off"


def department(person: str) -> str | None:
    p = PEOPLE.get(person)
    if not p or p["role"] == "Owner":
        return None
    return SALES if p["role"] == "Sales manager" else p.get("team")


def is_owner(person: str | None) -> bool:
    return bool(person) and PEOPLE.get(person, {}).get("role") == "Owner"


def sees_compliance() -> bool:
    """Whether the person asking may read Compliance's work, not only its status (the spec's table): tests and the owner do."""
    person = USER.get()
    return person is None or is_owner(person) or department(person) == COMP


def owner_id() -> str:
    return next(k for k, p in PEOPLE.items() if p["role"] == "Owner")


def may_open(person: str, page: str) -> bool:
    return is_owner(person) or department(person) in PAGES.get(page, ())


def may_call(person: str, method: str, path: str) -> bool:
    if is_owner(person):
        return True
    dept = department(person)
    for prefix, who, only in API:
        if path.startswith(prefix) and (only is None or only == method):
            if dept not in who:
                return False
            if prefix in OWN_PATH:
                return path[len(prefix):].split("/")[0] == person
            return True
    return False


def home(person: str) -> str:
    return OWNER_HOME if is_owner(person) else HOME.get(department(person), "knowledge.html")


def visible(events: list[dict]) -> list[dict]:
    """Of these events, what the person asking may see: their department's, and notices and requests that are theirs."""
    person = USER.get()
    if person is None or is_owner(person):
        return events
    dept = department(person)
    kinds = EVENTS.get(dept, ())
    out = []
    for e in events:
        t, c = e["type"], e.get("content") or {}
        if t.startswith(("notify.", "lobby.")):
            if person in (c.get("to"), c.get("by"), e.get("actor")):
                out.append(e)
        elif dept != COMP and (e.get("agent") in COMP_AGENTS or c.get("agent") in COMP_AGENTS):
            continue  # what Compliance is doing stays with Compliance: anyone else knowing can tip a client off
        elif t.startswith(kinds):
            out.append(e)
        elif dept == MKT and t.startswith("agent.") and _marketing_agent(e.get("agent")):
            out.append(e)  # the studio's own agents at work: what "Running now" shows
    return out


def _marketing_agent(aid: str | None) -> bool:
    """An agent in the Marketing lead's team, at any depth."""
    from diwan.agents import charters
    while aid and aid in charters.BY_ID:
        if aid == "mkt":
            return True
        aid = charters.BY_ID[aid].parent
    return False


# ---------- passwords and sessions ----------

def _db() -> sqlite3.Connection:
    office = env("DIWAN_DB")
    path = Path(office).with_name("auth.db") if office and office != ":memory:" else config.ROOT / "auth.db"
    c = sqlite3.connect(path)
    c.execute("create table if not exists logins (person text primary key, salt blob, hash blob, set_at real)")
    c.execute("create table if not exists sessions (token text primary key, person text, expires real)")
    return c


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1)


def supabase() -> bool:
    """Logins kept in Supabase Auth, when its three keys are set."""
    return sb.available()


def has_password(person: str) -> bool:
    if supabase():
        return person in sb.users()
    with _db() as c:
        return c.execute("select 1 from logins where person=?", (person,)).fetchone() is not None


def set_password(person: str, password: str, email: str | None = None) -> None:
    """A new password ends every session that person has. With Supabase, a first login needs the email they sign in with."""
    if person not in PEOPLE:
        raise ValueError("No such person")
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"A password needs at least {MIN_PASSWORD} characters")
    if supabase():
        sb.save(person, password, (email or "").strip().lower() or None)
        with _db() as c:
            c.execute("delete from sessions where person=?", (person,))
        return
    salt = secrets.token_bytes(16)
    with _db() as c:
        c.execute("insert or replace into logins values (?,?,?,?)", (person, salt, _hash(password, salt), time.time()))
        c.execute("delete from sessions where person=?", (person,))


def remove_login(person: str) -> None:
    if supabase():
        sb.remove(person)
    with _db() as c:
        c.execute("delete from logins where person=?", (person,))
        c.execute("delete from sessions where person=?", (person,))


def check_password(person: str, password: str) -> bool:
    with _db() as c:
        row = c.execute("select salt, hash from logins where person=?", (person,)).fetchone()
    salt, want = row if row else (b"\0" * 16, b"")
    return hmac.compare_digest(_hash(password, salt), want) and bool(row)  # the same work whether or not they exist


def who_signs_in(typed: str, password: str) -> str | None:
    """The person these details belong to. With Supabase it is Supabase's record that says who, never what was typed."""
    if not supabase():
        person = pid(typed) or typed.strip().lower()
        return person if check_password(person, password) else None
    email = typed.strip().lower() if "@" in typed else (sb.users().get(pid(typed) or "") or {}).get("email")
    person = sb.sign_in(email, password) if email else None
    return person if person in PEOPLE else None


def _key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()  # a stolen database holds no working sessions


def open_session(person: str) -> str:
    token = secrets.token_urlsafe(32)
    with _db() as c:
        c.execute("delete from sessions where expires<?", (time.time(),))
        c.execute("insert into sessions values (?,?,?)", (_key(token), person, time.time() + HOURS * 3600))
    return token


def session_person(token: str | None) -> str | None:
    if not token:
        return None
    with _db() as c:
        row = c.execute("select person from sessions where token=? and expires>?", (_key(token), time.time())).fetchone()
    return row[0] if row else None


def close_session(token: str | None) -> None:
    if token:
        with _db() as c:
            c.execute("delete from sessions where token=?", (_key(token),))


_fails: dict[str, tuple[int, float]] = {}


def _cookie(res: JSONResponse, request: Request, token: str) -> None:
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    res.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=secure, max_age=HOURS * 3600, path="/")


def describe(person: str | None) -> dict:
    if not person:
        return {"person": None}
    return {"person": person, "name": name(person), "role": PEOPLE[person]["role"], "department": department(person), "owner": is_owner(person),
            "home": home(person), "pages": None if is_owner(person) else sorted(p for p in PAGES if may_open(person, p))}


class LoginIn(BaseModel):
    person: str  # a name, or with Supabase the email
    password: str


class SetupIn(BaseModel):
    password: str
    email: str = ""


class PasswordIn(BaseModel):
    person: str
    password: str = ""
    email: str = ""


def _unreachable() -> HTTPException:
    return HTTPException(503, "The sign-in service can't be reached. Try again in a minute.")


@router.get("/api/auth/me")
def me(request: Request):
    if not enabled():
        return {"auth": False, "setup": False, **describe(owner_id())}
    try:
        setup = not has_password(owner_id())
    except sb.SupabaseError:
        setup = False
    return {"auth": True, "setup": setup, "email": supabase(), **describe(session_person(request.cookies.get(COOKIE)))}


@router.post("/api/auth/setup")
def setup(body: SetupIn, request: Request):
    """The owner's first password. Only on this machine: a public server is never open to whoever arrives first."""
    owner = owner_id()
    local = request.client and request.client.host in ("127.0.0.1", "::1") and not request.headers.get("x-forwarded-for")
    try:
        done = has_password(owner)
    except sb.SupabaseError:
        raise _unreachable() from None
    if done or not local:
        raise HTTPException(403, "The owner's password is set from this machine, once")
    try:
        set_password(owner, body.password, body.email)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    except sb.SupabaseError:
        raise _unreachable() from None
    res = JSONResponse(describe(owner))
    _cookie(res, request, open_session(owner))
    return res


@router.post("/api/auth/login")
def login(body: LoginIn, request: Request):
    tried = pid(body.person) or body.person.strip().lower()
    n, until = _fails.get(tried, (0, 0.0))
    if n >= TRIES and time.time() < until:
        raise HTTPException(429, "Too many tries. Wait a few minutes.")
    try:
        person = who_signs_in(body.person, body.password)
    except sb.SupabaseError:
        raise _unreachable() from None
    if not person:
        _fails[tried] = (n + 1 if time.time() >= until or n < TRIES else n, time.time() + LOCK_SECONDS)
        raise HTTPException(401, "That email and password don't match" if supabase() else "That name and password don't match")
    _fails.pop(tried, None)
    res = JSONResponse(describe(person))
    _cookie(res, request, open_session(person))
    return res


@router.post("/api/auth/logout")
def logout(request: Request):
    close_session(request.cookies.get(COOKIE))
    res = JSONResponse({"ok": True})
    res.delete_cookie(COOKIE, path="/")
    return res


def _owner_only(request: Request) -> None:
    if enabled() and not is_owner(session_person(request.cookies.get(COOKIE))):
        raise HTTPException(403, "Only the owner manages logins")


@router.get("/api/auth/people")
def people(request: Request):
    _owner_only(request)
    try:
        held = sb.users() if supabase() else None
    except sb.SupabaseError:
        raise _unreachable() from None
    return [{"id": k, "name": p["name"], "role": p["role"], "department": department(k),
             "has_login": k in held if held is not None else has_password(k), "email": (held or {}).get(k, {}).get("email")}
            for k, p in PEOPLE.items()]


@router.post("/api/auth/password")
def password(body: PasswordIn, request: Request):
    """The owner sets anyone's password, or removes a login (an empty password): someone who left stops at once."""
    _owner_only(request)
    who = pid(body.person)
    if not who:
        raise HTTPException(404, "No such person")
    if not body.password:
        if is_owner(who):
            raise HTTPException(400, "The owner's login stays")
        try:
            remove_login(who)
        except sb.SupabaseError:
            raise _unreachable() from None
        return {"ok": True, "has_login": False}
    try:
        set_password(who, body.password, body.email)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    except sb.SupabaseError:
        raise _unreachable() from None
    return {"ok": True, "has_login": True}


# ---------- the gate ----------

def _public(path: str, method: str) -> bool:
    if path.startswith(PUBLIC_API) or path == "/favicon.ico":
        return True
    if path.startswith("/web/"):
        return not path.endswith(".html") or path.rsplit("/", 1)[-1] in PUBLIC_PAGES
    if path.startswith("/media/"):
        return method == "GET" and not path.rsplit("/", 1)[-1].startswith(SENSITIVE_MEDIA)
    return False


def _form_as(body: bytes, boundary: bytes, person: str) -> bytes:
    """A multipart upload: its `by` field says this person, whatever it said."""
    field = re.compile(rb'(name="by"\r\n\r\n)[^\r]*')
    if field.search(body):
        return field.sub(lambda m: m.group(1) + person.encode(), body, count=1)
    return b"--" + boundary + b'\r\nContent-Disposition: form-data; name="by"\r\n\r\n' + person.encode() + b"\r\n" + body


chat_guard = None  # set by the app: may this person open this conversation? (a broker: their own leads and the Pool)
deal_guard = None  # set by the app: may this person open this deal? (a broker: their own)
file_guard = None  # set by the app: may this person open this client's ID, signature or signed form?


# A public demo (DIWAN_TEAM_PASSWORD set: every visitor shares the demo logins) never lets anyone change the keys or the
# logins from the page: a visitor signed in as the owner could otherwise lock others out or replace the keys.
LOCKED_IN_DEMO = ("/api/auth/password", "/api/integrations")


def demo_locked(path: str, method: str) -> bool:
    return method in ("POST", "PUT", "PATCH", "DELETE") and path.startswith(LOCKED_IN_DEMO) and bool(config.env("DIWAN_TEAM_PASSWORD"))


class Gate:
    """In front of everything, so a route, a page or a socket added later is behind it from the start."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket") or not enabled():
            return await self.app(scope, receive, send)
        path, method = scope["path"], scope.get("method", "GET")
        if demo_locked(path, method):
            return await self._refuse(scope, receive, send, 403, "Locked in the public demo", None)
        if _public(path, method):
            return await self.app(scope, receive, send)
        headers = {k.decode("latin1").lower(): v for k, v in scope["headers"]}
        jar = SimpleCookie()
        jar.load(headers.get("cookie", b"").decode("latin1"))
        person = session_person(jar[COOKIE].value if COOKIE in jar else None)
        page = None if path != "/" and not path.endswith(".html") else (OWNER_HOME if path == "/" else path.rsplit("/", 1)[-1])
        if person is None:
            return await self._refuse(scope, receive, send, 401, "Please sign in", page and f"/web/login.html?next=/web/{page}")
        allowed = (may_open(person, page) if page else
                   is_owner(person) or department(person) == COMP if path.startswith(FUNDS_PROOF) else
                   department(person) in DEAL_TEAM or is_owner(person) if path.startswith("/media/") else may_call(person, method, path))
        if not allowed:
            return await self._refuse(scope, receive, send, 403, "That belongs to another department", page and f"/web/{home(person)}")
        if (m := re.match(r"/api/chats/([^/]+)", path)) and chat_guard and not chat_guard(person, m.group(1)):
            return await self._refuse(scope, receive, send, 403, "That lead belongs to another broker", None)
        if (m := re.match(r"/api/desk/deals/([^/]+)", path)) and deal_guard and not deal_guard(person, m.group(1)):
            return await self._refuse(scope, receive, send, 403, "That deal belongs to another broker", None)
        if path.startswith("/media/") and path.rsplit("/", 1)[-1].startswith(SENSITIVE_MEDIA) and file_guard and not file_guard(person, path.rsplit("/", 1)[-1]):
            return await self._refuse(scope, receive, send, 403, "That document belongs to another broker's client", None)
        token = USER.set(person)
        try:
            if is_owner(person):
                if path.startswith("/api/desk/") and method in ("POST", "PUT", "PATCH", "DELETE"):  # the record says who really did it, the owner too
                    scope, receive = await self._body_as(scope, receive, headers, person, keep_person=True)
                return await self.app(scope, receive, send)
            q = [(k, v) for k, v in parse_qsl(scope.get("query_string", b"").decode("latin1"), keep_blank_values=True) if k not in ("by", "person", "as")]
            scope = dict(scope, query_string=urlencode(q + [("by", person), ("person", person), ("as", person)]).encode())  # never someone else
            if scope["type"] == "http" and method in ("POST", "PUT", "PATCH", "DELETE"):
                scope, receive = await self._body_as(scope, receive, headers, person)
            await self.app(scope, receive, send)
        finally:
            USER.reset(token)

    async def _body_as(self, scope, receive, headers, person, keep_person=False):
        kind = headers.get("content-type", b"").decode("latin1")
        chunks, more = [], True
        while more:
            m = await receive()
            if m["type"] != "http.request":
                break
            chunks.append(m.get("body", b""))
            more = m.get("more_body", False)
        body = b"".join(chunks)
        if "multipart/form-data" in kind and (b := re.search(r"boundary=([^;]+)", kind)):
            body = _form_as(body, b.group(1).strip('"').encode(), person)
        elif "json" in kind or not kind:
            try:
                data = json.loads(body or b"{}")
            except ValueError:
                data = None
            if isinstance(data, dict):
                data["by"] = person
                if "person" in data and not keep_person:  # the owner names a person when assigning a role
                    data["person"] = person
                body = json.dumps(data).encode()
        new = [(k, v) for k, v in scope["headers"] if k.lower() != b"content-length"] + [(b"content-length", str(len(body)).encode())]
        sent = False

        async def again():
            nonlocal sent
            if sent:
                return await receive()
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        return dict(scope, headers=new), again

    async def _refuse(self, scope, receive, send, code: int, why: str, to: str | None):
        if scope["type"] == "websocket":
            await receive()
            return await send({"type": "websocket.close", "code": 1008})
        if to:
            return await send_all(send, 303, b"", [(b"location", to.encode())])
        return await send_all(send, code, json.dumps({"detail": why}).encode(), [(b"content-type", b"application/json")])


async def send_all(send, status: int, body: bytes, headers: list) -> None:
    await send({"type": "http.response.start", "status": status, "headers": headers + [(b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})
