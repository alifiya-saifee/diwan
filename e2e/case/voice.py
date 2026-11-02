"""Does Nova really speak, from the very first reply? A spy on the browser's speech records every sentence: asked for, started, finished or failed.
A reply that was asked to be spoken and never started is a failure, whatever the screen shows.

    python e2e/case/voice.py http://127.0.0.1:8040 <out dir>
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from browser import Run  # noqa: E402

SPY = """(() => { window.__spoken = []; const s = window.speechSynthesis; if (!s) return; const real = s.speak.bind(s);
  s.speak = (u) => { const r = { text: u.text.slice(0, 60), voice: u.voice && u.voice.name, voices: s.getVoices().length, started: false, ended: false, error: null, at: performance.now() };
    window.__spoken.push(r); u.addEventListener('start', () => { r.started = true; r.after = Math.round(performance.now() - r.at); });
    u.addEventListener('end', () => { r.ended = true; }); u.addEventListener('error', (e) => { r.error = e.error; }); real(u); }; })();"""
# a stand-in microphone: it hears what the test says, in the pieces a real one breaks a sentence into
EARS = """(() => { class SR { start() { window.__ear = this; } abort() {} stop() {} } window.SpeechRecognition = SR; window.webkitSpeechRecognition = SR;
  window.__hear = (t) => { const r = [{ transcript: t }]; r.isFinal = true; window.__ear.onresult({ results: [r] }); }; })();"""
r = Run(sys.argv[1], sys.argv[2], "voice")
c = r.person("layla")[0]
r.person("layla")[1].on("console", lambda m: print("   console:", m.text[:160], flush=True) if m.type in ("error", "warning") else None)
c.grant_permissions(["microphone"], origin=sys.argv[1])
c.add_init_script(SPY)


def rows():
    return r.pg.evaluate("window.__spoken")


def reply(text, n):
    """Type to her on a live call and wait for her voice to be asked for."""
    before = len(rows())
    r.pg.locator("#say").fill(text)
    r.pg.locator("#say").press("Enter")
    end = time.time() + 75
    while time.time() < end and len([x for x in rows()[before:] if "moment" not in x["text"].lower()]) < 1:
        r.pg.wait_for_timeout(400)
    r.pg.wait_for_timeout(5000)
    got = [x for x in rows()[before:] if "moment" not in x["text"].lower()]
    print(json.dumps(got, ensure_ascii=False)[:400], flush=True)
    print("   live button:", r.pg.inner_text("#livebtn"), "| all speech:", [x["text"][:40] for x in rows()], "| screen:", r.pg.inner_text("#answer")[-160:].replace(chr(10), " / "), flush=True)
    r.check(f"reply {n}: her voice was asked for", got, got[:1])
    r.check(f"reply {n}: sound really started", got and any(x["started"] for x in got), got[:1])


def fresh_page(label):
    r.be("layla", "index.html")
    r.step(label)
    r.pg.wait_for_timeout(1000)
    if r.pg.inner_text("#livebtn") == "Go live":
        r.pg.locator("#livebtn").click()
    r.pg.wait_for_timeout(600)
    print("   after Go live:", r.pg.inner_text("#livebtn"), flush=True)


fresh_page("A fresh page: Go live, then the first question")
reply("Hello Nova, who are you?", 1)
reply("What time is it in Dubai?", 2)
reply("Thanks", 3)
fresh_page("Reloaded, a second first question")
reply("Say good morning to me", "1 after reload")
r.step("On the open mic: their sentence arrives in two pieces, and the second means nothing")
c.add_init_script(EARS)
r.be("layla", "index.html")
r.pg.wait_for_timeout(1000)
before = len(rows())
r.pg.evaluate("window.__hear('What time is it in Dubai right now')")
r.pg.wait_for_timeout(500)
r.pg.evaluate("window.__hear('the the')")
end = time.time() + 40
while time.time() < end and not any(re.search(r"\d", x["text"]) for x in rows()[before:]):
    r.pg.wait_for_timeout(500)
r.check("the answer is still spoken", any(re.search(r"\d", x["text"]) for x in rows()[before:]), [x["text"] for x in rows()[before:]])
r.step("Overheard talk gets no reply and no blank bubble")
n = r.pg.locator("#answer .answer").count()
r.pg.evaluate("window.__hear('So did you listen to them or did you open the door')")
r.pg.wait_for_timeout(9000)
r.check("no blank Nova bubble", not r.pg.evaluate("[...document.querySelectorAll('#answer .answer:not(.me)')].some((b) => b.innerText.trim() === 'Nova')"))
r.check("nothing added to the chat", r.pg.locator("#answer .answer").count() == n, r.pg.inner_text("#answer")[-120:])
print(r.finish())
