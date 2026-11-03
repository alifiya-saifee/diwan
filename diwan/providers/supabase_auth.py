"""Staff logins kept in Supabase Auth (SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY in .env). Supabase checks the
password; the app still decides who sees what (diwan/access.py) and keeps its own session cookie.

  POST   {url}/auth/v1/token?grant_type=password     anon key        email + password → the user, or a refusal
  GET    {url}/auth/v1/admin/users                   service key     every login
  POST   {url}/auth/v1/admin/users                   service key     a new login, confirmed, with app_metadata.person
  PUT    {url}/auth/v1/admin/users/{id}               service key     a new password or email
  DELETE {url}/auth/v1/admin/users/{id}               service key     someone who left

Which Diwan person a login is lives in app_metadata.person, which only the service key can write: a user can't make
themselves the owner. The service key stays on the server, is never sent to a page, and is never logged.
"""
from __future__ import annotations

import time

import httpx

from diwan.config import env

KEYS = ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY")
TRANSPORT = None  # tests put a stand-in here; never set in the app
CACHE_SECONDS = 30
_users: dict = {}


class SupabaseError(RuntimeError):
    pass


def missing() -> list[str]:
    return [k for k in KEYS if not env(k)]


def available() -> bool:
    return not missing()


def _client() -> httpx.Client:
    return httpx.Client(base_url=env("SUPABASE_URL").rstrip("/") + "/auth/v1", transport=TRANSPORT, timeout=20)


def _admin() -> dict:
    key = env("SUPABASE_SERVICE_KEY")
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def _why(r: httpx.Response) -> str:
    try:
        d = r.json()
    except ValueError:
        return f"Supabase answered {r.status_code}"
    return d.get("msg") or d.get("error_description") or d.get("message") or f"Supabase answered {r.status_code}"


def _forget() -> None:
    _users.clear()


def users() -> dict[str, dict]:
    """Every login that belongs to a Diwan person, by person. Kept for a few seconds: the login page asks often."""
    if _users.get("at", 0) > time.time() - CACHE_SECONDS:
        return _users["by"]
    found, page = {}, 1
    with _client() as c:
        while True:
            r = c.get("/admin/users", params={"page": page, "per_page": 200}, headers=_admin())
            if r.status_code != 200:
                raise SupabaseError(_why(r))
            batch = r.json().get("users", [])
            for u in batch:
                if person := (u.get("app_metadata") or {}).get("person"):
                    found[person] = {"id": u["id"], "email": u.get("email")}
            if len(batch) < 200:
                break
            page += 1
    _users.update(at=time.time(), by=found)
    return found


def sign_in(email: str, password: str) -> str | None:
    """The Diwan person whose email and password these are, or None. The person comes from Supabase's own record."""
    with _client() as c:
        r = c.post("/token", params={"grant_type": "password"}, json={"email": email, "password": password},
                   headers={"apikey": env("SUPABASE_ANON_KEY")})
    if r.status_code in (400, 401, 422):
        return None
    if r.status_code != 200:
        raise SupabaseError(_why(r))
    return ((r.json().get("user") or {}).get("app_metadata") or {}).get("person")


def save(person: str, password: str, email: str | None) -> None:
    """A login for this person: a new user, or a new password (and email) for theirs."""
    known = users().get(person)
    with _client() as c:
        if known:
            body = {"password": password} | ({"email": email, "email_confirm": True} if email and email != known["email"] else {})
            r = c.put(f"/admin/users/{known['id']}", json=body, headers=_admin())
        else:
            if not email:
                raise ValueError("Add their email first: it is what they sign in with")
            r = c.post("/admin/users", json={"email": email, "password": password, "email_confirm": True,
                                             "app_metadata": {"person": person}}, headers=_admin())
    _forget()
    if r.status_code not in (200, 201):
        raise ValueError(_why(r)) if r.status_code in (400, 422) else SupabaseError(_why(r))


def remove(person: str) -> None:
    known = users().get(person)
    if not known:
        return
    with _client() as c:
        r = c.delete(f"/admin/users/{known['id']}", headers=_admin())
    _forget()
    if r.status_code not in (200, 204, 404):
        raise SupabaseError(_why(r))
