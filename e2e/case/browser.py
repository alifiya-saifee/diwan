"""The window you watch. A real Edge, slowed down, a caption on every step, each person signed in as themselves in a browser of their own, video
and screenshots kept. Every check is written to results.jsonl as it happens, so a stopped run keeps what it found."""
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

PASSWORD = "a good password"
SPEND_LIMIT = 14.0  # of the 15 for this part of the office: the real Nova keeps the rest
CAPTION = """([t, c]) => { let b = document.getElementById('__case'); if (!b) { b = document.createElement('div'); b.id = '__case';
  b.style.cssText = 'position:fixed;left:50%;transform:translateX(-50%);top:8px;z-index:2147483647;font:600 15px system-ui;padding:9px 18px;border-radius:12px;box-shadow:0 4px 18px rgba(0,0,0,.5);max-width:86vw;pointer-events:none';
  document.documentElement.append(b); } b.style.background = c; b.style.color = '#14110a'; b.textContent = t; }"""


class Stop(Exception):
    """The budget line was reached: what was found so far is kept."""


class Run:
    def __init__(self, base, out, name, slow=350):
        self.base, self.name = base, name
        self.out = Path(out) / name
        (self.out / "shots").mkdir(parents=True, exist_ok=True)
        self.results = open(self.out / "results.jsonl", "a", encoding="utf8")
        self.pw = sync_playwright().start()
        self.b = self.pw.chromium.launch(channel="msedge", headless=False, slow_mo=slow, args=["--window-position=0,0", "--window-size=1500,950"] + [a for a in os.environ.get("CASE_ARGS", "").split("|") if a])
        self.people, self.errors, self.good, self.bad = {}, [], 0, 0
        self.pg, self.step_text, self.n, self.skip_ms = None, "", 0, 0
        self.answers = []
        self.owner = self.person("layla")[0].request

    def person(self, who):
        if who not in self.people:
            c = self.b.new_context(viewport={"width": 1440, "height": 860}, record_video_dir=str(self.out / "video" / who))
            r = c.request.post(f"{self.base}/api/auth/login", data={"person": who, "password": PASSWORD})
            assert r.ok, r.text()
            self._browser_clock(c)
            c.add_init_script("window.print = () => { window.__printed = (window.__printed || 0) + 1; };")  # the real dialog freezes the window
            pg = c.new_page()
            pg.set_default_timeout(15000)
            pg.set_default_navigation_timeout(45000)
            pg.on("pageerror", lambda e, w=who: self._bad(f"page error for {w}: {e}"))
            pg.on("response", lambda r, w=who: self._bad(f"{w}: {r.status} {r.url}") if r.status >= 500 else None)
            pg.on("dialog", self._dialog)
            self.people[who] = (c, pg)
        return self.people[who]

    def _browser_clock(self, c):
        """Pages read their own clock too: it moves with the office's."""
        if self.skip_ms:
            c.add_init_script("(() => { const R = window.__real = window.__real || Date; const o = %d; "
                              "class D extends R { constructor(...a) { a.length ? super(...a) : super(R.now() + o); } static now() { return R.now() + o; } } window.Date = D; })();" % self.skip_ms)

    def _moved(self, now):
        self.skip_ms = int((datetime.fromisoformat(now) - datetime.now(timezone.utc)).total_seconds() * 1000)
        for c, _ in self.people.values():
            self._browser_clock(c)

    def _dialog(self, d):
        if d.type == "prompt":
            d.accept(self.answers.pop(0) if self.answers else "A reason")
        elif self.answers:
            d.accept() if self.answers.pop(0) else d.dismiss()
        else:
            d.accept()

    def _bad(self, text):
        self.errors.append(text)
        print("  !!", text[:200], flush=True)

    def be(self, who, page=None):
        self.pg = self.person(who)[1]
        self.pg.bring_to_front()
        if page:
            self.pg.goto(f"{self.base}/web/{page}")
            self.pg.wait_for_timeout(900)
        self.caption(self.step_text)
        return self.pg

    def caption(self, text, color="#e8c77a"):
        try:
            self.pg.evaluate(CAPTION, [text, color])
        except Exception:  # noqa: BLE001  mid-navigation
            pass

    def step(self, text, pause=1200):
        self.step_text = text
        print(f"\n--- {text}", flush=True)
        self.caption(text)
        self.pg.wait_for_timeout(pause)
        self.guard()

    def guard(self):
        s = self.owner.get(f"{self.base}/api/case/spend").json()
        if s["rest"] >= SPEND_LIMIT:
            raise Stop(f"USD {s['rest']:.2f} spent of {s['cap']}: stopping here")

    def check(self, what, ok, note=""):
        ok = bool(ok)
        self.n += 1
        self.good += ok
        self.bad += not ok
        shot = f"{self.n:03d}.png"
        try:
            self.caption(f"{'PASS' if ok else 'FAIL'}: {what}", "#8fdca8" if ok else "#f27d7d")
            self.pg.wait_for_timeout(700 if ok else 1800)
            self.pg.screenshot(path=str(self.out / "shots" / shot))
        except Exception:  # noqa: BLE001
            shot = ""
        print(f"{'PASS' if ok else 'FAIL'} {self.n} {what}" + (f" · {str(note)[:240]}" if note else ""), flush=True)
        self.results.write(json.dumps({"n": self.n, "step": self.step_text, "what": what, "ok": ok, "note": str(note)[:600], "shot": shot, "at": time.strftime("%H:%M:%S")}, ensure_ascii=False) + "\n")
        self.results.flush()
        return ok

    def part(self, name, fn):
        """One part breaking is reported and the run goes on, so one fault doesn't hide the rest."""
        try:
            fn()
        except Stop:
            raise
        except Exception as e:  # noqa: BLE001
            self.check(f"stopped partway: {name}", False, str(e).split("\n")[0])

    # ---------- what people do ----------

    def api(self, who="layla"):
        return self.person(who)[0].request

    def chat(self, phone):
        r = self.owner.get(f"{self.base}/api/chats/{phone}")
        return r.json() if r.ok else None

    def client_says(self, phone, name, text, wait_reply=True, secs=60):
        """A client writes: on the sandbox phone, on the Inbox page. Returns what the office answered."""
        before = len((self.chat(phone) or {"messages": []})["messages"])
        self.be("layla")
        if "inbox.html" not in self.pg.url:
            self.pg.goto(f"{self.base}/web/inbox.html")
            self.pg.wait_for_timeout(800)
        if self.pg.locator("#phone").is_hidden():
            self.pg.click("#phonebtn")
        self.caption(f"{name} writes: {text[:90]}", "#9cc2ff")
        self.pg.fill("#pname", name)
        self.pg.fill("#pnum", phone)
        self.pg.fill("#ptext", text)
        self.pg.click("#psend")
        if not wait_reply:
            return None
        end = time.time() + secs
        while time.time() < end:
            c = self.chat(phone)
            if c:
                new = c["messages"][before:]
                if any(m["type"] in ("sent", "suggested") for m in new):
                    self.pg.wait_for_timeout(1200)
                    reply = " ".join(m.get("text", "") for m in new if m["type"] in ("sent", "suggested"))
                    print(f"     {name}: {text[:100]}\n     office: {reply[:300]}", flush=True)
                    return reply
            self.pg.wait_for_timeout(500)
        print(f"     {name}: {text[:100]}\n     office: (nothing within {secs}s)", flush=True)
        return ""

    def open_nova(self, who="layla"):
        self.be(who, "index.html")
        return self.pg

    def ask_nova(self, text, who="layla", secs=90):
        """Typed into her real chat box. Returns her reply as shown on the page."""
        self.be(who)
        if "index.html" not in self.pg.url:
            self.pg.goto(f"{self.base}/web/index.html")
            self.pg.wait_for_timeout(900)
            self.caption(self.step_text)
        box = self.pg.locator("#say")
        said = self.pg.locator("#chat .m, #chat .msg, #log .m, #log .msg, .pa-log > *")
        n = self.pg.evaluate("document.body.innerText.length")
        box.fill(text)
        box.press("Enter")
        end = time.time() + secs
        last, same = "", 0
        while time.time() < end:
            self.pg.wait_for_timeout(700)
            now = self.pg.evaluate("document.body.innerText")
            if len(now) > n + len(text) + 2 and "One moment" not in now[-200:]:
                same = same + 1 if now == last else 0
                if same >= 2:
                    break
            last = now
        last_answer = self.pg.locator(".answer:not(.me)").last
        if self.pg.locator(".answer").count() and "me" not in (self.pg.locator(".answer").last.get_attribute("class") or "").split():
            reply = re.sub(r"^Nova\s*", "", last_answer.inner_text()).strip()
            print(f"     you: {text[:120]}\n     nova: {reply[:500]}", flush=True)
            return reply
        text_now = self.pg.evaluate("document.body.innerText")
        i = text_now.rfind(text)
        reply = text_now[i + len(text):].strip() if i >= 0 else ""
        reply = re.split(r"\n(?:Message Nova|Ask your PA|Go live|Send\n)", reply)[0].strip()
        print(f"     you: {text[:120]}\n     nova: {reply[:400]}", flush=True)
        return reply

    def clock(self, hours=0, minutes=0):
        n = self.owner.post(f"{self.base}/api/case/clock", data={"hours": hours, "minutes": minutes}).json()["now"]
        self._moved(n)
        self.caption(f"Time skips ahead to {n[:16].replace('T', ' ')}", "#d9b3ff")
        self.pg.wait_for_timeout(1200)
        return n

    def set_clock(self, at):
        n = self.owner.post(f"{self.base}/api/case/set-clock", data={"at": at}).json()["now"]
        self._moved(n)
        self.caption(f"The clock is set to {n[:16].replace('T', ' ')}", "#d9b3ff")
        self.pg.wait_for_timeout(1000)
        return n

    def tick(self):
        r = self.owner.post(f"{self.base}/api/case/tick").json()
        for k, v in r["did"].items():
            if str(v).startswith("FAILED"):
                self._bad(f"sweep {k}: {v}")
        return r["did"]

    def finish(self):
        for c, _ in self.people.values():
            c.close()
        self.b.close()
        self.pw.stop()
        print(f"\n{self.name}: {self.good} passed, {self.bad} failed. Page errors: {self.errors or 'none'}", flush=True)
        return self.good, self.bad, self.errors
