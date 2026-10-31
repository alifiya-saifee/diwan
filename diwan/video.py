"""Links for online appointments (docs/calendar-basics-spec.md). The owner picks the service (Zoom, Google Meet, or
none) and whether the link is made when Rania confirms a call (`setting.changed` person "sales", key "video"; off by
default). A link is only ever one the service made: when it can't be made, nothing is invented, the reason is kept,
and the broker gets a card to send one.

Event `appointment.link` {id, provider, url, meeting_id} or {id, provider, error}; `appointment.link_removed` {id}.
"""
from __future__ import annotations

from datetime import datetime

from diwan.graph import Graph
from diwan.office import Office
from diwan.providers import zoom

VIDEO = {"provider": None, "auto": False}
PROVIDERS = {"zoom": "Zoom", "google_meet": "Google Meet"}


def settings(g: Graph) -> dict:
    return VIDEO | (g.settings.get("sales", {}).get("video") or {})


def status() -> dict:
    """What each service needs, for the owner's settings (never the keys themselves)."""
    return {"zoom": {"ready": zoom.available(), "missing": zoom.missing()},
            "google_meet": {"ready": False, "missing": ["the Google connection (not built yet)"]}}


def set_settings(office: Office, value: dict, *, by: str) -> dict:
    from diwan import qualify
    if by not in qualify.owner_ids():
        raise PermissionError("Only the owner changes the video links")
    v = settings(office.graph()) | {k: value[k] for k in VIDEO if k in value}
    if v["provider"] not in (None, *PROVIDERS):
        raise ValueError("Pick Zoom, Google Meet or none")
    v["auto"] = bool(v["auto"]) and v["provider"] is not None
    office.log.append("setting.changed", actor=by, content={"person": "sales", "key": "video", "value": v})
    return v


def ready(g: Graph) -> bool:
    p = settings(g)["provider"]
    return bool(p) and status()[p]["ready"]


def make(office: Office, vid: str, *, by: str, cause: int | None = None) -> str | None:
    """Make the link for this appointment with the owner's service. Returns the link, or None (the reason is logged)."""
    from diwan import leads
    from diwan.people import name
    g = office.graph()
    v = g.nodes[vid]
    p = v.props
    prov = settings(g)["provider"]
    if (p.get("link") or {}).get("url"):
        return p["link"]["url"]
    try:
        if not prov:
            raise RuntimeError("no video service is picked in the calendar settings")
        if not status()[prov]["ready"]:
            raise RuntimeError(f"{PROVIDERS[prov]} is not connected: {', '.join(status()[prov]['missing'])}")
        m = zoom.create(f"{p.get('kind_name') or 'Video call'} with {p.get('customer')} ({name(p['broker'])})",
                        datetime.fromisoformat(p["at"]), int(p.get("minutes") or 30))
    except Exception as e:  # noqa: BLE001  the broker sends one instead, and the reason is kept
        ev = office.log.append("appointment.link", actor=by, deal=v.deal, caused_by=cause, content={"id": vid, "provider": prov, "error": str(e)[:300]})
        if p.get("chat") and f"chat:{p['chat']}" in g.nodes:
            leads.raise_card(office, p["chat"], reason=f"Send the video link for {p.get('kind_name') or 'the video call'}, "
                                                          f"{datetime.fromisoformat(p['at']).astimezone(leads.DUBAI):%a %d %b %H:%M} (it couldn't be made: {str(e)[:120]})",
                             to=p["broker"], kind="reply", cause=ev["id"])
        return None
    office.log.append("appointment.link", actor=by, deal=v.deal, caused_by=cause,
                      content={"id": vid, "provider": prov, "url": m["url"], "meeting_id": m["id"]})
    return m["url"]


def moved(office: Office, vid: str, *, by: str, cause: int | None = None) -> None:
    """The appointment has a new time: the meeting moves with it (its link stays the same)."""
    v = office.graph().nodes[vid]
    link = v.props.get("link") or {}
    if link.get("provider") == "zoom" and link.get("meeting_id"):
        try:
            zoom.move(link["meeting_id"], datetime.fromisoformat(v.props["at"]), int(v.props.get("minutes") or 30))
        except Exception as e:  # noqa: BLE001
            office.log.append("appointment.link", actor=by, deal=v.deal, caused_by=cause,
                              content={"id": vid, "provider": "zoom", "url": link.get("url"), "meeting_id": link["meeting_id"],
                                       "error": f"the new time didn't reach Zoom: {str(e)[:200]}"})


def cancelled(office: Office, vid: str, *, by: str, cause: int | None = None) -> None:
    v = office.graph().nodes[vid]
    link = v.props.get("link") or {}
    if link.get("provider") == "zoom" and link.get("meeting_id"):
        try:
            zoom.delete(link["meeting_id"])
            office.log.append("appointment.link_removed", actor=by, deal=v.deal, caused_by=cause, content={"id": vid})
        except Exception as e:  # noqa: BLE001
            office.log.append("appointment.link", actor=by, deal=v.deal, caused_by=cause,
                              content={"id": vid, "provider": "zoom", "url": link.get("url"), "meeting_id": link["meeting_id"],
                                       "error": f"the meeting couldn't be deleted in Zoom: {str(e)[:200]}"})
