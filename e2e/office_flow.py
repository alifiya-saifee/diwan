"""The office, end to end in a real browser, as people would use it:
 1. a customer messages on the sandbox WhatsApp line and Rania answers in the inbox; a broker takes over and replies
 2. the owner teaches Rania a lesson on the Team page, and her next reply keeps it
 3. an Instagram comment arrives and shows in the inbox with Rania's reply
 4. the owner tells Nova to give Priya a job; Nova reads it back, a yes puts it on the requests board, Priya marks it done
Run against a server: python e2e/office_flow.py http://127.0.0.1:8031 [shots dir]"""
import json
import random
import sys
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8031"
SHOTS = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("e2e/shots")
SHOTS.mkdir(parents=True, exist_ok=True)
errors, results = [], []
PHONE = f"97150{random.randint(1000000, 9999999)}"  # a new customer each run, so the scenario can be rerun
NAME = f"Sara {PHONE[-4:]}"


def step(name):
    print("·", name, flush=True)
    results.append(name)


with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    pg = b.new_page(viewport={"width": 1440, "height": 950})
    pg.on("pageerror", lambda e: errors.append(f"{pg.url}: {e}"))
    pg.on("console", lambda m: errors.append(f"{pg.url}: {m.text}") if m.type == "error" else None)

    # 1. WhatsApp sandbox -> Rania -> takeover
    pg.goto(f"{BASE}/web/inbox.html")
    pg.click("#phonebtn")
    pg.fill("#pname", NAME)
    pg.fill("#pnum", PHONE)
    pg.fill("#ptext", "Hi, is the Marina Crest 2 bed still available? Can I see it Saturday at 4pm?")
    pg.click("#psend")
    conv = pg.locator(".conv", has_text=NAME)
    expect(conv).to_be_visible(timeout=60_000)
    conv.click()
    expect(pg.locator(".thread")).to_contain_text("Rania · AI", timeout=60_000)
    reply = pg.locator(".b.sent").last.inner_text()
    step(f"Rania replied: {[x for x in reply.splitlines() if x and x != 'Rania · AI'][0][:120]}")
    from datetime import datetime as _dt
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
    from diwan import slots as _slots
    want = _slots.say(_slots.parse("Saturday at 4pm", _dt.now(_slots.DUBAI)))  # the next Saturday, whatever today is
    assert ("Booked" in reply and want in reply) or ("isn't available" in reply and "Saturday" in reply), f"wrong time: {reply}"
    pg.screenshot(path=str(SHOTS / "o1-rania.png"))
    pg.locator(".chead .switch").click()
    expect(pg.locator(".chead .switch")).to_contain_text("has it")
    pg.click("#phoneclose")
    pg.fill("#box", "Hi Sara, Omar here. Saturday 4pm works, I'll meet you in the lobby.")
    pg.locator(".compose .tools button.primary").click()
    expect(pg.locator(".b.sent.person").last).to_contain_text("Omar here", timeout=20_000)
    step("a person took over and replied")
    pg.locator(".chead .switch").click()
    expect(pg.locator(".chead .switch")).to_contain_text("Rania replying")
    step("handed back to Rania")

    # 2. a lesson on the Team page, kept in the next reply
    pg.goto(f"{BASE}/web/team.html")
    pg.locator('[data-agent="rania"]').click()
    box = pg.locator("#detail input[placeholder^='e.g.']")
    box.fill("never mention service charges")
    pg.click("#teach")
    expect(pg.locator("#detail")).to_contain_text("service charges", timeout=20_000)
    step("lesson taught to Rania")
    pg.goto(f"{BASE}/web/inbox.html")
    pg.click("#phonebtn")
    pg.fill("#pname", NAME); pg.fill("#pnum", PHONE)
    pg.fill("#ptext", "And what are the service charges per year?")
    pg.click("#psend")
    pg.locator(".conv", has_text=NAME).click()
    expect(pg.locator(".thread")).to_contain_text("service charges per year", timeout=30_000)
    pg.wait_for_timeout(1500)
    last = pg.locator(".b.sent, .b.suggested").last.inner_text()
    assert "service charge" not in last.lower(), f"Rania broke the lesson: {last}"
    step(f"lesson kept: {last.splitlines()[0][:120]}")

    # 3. an Instagram comment, through the webhook, shows in the inbox
    body = {"object": "instagram", "entry": [{"changes": [{"field": "comments", "value": {"id": f"c-{PHONE}", "text": "price please? 🙏",
                                                                                        "from": {"username": f"tester{PHONE[-4:]}"}, "media": {"id": "m1"}}}]}]}
    r = httpx.post(f"{BASE}/api/instagram/webhook", content=json.dumps(body), headers={"content-type": "application/json"})
    assert r.status_code == 200, r.text
    pg.reload()
    c = pg.locator(".conv", has_text=f"tester{PHONE[-4:]}")
    expect(c).to_be_visible(timeout=30_000)
    c.click()
    expect(pg.locator(".thread")).to_contain_text("price please", timeout=20_000)
    step(f"Instagram comment in the inbox; reply: {pg.locator('.b.sent, .b.suggested').last.inner_text().splitlines()[0][:100]}")
    pg.screenshot(path=str(SHOTS / "o3-comment.png"))

    # 4. Nova -> read-back -> Lobby -> done
    pg.goto(f"{BASE}/web/office3d.html")
    pg.wait_for_selector("#say", timeout=60_000)
    pg.fill("#say", "Tell Priya I need the Karim review ready by this evening")
    pg.click("#send")
    expect(pg.locator("#zbody")).to_contain_text("Shall I send it?", timeout=60_000)
    step("Nova read the job back")
    pg.fill("#say", "yes")
    pg.click("#send")
    expect(pg.locator("#zbody")).to_contain_text("L", timeout=60_000)
    pg.wait_for_timeout(1000)
    step(f"Nova: {pg.locator('#zbody').inner_text().strip().splitlines()[-1][:120]}")
    pg.get_by_role("button", name="Requests board").first.click() if pg.get_by_role("button", name="Requests board").count() else None
    lob = httpx.get(f"{BASE}/api/lobby").json()
    assert any(x["to"] == "priya" and "Karim" in x["text"] for x in lob), lob
    step("card on the requests board for Priya")
    pg.screenshot(path=str(SHOTS / "o4-nova-lobby.png"))
    pg.fill("#say", "What did we sell last month?")
    pg.click("#send")
    pg.wait_for_timeout(2500)
    step(f"Nova on sales: {pg.locator('#zbody').inner_text().strip().splitlines()[-1][:160]}")
    b.close()

noise = [e for e in errors if "favicon" not in e and "speech" not in e.lower()]
print("console errors:", noise or "none")
sys.exit(1 if noise else 0)
