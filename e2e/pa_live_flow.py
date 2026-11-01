"""Live mode: Nova stays on the line without a click, on every page. A stand-in microphone says the words, because a browser check has
no voice; a real microphone is tried by a person. Fresh offline server, DIWAN_AUTH=off:
python e2e/pa_live_flow.py http://127.0.0.1:8034 <out dir>"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8034"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "pa"
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []
FAKE = """
class FakeRec { constructor() { window.__rec = this; window.__starts = (window.__starts || 0) + 1; }
  start() { this.live = true; } abort() { this.live = false; } stop() { this.live = false; this.onend && this.onend(); } }
window.SpeechRecognition = FakeRec; window.webkitSpeechRecognition = FakeRec;
window.__say = (t) => { const r = [{ transcript: t }]; r.isFinal = true; window.__rec.onresult({ results: [r] }); };
"""


def check(n, name, ok, note=""):
    results.append((n, name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {n:>2} {name}{' · ' + str(note)[:140] if note else ''}")


with sync_playwright() as p:
    b = p.chromium.launch(channel=os.environ.get("E2E_CHANNEL", "chrome"))
    ctx = b.new_context(viewport={"width": 1500, "height": 900})
    ctx.add_init_script(FAKE)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))

    def state():
        return pg.locator(".live-pill").get_attribute("data-s")

    pg.goto(f"{BASE}/web/index.html")
    pg.wait_for_selector("#stats div")
    pg.wait_for_timeout(600)
    pg.screenshot(path=str(OUT / "1-start.png"))
    check(1, "The page fits the screen, with no page scroll", not pg.evaluate("document.documentElement.scrollHeight > innerHeight + 2"))
    pg.locator("#livebtn").first.click()
    pg.wait_for_timeout(300)
    check(2, "Go live: she is listening", state() == "listening")
    pg.evaluate("__say('Can you hear me?')")
    pg.wait_for_function("document.querySelector('#answer').innerText.includes('I can hear you')", timeout=30000)
    pg.wait_for_function("document.querySelector('.live-pill').dataset.s === 'listening'", timeout=30000)
    check(3, "She answers and listens again, with no click", pg.evaluate("window.__rec.live"))
    n = pg.evaluate("window.__starts")
    pg.evaluate("window.__rec.stop()")
    pg.wait_for_timeout(600)
    check(4, "When the browser ends the mic after a silence, she stays on", pg.evaluate("window.__starts") > n and state() == "listening")
    pg.goto(f"{BASE}/web/calendar.html")
    pg.wait_for_selector(".live-pill:not([hidden])", timeout=6000)
    check(5, "She stays on the line on another page", state() == "listening")
    pg.evaluate("__say('Who has not called Sara back?')")
    pg.wait_for_function("document.querySelector('.live-pill').dataset.s === 'listening'", timeout=30000)
    pg.wait_for_timeout(600)
    pg.goto(f"{BASE}/web/index.html")
    pg.wait_for_selector("#stats div")
    pg.wait_for_timeout(600)
    text = pg.locator("#answer").inner_text()
    check(6, "The same conversation is on every page", "I can hear you" in text and "Sara back" in text, text[-90:])
    pg.screenshot(path=str(OUT / "2-talking.png"))
    pg.evaluate("__say('stop listening')")
    pg.wait_for_timeout(500)
    check(7, "'Stop listening' ends the call", pg.locator(".live-pill").is_hidden() and pg.locator("#livebtn").inner_text() == "Go live")
    pg.locator("#say").fill("Remind me tomorrow at 10am to call Sara")
    pg.locator("#say").press("Enter")
    pg.wait_for_function("document.querySelector('#answer').innerText.includes('remind you')", timeout=30000)
    check(8, "Typing still works", True)
    b.close()

failed = [r for r in results if not r[2]]
print(f"\n{len(results) - len(failed)} of {len(results)} passed; page errors: {errors or 'none'}")
sys.exit(1 if failed or errors else 0)
