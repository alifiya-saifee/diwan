"""The live 3D office (Part 7), checked in a browser: real events become cards, the correction ripple plays with the Deal
desk's own numbers, robots take their poses, monitors show real output, and rooms show their own numbers.
Run on a fresh scratch server with DIWAN_AUTH=off, never diwan.db:
python e2e/live_floor_flow.py http://127.0.0.1:8064 <out dir>"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8064"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "live_floor"
OUT.mkdir(parents=True, exist_ok=True)
errors, fails = [], []


def check(name, ok, note=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}{' · ' + str(note)[:200] if note else ''}", flush=True)
    if not ok:
        fails.append(name)


with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", args=["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.on("pageerror", lambda e: errors.append(str(e)[:300]))
    pg.on("console", lambda m: errors.append(m.text[:300]) if m.type == "error" and "favicon" not in m.text else None)
    pg.goto(f"{BASE}/web/office3d.html?as=layla")
    pg.wait_for_function("window.__diwan && window.__diwan.live", timeout=30000)
    pg.wait_for_timeout(3500)
    stats = lambda: pg.evaluate("() => { const s = window.__diwan.live.stats; return { messages: s.messages, cards: s.cards, refused: s.refused.length, ripples: s.ripples.length, maxRedraw: s.maxRedraw, states: s.states.slice(-30) } }")
    pg.screenshot(path=str(OUT / "1-hq-idle.png"))
    check("idle: every card came from a real message", stats()["cards"] <= stats()["messages"] * 2, stats())

    # a real client message: a card comes in by the door
    pg.request.post(f"{BASE}/api/chats/incoming", data={"phone": "971501112233", "text": "Hi, is the Marina flat still free?", "name": "Sana Test"})
    pg.wait_for_timeout(900)
    pg.screenshot(path=str(OUT / "2-card.png"))
    pg.wait_for_timeout(1500)
    s = stats()
    check("a real message becomes cards", s["messages"] > 0 and s["cards"] > 0, s)

    # the correction, from the demo button
    pg.get_by_role("button", name="Karim corrects himself").click()
    pg.wait_for_function("window.__diwan.live.stats.ripples.length > 0", timeout=20000)
    for t, name in ((900, "3-quote"), (1000, "4-compliance"), (1100, "5-threads"), (1100, "6-untouched")):
        pg.wait_for_timeout(t)
        pg.screenshot(path=str(OUT / f"{name}.png"))
    pg.wait_for_selector("#floorripple", timeout=8000)
    pg.screenshot(path=str(OUT / "7-counter.png"))
    shown = dict((label, value) for value, label in json.loads(pg.get_attribute("#floorripple", "data-counts")))
    desk = pg.request.get(f"{BASE}/api/desk/overview").json()["corrections"][0]
    check("the counter is the Deal desk's", shown["tasks withdrawn"] == desk["withdrawn"] and shown["drafts sent back"] == desk["sent_back"] and shown["approvals back to the approver"] == desk["approvals"]
          and shown["forms recalled"] == desk["recalled"] and shown["rooms alerted"] == len(desk["rooms"]), {"shown": shown, "desk": desk})
    check("compliance heard first", desk["compliance_first"])
    check("nothing else was touched", shown["other work touched"] == 0)

    # poses and monitors
    robot = pg.evaluate("() => { const r = window.__diwan.hqBots.comp; return { state: r.state, hands: r.fx?.hands.length, lean: r.fx?.lean, chip: r.fx?.chipKey } }")
    check("robots have hands and a state", robot["hands"] == 2, robot)
    check("poses change on real work", any(x in stats()["states"] for x in ("comparing", "checking", "typing", "working", "handing")), stats()["states"])
    pg.click("#floorripple button")
    pg.evaluate("() => window.__diwan.enter('comp')")
    pg.wait_for_function("window.__diwan.floor?.dept === 'comp'", timeout=8000)
    pg.wait_for_timeout(2800)
    pg.screenshot(path=str(OUT / "8-compliance-room.png"))
    pg.evaluate("() => window.__diwan.goStop(1)")
    pg.wait_for_timeout(1600)
    pg.screenshot(path=str(OUT / "8b-compliance-lead.png"))
    hud = pg.inner_text("#hud")
    pg.evaluate("() => window.__diwan.leave()")
    pg.wait_for_timeout(1800)
    whole = pg.inner_text("#hud")
    pg.evaluate("() => window.__diwan.enter('fin')")
    pg.wait_for_function("window.__diwan.floor?.dept === 'fin'", timeout=8000)
    pg.wait_for_timeout(2800)
    pg.screenshot(path=str(OUT / "9-finance-room.png"))
    fin = pg.inner_text("#hud")
    check("each room shows its own numbers", hud != fin or hud != whole, {"comp": hud, "fin": fin, "hq": whole})
    check("at most 8 screens a frame", stats()["maxRedraw"] <= 8, stats()["maxRedraw"])
    pg.evaluate("() => window.__diwan.leave()")
    pg.wait_for_timeout(1500)
    frames = pg.evaluate("""() => new Promise((ok) => { const t = []; let last = performance.now(), n = 0;
      const f = (now) => { t.push(now - last); last = now; ++n < 90 ? requestAnimationFrame(f) : ok(t.sort((a, b) => a - b)[45]); }; requestAnimationFrame(f); })""")
    print(f"INFO median frame {frames:.1f} ms; renderer: {pg.evaluate('() => { const g = document.createElement(`canvas`).getContext(`webgl`), d = g.getExtension(`WEBGL_debug_renderer_info`); return d ? g.getParameter(d.UNMASKED_RENDERER_WEBGL) : `?` }')}", flush=True)
    check("no message was refused", stats()["refused"] == 0, stats()["refused"])
    check("no page errors", not errors, errors[:5])
    b.close()

print(f"{'ALL PASSED' if not fails else 'FAILED: ' + ', '.join(fails)}")
sys.exit(1 if fails else 0)
