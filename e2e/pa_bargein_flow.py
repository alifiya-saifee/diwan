"""Cutting in on Nova: the mic stays open while she talks, her own voice is not taken for the person's, and a person who talks over her
stops her. A stand-in microphone and voice, because a browser check has neither. Fresh offline server, DIWAN_AUTH=off:
python e2e/pa_bargein_flow.py http://127.0.0.1:8034"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8034"
errors, results = [], []
FAKE = """
class FakeRec { constructor() { window.__rec = this; } start() { this.live = true; } abort() { this.live = false; } stop() { this.live = false; } }
window.SpeechRecognition = FakeRec; window.webkitSpeechRecognition = FakeRec;
window.__heard = (t, final = true) => { const r = [{ transcript: t }]; r.isFinal = final; window.__rec.onresult({ results: [r] }); };
window.__spoke = []; window.__cut = 0; window.__u = null;
speechSynthesis.speak = (u) => { window.__spoke.push(u.text); window.__u = u; };  // keeps talking until cancelled
speechSynthesis.cancel = () => { if (window.__u) { window.__cut++; const u = window.__u; window.__u = null; u.onend && u.onend(); } };
window.__finish = () => { const u = window.__u; window.__u = null; u && u.onend && u.onend(); };
"""


def check(n, name, ok, note=""):
    results.append((n, name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {n:>2} {name}{' · ' + str(note)[:140] if note else ''}")


with sync_playwright() as p:
    b = p.chromium.launch(channel=os.environ.get("E2E_CHANNEL", "chrome"))
    pg = b.new_context(viewport={"width": 1500, "height": 900}).new_page()
    pg.add_init_script(FAKE)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{BASE}/web/index.html")
    pg.wait_for_selector("#stats div")
    pg.evaluate("localStorage.clear()")
    pg.locator("#livebtn").first.click()
    pg.wait_for_timeout(300)

    def state():
        return pg.locator(".live-pill").get_attribute("data-s")

    pg.evaluate("__heard('Can you hear me?')")
    pg.wait_for_function("window.__spoke.length === 1", timeout=30000)
    check(1, "She is talking and the mic stays open", state() == "speaking" and pg.evaluate("window.__rec.live"))
    said = pg.evaluate("window.__spoke[0]")
    pg.evaluate("t => __heard(t)", said)
    pg.wait_for_timeout(500)
    check(2, "Her own voice through the speakers changes nothing", pg.evaluate("window.__cut") == 0 and state() == "speaking", said)
    pg.evaluate("__heard('wait a', false)")
    check(3, "Two words over her and she stops at once", pg.evaluate("window.__cut") == 1)
    pg.evaluate("__heard('Who has not called Sara back?')")
    pg.wait_for_function("document.querySelector('#answer').innerText.includes('Sara back')", timeout=30000)
    pg.wait_for_function("window.__spoke.length === 2", timeout=30000)
    check(4, "What was said over her is answered", True)
    pg.evaluate("__heard('stop')")
    pg.wait_for_timeout(500)
    check(5, "A single 'stop' just stops her", pg.evaluate("window.__spoke.length") == 2 and state() == "listening", state())
    pg.evaluate("window.__heard('What needs me today?'); window.__heard('Who has not called Dana back?')")
    pg.wait_for_function("document.querySelector('.live-pill').dataset.s === 'speaking'", timeout=30000)
    pg.wait_for_timeout(1200)
    last = pg.evaluate("window.__spoke[window.__spoke.length - 1]")
    check(6, "Cut off while thinking: she speaks only the newer answer", "Dana" in last, last)
    pg.evaluate("__finish()")
    pg.wait_for_timeout(300)
    check(7, "Back to listening", state() == "listening")
    b.close()

failed = [r for r in results if not r[2]]
print(f"\n{len(results) - len(failed)} of {len(results)} passed; page errors: {errors or 'none'}")
sys.exit(1 if failed or errors else 0)
