"""Every file a person downloads from a deal, opened and read: is it really a PDF, is it this client's, is the signature on it, and is it closed to people who shouldn't have it.

    python e2e/case/signed.py http://127.0.0.1:8040 <out dir> <client's first name>
"""
import hashlib
import io
import re
import sys
from pathlib import Path

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).parent))
from browser import Run, Stop  # noqa: E402

BASE, OUT, WHO = sys.argv[1], sys.argv[2], sys.argv[3]
r = Run(BASE, OUT, "signed")


def read(body):
    p = PdfReader(io.BytesIO(body))
    images = sum(len(pg.images) for pg in p.pages)
    return {"pages": len(p.pages), "text": " ".join((pg.extract_text() or "") for pg in p.pages), "images": images}


def walk():
    deal = r.chat("971507771001")["deal"]
    broker = r.owner.get(f"{BASE}/api/desk/deals/{deal}").json()["broker"]
    r.be(broker, f"deal.html?deal={deal}")
    r.step("Every download on the deal page, as the broker")
    r.pg.wait_for_selector("#dept-comp")
    r.pg.wait_for_timeout(1500)
    links = r.pg.evaluate("[...document.querySelectorAll('a[href]')].filter((a) => /\\.pdf|\\/media\\//.test(a.href)).map((a) => [a.innerText.trim(), a.getAttribute('href')])")
    links = list({h: (t, h) for t, h in links}.values())
    r.check("the deal page has files to download", links, [t for t, _ in links])
    api = r.api(broker)
    files = {}
    sent = {e["content"]["sha"] for e in r.owner.get(f"{BASE}/api/events?deal={deal}").json() if e["type"] == "docs.received"}
    r.check("the signed Form F can be downloaded", any("form-F" in h for _, h in links), [h for _, h in links if "signed" in h])
    for label, href in links:
        got = api.get(BASE + href)
        name = f"{label or href}"
        if not r.check(f"\"{name}\" downloads", got.ok, f"{got.status} {href}"):
            continue
        body = got.body()
        if href.endswith(".jpg"):
            r.check(f"{href.rsplit('-', 1)[-1]}: a real photo, the same file the client sent", body[:2] == b"\xff\xd8" and hashlib.sha256(body).hexdigest() in sent, f"{len(body)} bytes")
            continue
        if not r.check(f"\"{name}\" is a real file", body[:5] == b"%PDF-" and len(body) > 500, f"{len(body)} bytes"):
            continue
        try:
            info = read(body)
        except Exception as e:  # noqa: BLE001
            r.check(f"\"{name}\" opens", False, repr(e)[:160])
            continue
        files[href] = info
        r.check(f"\"{name}\" opens, and it's this client's", (WHO.lower() in info["text"].lower() or "invoice" in name.lower() or "receipt" in name.lower() or (info["text"].startswith("Form A") and deal in info["text"] and "Villa 88" in info["text"])), f"{info['pages']} pages, {info['images']} images: {info['text'][:140]}")
        if re.search("signed", name, re.I):
            r.check(f"\"{name}\" carries the signature", info["images"] or re.search("signed by|signature", info["text"], re.I), f"{info['images']} images")
    r.step("The first download, in the browser the way a person opens it")
    if links:
        with r.pg.context.expect_page() as pop:
            r.pg.locator(f'a[href="{links[0][1]}"]').first.click()
        pop.value.wait_for_timeout(1500)
        r.check("it opens in a new tab", pop.value.url.endswith(links[0][1].split("/")[-1]) or ".pdf" in pop.value.url or "/media/" in pop.value.url, pop.value.url)
        pop.value.close()
    r.step("Who may not have these files")
    sensitive = [h for _, h in links if "/media/" in h or "forms" in h]
    other = next(x for x in ("omar", "hamza", "nadia") if x != broker)
    for who, label in (("maya", "Marketing"), (other, "another broker")):
        api2 = r.api(who)
        for h in sensitive[:3]:
            got = api2.get(BASE + h)
            r.check(f"{who} ({label}) can't open {h.split('/')[-1][:40]}", got.status in (401, 403), got.status)
    got = r.api(other).get(f"{BASE}/api/desk/deals/{deal}")
    r.check(f"{other} can't open another broker's deal", got.status == 403, got.status)
    anon = r.b.new_context()
    for h in sensitive[:3]:
        got = anon.request.get(BASE + h)
        r.check(f"nobody signed out can open {h.split('/')[-1][:40]}", got.status in (401, 403) or "login" in got.url, got.status)
    anon.close()


try:
    r.be("layla", "index.html")
    r.part("downloads", walk)
except Stop as e:
    print("STOPPED:", e, flush=True)
good, bad, errors = r.finish()
print(f"RESULT {good} passed, {bad} failed")
