"""Every page, as each person who uses it: is every option it needs there, and does every button do something? A button that changes nothing on the page and asks nothing of
the server is dead. Links are followed. Anything that spends model money or can't be undone is listed as not pressed, never counted as a pass.

    python e2e/case/pages.py http://127.0.0.1:8040 <out dir> [phone of a live client]
"""
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from browser import Run, Stop  # noqa: E402

BASE, OUT = sys.argv[1], sys.argv[2]
PHONE = sys.argv[3] if len(sys.argv) > 3 else "971507771001"
r = Run(BASE, OUT, "pages", slow=60)
NOT_PRESSED = re.compile(r"reset|sign out|delete|remove|end call|go live|publish|run the|^run\b|generate|make |write |refresh|render|film|forget|wipe|approve|launch|create link|upload|import|^start$|sync|^stop$|^call$|retire|stop this", re.I)

# who uses what, and the options that page must offer them
PAGES = {
    "layla": {"office3d.html": [], "index.html": ["Go live", "Send|Ask", "Notebook|notebook", "Urgent", "Decisions"], "personal.html": ["All", "Needs you", "Owed a reply", "Stand-in phone"],
              "sales.html": ["Add a lead"], "inbox.html": ["Needs you", "Mine", "Pool", "Sandbox phone", "Calendar"], "calendar.html": ["Add|appointment", "Busy", "Day off", "Today"],
              "qualify.html": ["Buyer", "Tenant", "Seller", "Landlord"], "meeting.html": ["Start"], "deal.html": ["Stage|stage|Deals|deal"], "lobby.html": [], "knowledge.html": [],
              "graph.html": [], "team.html": ["Rania", "Nova"], "settings.html": ["WhatsApp", "Instagram", "portal", "Team|team", "Logins|logins", "Models|models", "Sales"], "catalog.html": [], "studio.html": ["Run", "Plan", "Competitors", "Results", "Setup"], "test.html": []},
    "omar": {"sales.html": ["Add a lead"], "inbox.html": ["Mine", "Pool", "Calendar"], "calendar.html": ["Add|appointment", "Busy", "Day off"], "meeting.html": ["Start"], "deal.html": [], "qualify.html": [], "catalog.html": [], "lobby.html": [], "knowledge.html": []},
    "joseph": {"deal.html": [], "lobby.html": [], "knowledge.html": []},
    "ahmed": {"deal.html": [], "lobby.html": []},
    "priya": {"deal.html": [], "lobby.html": []},
    "maya": {"studio.html": ["Run", "Plan", "Competitors", "Results", "Setup"], "catalog.html": [], "lobby.html": [], "knowledge.html": []},
}
CLIENT = {"inbox.html": f"inbox.html?chat={PHONE}", "deal.html": None}
IN_CHAT = ["Convert", "Transfer", "Merge", "Follow up on", "Open the deal", "Record a meeting", "Stage", "Hot", "no calls", "template|📋"]
report = []
SEE = """() => { const seen = new Set(), out = [];
  const all = [...document.querySelectorAll('button, [role=tab]')];
  all.forEach((b, i) => { const t = (b.innerText || b.getAttribute('aria-label') || b.title || '').trim().replace(/\\s+/g, ' ').slice(0, 50);
    if (b.disabled || b.matches(':disabled') || !b.offsetParent || !t || seen.has(t)) return;
    b.scrollIntoView({ block: 'center' }); const q = b.getBoundingClientRect(); const top = document.elementFromPoint(q.x + q.width / 2, q.y + q.height / 2);
    if (!top || !(b === top || b.contains(top) || top.contains(b))) return;  // behind a drawer or a dialog: no person can press it now
    seen.add(t); out.push({ t, i, tab: b.getAttribute('role') === 'tab' || !!b.closest('.tabs, nav, .seg, [role=tablist]'), on: b.classList.contains('on') || b.classList.contains('active') || b.getAttribute('aria-selected') === 'true' }); });
  return out; }"""
STATE = """() => { const s = document.body.innerHTML + [...document.querySelectorAll('input, textarea, select')].map((e) => e.value + e.checked).join('|') + location.href + (window.__printed || 0) + (document.activeElement && document.activeElement.id);
  let h = 0; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0; return h; }"""
slow = {}


def state():
    return r.pg.evaluate(STATE)


def find(label):
    hit = next((x for x in r.pg.evaluate(SEE) if x["t"] == label), None)
    return r.pg.locator("button, [role=tab]").nth(hit["i"]) if hit else None


def load(url):
    t = time.time()
    r.pg.goto(url)
    r.pg.wait_for_timeout(700)
    slow[url] = max(slow.get(url, 0), round(time.time() - t - .7, 1))


def press(who, target, label, first=None):
    load(f"{BASE}/web/{target}")
    hits = []
    on = lambda q: hits.append(q.url) if "/api/" in q.url else None  # noqa: E731
    r.pg.on("request", on)
    try:
        if first:
            find(first).click(timeout=2500)
            r.pg.wait_for_timeout(450)
        b = find(label)
        if b is None:
            return "gone"
        hits.clear()
        before = state()
        r.pg.wait_for_timeout(250)
        live = state() != before  # the page changes by itself, so a change proves nothing
        before = state()
        b.click(timeout=2500)
        r.pg.wait_for_timeout(450)
        if hits or (state() != before and not live) or r.pg.locator("dialog[open], .toast").count():
            return "worked"
        box = r.pg.locator("textarea:visible, input[type=text]:visible, input:not([type]):visible")
        if box.count() and not box.first.input_value():  # a Send with nothing typed rightly does nothing: give it words
            box.first.fill("A line from the check")
            b = find(label)
            if b is not None and b.is_enabled():
                b.click(timeout=2500)
                r.pg.wait_for_timeout(450)
                if hits or r.pg.locator("dialog[open], .toast").count():
                    return "worked"
        return "unclear" if live else "dead"
    except Exception as e:  # noqa: BLE001
        return f"stuck: {str(e).splitlines()[0][:80]}"
    finally:
        r.pg.remove_listener("request", on)
        for extra in r.pg.context.pages:
            if extra != r.pg:
                extra.close()


def chats():
    return len(r.owner.get(f"{BASE}/api/chats").json().get("rows", []))


seen_chats = [0]


def walk_options(who, page, target, labels, row, tried, first=None):
    for x in labels:
        label = x["t"]
        if label in tried:
            continue
        tried.add(label)
        if NOT_PRESSED.search(label):
            row["not_pressed"].append(label)
            continue
        if x["on"] and not first:
            row["current"].append(label)  # already selected: pressing it again rightly changes nothing
        got = "worked" if x["on"] and not first else press(who, target, label, first)
        now_chats = chats()
        if now_chats != seen_chats[0]:
            r.check(f"the office's conversations survive \"{label}\" on {page}", now_chats >= seen_chats[0], f"{seen_chats[0]} before, {now_chats} after")
            seen_chats[0] = now_chats
        if got == "worked":
            row["worked"].append(label)
        elif got == "dead":
            row["dead"].append(label)
            r.check(f"{page}: \"{label}\" does something, as {who}" + (f" (in {first})" if first else ""), False, "nothing changed and nothing was asked of the server")
        elif got == "unclear":
            row["unclear"].append(label)
        elif got.startswith("stuck"):
            row["stuck"].append(f"{label}: {got}")
            r.check(f"{page}: \"{label}\" can be pressed, as {who}" + (f" (in {first})" if first else ""), False, got)
        if x["tab"] and got == "worked" and not first:  # the buttons a tab opens
            try:
                load(f"{BASE}/web/{target}")
                find(label).click(timeout=2500)
                r.pg.wait_for_timeout(600)
                walk_options(who, page, target, [y for y in r.pg.evaluate(SEE) if y["t"] not in tried][:30], row, tried, label)
            except Exception as e:  # noqa: BLE001
                row["stuck"].append(f"inside {label}: {str(e).splitlines()[0][:80]}")


def walk(who, page, needs, open_deal=False):
    target = CLIENT.get(page) or page
    if page == "deal.html" and open_deal:
        rows = r.api(who).get(f"{BASE}/api/desk/deals").json()
        rows = rows.get("rows") if isinstance(rows, dict) else rows
        target = f"deal.html?deal={rows[0]['deal']}" if rows else page
    r.be(who, target)
    r.step(f"{who}: {page}", 300)
    r.pg.wait_for_timeout(600)
    text = r.pg.evaluate("document.body.innerText + ' ' + [...document.querySelectorAll('[aria-label],[title],[placeholder]')].map((e) => e.getAttribute('aria-label') + ' ' + e.title + ' ' + (e.placeholder || '')).join(' ')")
    for need in needs + (IN_CHAT if page == "inbox.html" and who in ("layla", "omar") else []):
        r.check(f"{page} has \"{need}\" for {who}", re.search(need, text, re.I), "")
    labels = r.pg.evaluate(SEE)
    links = r.pg.evaluate("[...new Set([...document.querySelectorAll('a[href]')].map((a) => a.href))].filter((h) => h.includes('/web/') || h.includes('/api/') || h.includes('/media/'))")
    row = {"who": who, "page": page, "target": target, "options": len(labels), "worked": [], "current": [], "dead": [], "stuck": [], "unclear": [], "not_pressed": []}
    for l in links[:40]:
        got = r.api(who).get(l)
        if got.status >= 400 and got.status != 403:
            r.check(f"link works on {page}: {l[-60:]}", False, got.status)
    walk_options(who, page, target, labels, row, set())
    r.guard()
    report.append(row)
    r.check(f"{who} on {page}: {len(row['worked'])} options worked", not row["dead"] and not row["stuck"], f"{len(row['unclear'])} unclear: {row['unclear'][:5]}; {len(row['not_pressed'])} not pressed: {row['not_pressed'][:8]}")
    (Path(OUT) / "pages" / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf8")


def phone_size():
    r.be("omar")
    r.pg.set_viewport_size({"width": 390, "height": 844})
    for page in ("sales.html", f"inbox.html?chat={PHONE}", "calendar.html", "meeting.html", "lobby.html"):
        r.pg.goto(f"{BASE}/web/{page}")
        r.pg.wait_for_timeout(700)
        wide = r.pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        r.step(f"{page} at phone size", 200)
        r.check(f"{page} fits a phone", not wide)
    r.pg.set_viewport_size({"width": 1440, "height": 860})


try:
    r.be("layla", "index.html")
    for said, name, text in (("971501112233", "Mum", "Habibti did you eat? Call me tonight"), ("971504445566", "Ahmed Client", "Can we meet tomorrow about the villa?")):
        r.owner.post(f"{BASE}/api/personal/incoming", data={"phone": said, "name": name, "text": text})
    seen_chats[0] = chats()
    only = [x for x in os.environ.get("PAGES_ONLY", "").split(",") if x]
    for who, pages in PAGES.items():
        for page, needs in pages.items():
            if only and page not in only:
                continue
            r.part(f"{who} {page}", lambda w=who, p=page, n=needs: walk(w, p, n))
            if page == "deal.html":
                r.part(f"{who} a deal open", lambda w=who, n=needs: walk(w, "deal.html", n, True))
    r.part("phone size", phone_size)
except Stop as e:
    print("STOPPED:", e, flush=True)
worst = sorted(slow.items(), key=lambda x: -x[1])[:6]
print("SLOWEST LOADS", worst, flush=True)
r.check("every page opens within 5 seconds", not worst or worst[0][1] < 5, worst[:2])
good, bad, errors = r.finish()
print(f"RESULT {good} passed, {bad} failed")
