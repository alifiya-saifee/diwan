"""The broker confirms the viewing Rania held for them (the app's default, docs/agent-confirms-spec.md). With a page, as the
broker would: the Inbox banner's "Confirmed: book it". Returns what the client was sent."""


def confirm(api, base, phone, page=None):
    d = api.get(f"{base}/api/chats/{phone}").json()
    w, broker, before = d["owner_wait"], d["broker"], len(d["messages"])
    assert w and w.get("confirm") == "broker", f"nothing held for the broker: {w}"
    if page is not None:
        page.goto(f"{base}/web/inbox.html?chat={phone}&as={broker}")
        page.locator(".banner.owner button", has_text="Confirmed: book it").click()
        page.wait_for_timeout(900)
    else:
        r = api.post(f"{base}/api/appointments/{w['id']}/owner", data={"by": broker, "said": "yes"})
        assert r.ok, r.text()
    return next((m["text"] for m in api.get(f"{base}/api/chats/{phone}").json()["messages"][before:] if m["type"] == "sent"), "")
