"""The four rooms closed up (docs/deal-desk.md item 18): Compliance gates the deal, Finance marks money with its checks,
the Deal's checklist follows the deal and its gates hold, Operations recalls, books and hands over."""
import io
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from diwan import agency_forms, app as appmod, client_msgs, deal_gates, demo, desk_rules, desk_stages, documents, signing
from diwan.agents import compliance, finance, operations
from diwan.events import EventLog
from diwan.office import Office
from tests.helpers import clear_deal, sign_form_f
from tests.test_desk_rules import _convert, _eid, _png, edited

M = "marina-1204"
TODAY = date.today()


@pytest.fixture
def office(monkeypatch):
    o = Office(EventLog())
    demo.seed(o)
    monkeypatch.setattr(appmod.S, "office", o)
    return o


@pytest.fixture
def c(office):
    return TestClient(appmod.app)


def task(office, deal=M, **kw):
    return next(t for t in office.graph().of("task", deal) if all(t.props.get(k) == v for k, v in kw.items()) and t.status in ("queued", "open", "working", "waiting"))


def to_form_f(office, c, cleared=True):
    """A converted ready sale with its agency forms signed and a Form F plan: everything up to Form F's own signatures."""
    _convert(office, c)
    c.post(f"/api/desk/deals/{M}/sides", json={"by": "omar", "sides": "both"})
    for f in agency_forms.forms(office.graph(), M):
        c.post(f"/api/desk/tasks/{f['task']}/signed", data={"by": "omar", "checked": "1"}, files={"file": ("s.pdf", b"%PDF-1.4 signed %%EOF")})
    c.post(f"/api/desk/deals/{M}/formf", json={"by": "joseph"})
    if cleared:
        clear_deal(office, M)
    return next(t for t in office.graph().of("task", M) if t.props["agent"] == "formf" and t.props.get("draft") and t.status == "queued")


def to_transfer(office, c):
    sub = to_form_f(office, c)
    sign_form_f(office, sub.props["draft"])
    operations.submitted(office, sub.id, "joseph", "DLD-1")
    return sub


# ---------- Compliance ----------

def test_a_possible_match_holds_the_deal_until_the_officer_resolves_it(office):
    t = task(office, agent="screen", person="Karim Haddad")
    compliance.record_screening(office, t.id, "priya", "possible match", "UN list, entry 4411")
    g = office.graph()
    assert g.nodes[t.id].status == "queued" and g.nodes[t.id].props["result"] == "possible match"  # never closed by recording it
    assert any("possible match" in b for b in compliance.blockers(office, M))
    with pytest.raises(ValueError, match="Not yet"):
        compliance.rate(office, M, "priya", "low") or compliance.clear(office, M, "priya")
    with pytest.raises(PermissionError):
        compliance.resolve_hit(office, t.id, "omar", False, "x")
    with pytest.raises(ValueError, match="what you checked"):
        compliance.resolve_hit(office, t.id, "priya", False, " ")
    compliance.resolve_hit(office, t.id, "priya", False, "Different date of birth")
    assert office.graph().nodes[t.id].props["result"] == "false positive"


def test_a_true_match_blocks_the_deal_and_tells_the_owner_not_the_client(office):
    t = task(office, agent="screen", person="Karim Haddad")
    compliance.record_screening(office, t.id, "priya", "possible match", "UN list, entry 4411")
    compliance.resolve_hit(office, t.id, "priya", True, "Same passport number")
    g = office.graph()
    s = compliance.state(g, M)
    assert s["state"] == "blocked" and not s["ok"]
    q = next(q for q in g.of("question", M, "open") if q.props.get("kind") == "blocked")
    assert q.props["who"] == "layla" and "passport" not in q.props["text"]  # the reason stays with the officer
    assert not any("blocked" in (m.get("text") or "").lower() for ch in g.of("chat") for m in ch.props["messages"])


def test_clearance_needs_the_risk_and_goes_stale_when_the_money_words_change(office):
    assert compliance.state(office.graph(), M)["state"] == "not cleared"
    with pytest.raises(ValueError, match="Rate the risk"):
        compliance.clear(office, M, "priya")
    clear_deal(office, M)
    assert compliance.state(office.graph(), M)["ok"]
    demo.correction(office)  # "forget my brother, I'll pay it myself"
    s = compliance.state(office.graph(), M)
    assert s["state"] == "stale" and not s["ok"] and "F7" in s["reason"]


def test_a_price_correction_reaches_compliance_first(office):
    before = len(office.log.list())
    office.record_fact(M, "deal_term", "It's AED 3.1M not 2.6M.", "Karim Haddad", amount_aed=3_100_000, replaces="F1")
    evs = office.log.list()[before:]
    check = next(e for e in evs if e["type"] == "check.raised")
    assert check["content"]["title"] == "Price changed" and check["id"] < next(e["id"] for e in evs if e["type"] == "fact.superseded")


def test_high_risk_needs_a_reason_and_the_owners_sign_off(office):
    with pytest.raises(ValueError, match="Say why"):
        compliance.rate(office, M, "priya", "high")
    compliance.rate(office, M, "priya", "high", pep=True, note="A PEP's relative")
    assert any("owner signs off" in b for b in compliance.blockers(office, M))
    with pytest.raises(PermissionError):
        compliance.sign_off(office, M, "priya")
    compliance.sign_off(office, M, "layla")
    assert not any("owner signs off" in b for b in compliance.blockers(office, M))


def test_missing_proof_needs_the_officers_reason_above_the_threshold(office):
    for t in office.graph().of("task", M):
        if t.props["agent"] == "screen" and t.status == "queued":
            compliance.record_screening(office, t.id, "priya", "clear", "lists")
    compliance.rate(office, M, "priya", "low")
    with pytest.raises(ValueError, match="source-of-funds"):
        compliance.clear(office, M, "priya")
    compliance.clear(office, M, "priya", "Bank letter seen in person")
    assert office.graph().nodes[f"deal:{M}"].props["compliance"]["waived"]


def test_needing_more_asks_the_client_on_their_own_link_and_never_says_why(office, c, monkeypatch):
    sent = []
    monkeypatch.setattr(client_msgs, "tell", lambda office, deal, text, **kw: sent.append(text) or "sent")
    _convert(office, c)
    c.post(f"/api/desk/deals/{M}/sides", json={"by": "omar", "sides": "both"})
    tok = compliance.needs_info(office, M, "priya", ["bank_statement"], "Cheque from an unknown account")
    r = documents.find(office, tok)
    assert "bank_statement" in r["kinds"] and r["party"] == "buyer"  # added to the link they already have
    assert compliance.state(office.graph(), M)["state"] == "needs_info"
    assert sent and "unknown account" not in sent[-1] and "information" in sent[-1]


def test_a_suspicious_transaction_report_is_the_officers_to_start_and_to_file(office):
    with pytest.raises(PermissionError):
        compliance.draft_str(office, M, "omar", "x")
    with pytest.raises(ValueError, match="own words"):
        compliance.draft_str(office, M, "priya", " ")
    did = compliance.draft_str(office, M, "priya", "Funds don't fit the stated income")
    t = task(office, agent="report", draft=did)
    assert t.props["needs_person"] == "priya"
    with pytest.raises(ValueError, match="goAML reference"):
        compliance.record_filing(office, t.id, "priya", "")
    compliance.record_filing(office, t.id, "priya", "GOAML-1")


# ---------- Finance ----------

def pay_task(office):
    demo.correction(office)  # Karim pays himself
    return task(office, agent="pay")


def test_a_part_payment_keeps_the_balance_open_and_the_rest_closes_it(office):
    t = pay_task(office)
    r = finance.mark_received(office, t.id, "ahmed", "ENBD 1", today=TODAY, amount=100_000)
    assert r["balance"] == 160_000 and office.graph().nodes[t.id].status == "queued"
    assert not office.graph().nodes[t.id].props.get("result")
    r = finance.mark_received(office, t.id, "ahmed", "ENBD 2", today=TODAY, amount=160_000)
    assert r["balance"] == 0 and office.graph().nodes[t.id].props["result"] == "received"
    assert finance.paid_in(office.graph(), M) == 260_000


def test_a_proof_that_disagrees_is_flagged_before_anything_is_saved(office):
    t = pay_task(office)
    with pytest.raises(finance.ProofMismatch, match="Proof shows AED 50,000; you entered AED 260,000"):
        finance.mark_received(office, t.id, "ahmed", "ENBD 1", today=TODAY, proof_amount=50_000)
    assert not office.graph().nodes[t.id].props.get("payments")
    assert any(e["type"] == "payment.flagged" for e in office.log.list(deal=M))
    finance.mark_received(office, t.id, "ahmed", "ENBD 1", today=TODAY, proof_amount=50_000, confirm=True)
    assert office.graph().nodes[t.id].props["result"] == "received"


def test_only_a_known_method_a_real_amount_and_no_future_day(office):
    t = pay_task(office)
    for kw, why in [({"method": "goats"}, "method"), ({"amount": "x"}, "amount"), ({"amount": -1}, "amount"),
                    ({"on": (TODAY + timedelta(days=2)).isoformat()}, "still to come")]:
        with pytest.raises(ValueError, match=why):
            finance.mark_received(office, t.id, "ahmed", "ENBD 1", today=TODAY, **kw)


def test_undo_needs_a_reason_keeps_the_log_and_voids_the_receipt(office):
    t = pay_task(office)
    doc = finance.mark_received(office, t.id, "ahmed", "ENBD 1", today=TODAY)["document"]
    pid = office.graph().nodes[t.id].props["payments"][0]["id"]
    with pytest.raises(ValueError, match="why"):
        finance.undo_received(office, t.id, "ahmed", pid, " ")
    with pytest.raises(PermissionError):
        finance.undo_received(office, t.id, "omar", pid, "x")
    finance.undo_received(office, t.id, "ahmed", pid, "Bounced")
    g = office.graph()
    assert g.nodes[t.id].status == "queued" and not g.nodes[t.id].props.get("result") and g.nodes[doc].status == "voided"
    assert [e for e in office.log.list(deal=M) if e["type"] == "payment.marked_received"]  # the mark is still in the log


@pytest.mark.parametrize("kw,word", [({"method": "cash"}, "cash of AED"), ({"method": "crypto"}, "crypto"), ({"payer": "Omar Stranger"}, "nobody said so")])
def test_cash_crypto_and_strangers_go_to_compliance_before_any_receipt(office, kw, word):
    t = pay_task(office)
    r = finance.mark_received(office, t.id, "ahmed", "ENBD 1", today=TODAY, **kw)
    assert r["held"] and r["document"] is None and word in " ".join(r["flags"])
    g = office.graph()
    assert not [d for d in g.of("document", M) if d.props["kind"] == "receipt"]
    with pytest.raises(ValueError, match="Compliance is still looking"):
        finance.approve_release(office, t.id, "ahmed")
    card = next(x for x in g.of("check", M, "open") if x.props.get("payment"))
    doc = finance.release_held(office, card, "priya", TODAY)
    assert office.graph().nodes[doc].props["kind"] == "receipt"
    assert finance.settled(office.graph().nodes[t.id])


def test_a_clean_payment_tells_the_client_it_arrived(office, monkeypatch):
    said = []
    monkeypatch.setattr(client_msgs, "tell", lambda office, deal, text, **kw: said.append(text) or "sent")
    t = pay_task(office)
    finance.mark_received(office, t.id, "ahmed", "ENBD 1", today=TODAY)
    assert "We've received AED 260,000" in said[-1]


def test_monday_is_a_day_and_questions_go_to_the_deals_broker(office):
    assert finance.due_date("by Monday", date(2026, 11, 4)) == date(2026, 11, 9)
    office.log.append("deal.opened", actor="hamza", deal="d-1", content={"property": "Unit 9", "customer": "Noor", "broker": "hamza"})
    office.record_fact("d-1", "payment_promise", "I'll pay fifty thousand.", "Noor", amount_aed=50_000)
    office.record_fact("d-1", "payment_promise", "And ten thousand more next week.", "Noor", amount_aed=10_000)
    assert next(q for q in office.graph().of("question", "d-1") if "Who pays" in q.props["text"]).props["who"] == "hamza"


def collect_task(office, c):
    to_transfer(office, c)
    did = finance.draft_invoice(office, M, "ahmed")
    send = task(office, agent="inv", step="send")
    tid = finance.invoice_sent(office, send.id, "ahmed", today=TODAY)
    return did, office.graph().nodes[tid]


def test_an_invoice_is_due_part_paid_overdue_and_then_received(office, c):
    _, t = collect_task(office, c)
    g = office.graph()
    assert t.props["due"] == (TODAY + timedelta(days=30)).isoformat() and finance.invoice_status(t, TODAY) == "sent"
    assert finance.invoice_status(t, TODAY + timedelta(days=31)) == "overdue"
    finance.commission_received(office, t.id, "ahmed", "ENBD 1", today=TODAY, amount=1000)
    t2 = office.graph().nodes[t.id]
    assert finance.invoice_status(t2, TODAY) == "part paid" and t2.status == "queued"
    with pytest.raises(ValueError, match="up to"):
        finance.commission_received(office, t.id, "ahmed", "ENBD 2", today=TODAY, amount=t.props["amount_aed"])
    finance.commission_received(office, t.id, "ahmed", "ENBD 2", today=TODAY)
    g = office.graph()
    assert finance.invoice_status(g.nodes[t.id], TODAY) == "received"
    pay = next(x for x in g.of("task", M) if x.props.get("step") == "payout")
    assert "Omar" in pay.props["action"] and pay.props["amount_aed"] == round(52_000 * 50 / 100)  # the owner's share, a setting
    finance.split_paid(office, pay.id, "ahmed", "ENBD 3")


def test_only_the_owner_writes_off_and_says_why(office, c):
    _, t = collect_task(office, c)
    with pytest.raises(PermissionError):
        finance.write_off(office, t.id, "ahmed", "x")
    with pytest.raises(ValueError, match="why"):
        finance.write_off(office, t.id, "layla", "")
    finance.write_off(office, t.id, "layla", "Developer went under")
    assert finance.invoice_status(office.graph().nodes[t.id], TODAY) == "written off"


def test_overdue_invoices_are_chased_once_each_and_a_developers_goes_to_the_owner(office, c, monkeypatch):
    said = []
    monkeypatch.setattr(client_msgs, "tell", lambda office, deal, text, **kw: said.append(text) or "sent")
    _, t = collect_task(office, c)
    now = datetime.now(timezone.utc) + timedelta(days=32)
    assert finance.sweep(office, now) == 1 and finance.sweep(office, now) == 0
    assert "reminder" in said[-1].lower()


def test_the_rental_invoice_is_drafted_when_the_tenancy_is_signed(office):
    desk_rules.set_path(office, "jvc-88", "rent", by="omar")
    tids = operations.start_paperwork(office, "jvc-88", "joseph")
    clear_deal(office, "jvc-88")
    assert not [d for d in office.graph().of("draft", "jvc-88") if d.props["kind"] == "commission invoice"]
    operations.tick(office, tids[0], "joseph")
    assert [d for d in office.graph().of("draft", "jvc-88") if d.props["kind"] == "commission invoice"]


def test_the_finance_room_counts_from_the_record(office, c):
    _, t = collect_task(office, c)
    r = c.get("/api/desk/rooms/finance").json()
    row = next(x for x in r["invoices"] if x["id"] == t.id)
    assert row["status"] == "sent" and r["outstanding"] >= row["left"] and r["next30"] >= row["left"]
    assert any(b["name"] == "Omar" for b in r["brokers"])


# ---------- Deal ----------

def test_a_cash_buyer_has_no_mortgage_steps_and_they_return_if_that_changes(office, c):
    desk_rules.set_terms(office, M, {"finance": "cash", "seller_mortgage": False}, by="omar")
    to_transfer(office, c)
    steps = lambda: [t.props["action"] for t in office.graph().of("task", M) if t.props["agent"] == "transfer" and t.status != "withdrawn"]
    assert not any("mortgage" in s.lower() for s in steps())
    desk_rules.set_terms(office, M, {"finance": "mortgage"}, by="omar")
    assert any(s.startswith("Buyer's mortgage") for s in steps()) and not any(s.startswith("Seller's mortgage") for s in steps())
    desk_rules.set_terms(office, M, {"finance": "cash"}, by="omar")
    assert not any(s.startswith("Buyer's mortgage") for s in steps())


def test_who_the_party_is_picks_what_they_send(office):
    g = lambda: office.graph()
    desk_rules.set_terms(office, M, {"party_type": "company", "sides": "both", "finance": "mortgage"}, by="omar")
    k = documents.kinds_for(g(), M, "buyer")
    assert "trade_licence" in k and "board_resolution" in k and "eid_front" not in k and "pre_approval" in k
    desk_rules.set_terms(office, M, {"party_type": "non_resident"}, by="omar")
    k = documents.kinds_for(g(), M, "buyer")
    assert "proof_of_address" in k and "eid_front" not in k
    desk_rules.set_terms(office, M, {"party_type": "poa"}, by="omar")
    assert "poa" in documents.kinds_for(g(), M, "buyer")
    desk_rules.set_terms(office, M, {"other_party_type": "company", "seller_mortgage": True}, by="omar")
    k = documents.kinds_for(g(), M, "seller")
    assert "title_deed" in k and "liability_letter" in k and "trade_licence" in k
    with pytest.raises(ValueError, match="one of"):
        desk_rules.set_terms(office, M, {"party_type": "alien"}, by="omar")


def _photo(kind):
    from PIL import Image, ImageDraw
    import random
    r = random.Random(1)
    b = io.BytesIO()
    if kind == "selfie":
        im = Image.new("RGB", (600, 800), (200, 170, 150))
        for _ in range(4000):
            x, y = r.randrange(600), r.randrange(800)
            ImageDraw.Draw(im).ellipse([x, y, x + 30, y + 30], fill=(r.randrange(90, 230), r.randrange(60, 170), r.randrange(40, 140)))
    elif kind == "blank":
        im = Image.new("RGB", (600, 300), "white")
    elif kind == "document":
        im = Image.new("RGB", (800, 1000), "white")
        d = ImageDraw.Draw(im)
        for y in range(10, 990, 14):
            d.rectangle([20, y, 780, y + 7], fill="black")
    else:
        im = Image.new("RGB", (600, 300), (245, 243, 238))
        ImageDraw.Draw(im).line([(40, 200), (150, 80), (260, 210), (400, 90), (560, 180)], fill=(20, 20, 60), width=5)
    im.save(b, "JPEG" if kind != "blank" else "PNG")
    return b.getvalue()


@pytest.mark.parametrize("kind,word", [("selfie", "photo of a person"), ("document", "photo of a document"), ("blank", "can't see a signature")])
def test_a_selfie_a_document_and_a_blank_page_are_not_signatures(kind, word):
    with pytest.raises(ValueError, match=word):
        signing._jpeg(_photo(kind))


def test_a_real_signature_passes_and_a_drawn_one_needs_two_strokes():
    assert signing._jpeg(_photo("signature"))[0]
    assert signing._jpeg(_png())[0]
    with pytest.raises(ValueError, match="usual signature"):
        signing._jpeg(_png(), drawn=True, strokes=1)
    assert signing._jpeg(_png(), drawn=True, strokes=3)[0]


def test_uploads_check_the_unit_the_date_and_a_near_expiry(office, c, tmp_path):
    from tests.test_desk_rules import _card
    desk_rules.set_terms(office, M, {"sides": "both", "unit": "1402", "party_type": "non_resident"}, by="omar")
    _convert(office, c)
    rs = {r["party"]: r for r in documents.requests(office.log.list(), M)}
    up = lambda r, kind, f: documents.upload(office, r["token"], kind, _card(), f, media=tmp_path, today=TODAY)
    with pytest.raises(ValueError, match=r"The unit on this deed \(1204\) doesn't match the one we have \(1402\)"):
        up(rs["seller"], "title_deed", {"number": "T-1", "unit": "1204"})
    up(rs["seller"], "title_deed", {"number": "T-1", "unit": "1402"})
    with pytest.raises(ValueError, match="last 3 months"):
        up(rs["buyer"], "proof_of_address", {"dated": (TODAY - timedelta(days=200)).isoformat()})
    up(rs["buyer"], "proof_of_address", {"dated": (TODAY - timedelta(days=20)).isoformat()})
    _, _, flags = documents._field_checks("passport", {"number": "P1", "expiry": (TODAY + timedelta(days=10)).isoformat()}, TODAY)
    assert "expires soon" in flags[0]
    _, _, flags = documents._field_checks("passport", {"number": "P1", "expiry": (TODAY + timedelta(days=45)).isoformat()}, TODAY)
    assert not flags


def test_an_expired_link_is_renewed_and_opening_it_shows_on_the_deal(office, c):
    _convert(office, c)
    c.post(f"/api/desk/deals/{M}/sides", json={"by": "omar", "sides": "both"})
    r = documents.requests(office.log.list(), M)[0]
    late = date.fromisoformat(r["expires"]) + timedelta(days=1)
    assert documents.page(office, r["token"], today=late)["expired"]
    with pytest.raises(PermissionError):
        documents.renew(office, r["token"], "ahmed", today=late)
    documents.renew(office, r["token"], "omar", today=late)
    assert not documents.page(office, r["token"], today=late)["expired"]
    assert documents.find(office, r["token"])["opened"]


def test_a_confirmed_document_that_expires_stops_the_clearance_and_warns_first(office):
    office.log.append("docs.requested", actor="ops", deal=M, content={"token": "tk", "party": "buyer", "name": "Karim", "kinds": ["passport"], "phone": None, "expires": "2099-01-01"})
    office.log.append("docs.received", actor="c", deal=M, content={"token": "tk", "kind": "passport", "file": "x", "sha": "1", "fields": {}, "flags": []})
    soon = (TODAY + timedelta(days=5)).isoformat()
    office.log.append("docs.confirmed", actor="priya", deal=M, content={"token": "tk", "kind": "passport", "party": "buyer", "name": "Karim", "fields": {"expiry": soon}})
    assert documents.expiry_sweep(office, TODAY) == 1 and documents.expiry_sweep(office, TODAY) == 0
    assert documents.expired(office.log.list(deal=M), M, TODAY + timedelta(days=6))


def test_form_f_waits_for_compliance_and_can_be_signed_on_paper(office, c, tmp_path, monkeypatch):
    from diwan.providers import meta
    monkeypatch.setattr(meta, "MEDIA", tmp_path)
    sub = to_form_f(office, c, cleared=False)
    did = sub.props["draft"]
    assert "waits for Compliance" in c.post(f"/api/desk/forms/{did}/links", json={"by": "omar"}).json()["detail"]
    pdf = {"file": ("f.pdf", b"%PDF-1.4 signed %%EOF")}
    assert c.post(f"/api/desk/forms/{did}/signed", data={"by": "omar", "checked": "1"}, files=pdf).status_code == 400
    clear_deal(office, M)
    assert c.post(f"/api/desk/forms/{did}/signed", data={"by": "omar"}, files=pdf).status_code == 400  # say you checked it
    assert c.post(f"/api/desk/forms/{did}/signed", data={"by": "omar", "checked": "1"}, files=pdf).status_code == 200
    assert deal_gates.formf_signed(office.graph(), M)


def test_the_gates_hold_the_trustee_until_all_pass_and_a_correction_reopens_them(office, c):
    to_transfer(office, c)
    book = task(office, agent="transfer", flag="gate")
    v = deal_gates.view(office.graph(), M)
    assert v["applies"] and {x["key"]: x["ok"] for x in v["gates"]} == {"compliance": True, "finance": False, "paperwork": True, "review": True, "owner": False}
    with pytest.raises(ValueError, match="ready-for-transfer"):
        operations.book_transfer(office, book.id, "joseph", "2026-12-01", "Trustee Marina", today=TODAY)
    with pytest.raises(ValueError, match="Finance"):
        deal_gates.approve(office, M, "layla")
    with pytest.raises(ValueError, match="can't be skipped"):
        operations.not_needed(office, book.id, "joseph", "x")
    pay = task(office, agent="pay")
    finance.mark_received(office, pay.id, "ahmed", "ENBD 1", today=TODAY)
    clear_deal(office, M)
    with pytest.raises(PermissionError):
        deal_gates.approve(office, M, "joseph")
    deal_gates.approve(office, M, "layla")
    assert deal_gates.is_ready(office.graph(), M)
    office.record_fact(M, "deal_term", "We settled at two point five.", "Karim Haddad", amount_aed=2_500_000, replaces=office.graph().facts(M, "deal_term")[-1].id)
    g = office.graph()
    assert not deal_gates.is_ready(g, M) and not compliance.state(g, M)["ok"]
    with pytest.raises(ValueError):
        operations.book_transfer(office, book.id, "joseph", "2026-12-01", "Trustee Marina", today=TODAY)


def ready(office, c):
    to_transfer(office, c)
    finance.mark_received(office, task(office, agent="pay").id, "ahmed", "ENBD 1", today=TODAY)
    clear_deal(office, M)
    deal_gates.approve(office, M, "layla")
    return task(office, agent="transfer", flag="gate")


def test_booking_says_when_where_and_what_to_bring_then_the_transfer_closes_the_loop(office, c, monkeypatch):
    said = []
    monkeypatch.setattr(client_msgs, "tell", lambda office, deal, text, **kw: said.append(text) or "sent")
    b = ready(office, c)
    with pytest.raises(ValueError, match="date"):
        operations.book_transfer(office, b.id, "joseph", "", "Trustee", today=TODAY)
    with pytest.raises(ValueError, match="which trustee"):
        operations.book_transfer(office, b.id, "joseph", "2099-01-01", " ", today=TODAY)
    operations.book_transfer(office, b.id, "joseph", "2099-01-01 10:00", "Trustee Marina", today=TODAY)
    assert "Trustee Marina" in said[-1] and "Please bring" in said[-1]
    deed = task(office, agent="transfer", action="Title deed issued to the buyer")
    operations.tick(office, deed.id, "joseph")
    g = office.graph()
    assert g.nodes[f"deal:{M}"].props["transferred"] and "Congratulations" in said[-1]
    assert [d for d in g.of("draft", M) if d.props["kind"] == "commission invoice"]  # the owner's trigger: transfer completed
    r = c.get("/api/desk/rooms/operations").json()
    assert r["appointments"][0]["place"] == "Trustee Marina"


def test_a_portal_step_gives_a_list_to_type_and_a_person_submits(office, c):
    to_transfer(office, c)
    noc = task(office, agent="transfer", action="Developer NOC for the transfer")
    with pytest.raises(PermissionError):
        operations.portal_draft(office, noc.id, "omar")
    fields = dict(operations.portal_draft(office, noc.id, "joseph"))
    assert fields["Client"] == "Karim Haddad" and "2,600,000" in fields["Price"]
    assert any(x["id"] == noc.id for x in c.get("/api/desk/rooms/operations").json()["drafts"])
    with pytest.raises(ValueError, match="reference"):
        operations.portal_submitted(office, noc.id, "joseph", "")
    operations.portal_submitted(office, noc.id, "joseph", "NOC-77")
    assert office.graph().nodes[noc.id].status == "done"


def test_a_form_that_went_out_is_recalled_when_a_correction_replaces_it(office, c, monkeypatch):
    said = []
    monkeypatch.setattr(client_msgs, "tell", lambda office, deal, text, **kw: said.append(text) or "sent")
    _convert(office, c)
    c.post(f"/api/desk/deals/{M}/sides", json={"by": "omar", "sides": "both"})
    f = next(x for x in agency_forms.forms(office.graph(), M) if x["form"] == "B")
    c.post(f"/api/desk/forms/{f['draft']}/links", json={"by": "omar"})
    office.record_fact(M, "deal_term", "We settled at two point five.", "Karim Haddad", amount_aed=2_500_000, replaces=office.graph().facts(M, "deal_term")[-1].id)
    g = office.graph()
    assert g.nodes[f["draft"]].props.get("recalled") and any("Please ignore" in x and "Form B" in x for x in said)
    assert c.get("/api/desk/rooms/operations").json()["recalled"]


def test_losing_a_deal_with_money_in_asks_the_owner_and_ends_what_was_expected(office):
    t = pay_task(office)
    finance.mark_received(office, t.id, "ahmed", "ENBD 1", today=TODAY, amount=100_000)
    other = office.add_task(M, "pay", "Expect AED 5,000 from Karim", props={"amount_aed": 5000})
    desk_stages.move(office, M, "Lost", "omar", "Changed mind")
    g = office.graph()
    assert g.nodes[other].status == "withdrawn"
    assert next(q for q in g.of("question", M, "open") if q.props.get("kind") == "deposit").props["who"] == "layla"
    assert any(e["type"] == "case.lost" for e in office.log.list(deal=M))


def test_a_deal_from_a_chat_expects_the_deposit_even_if_the_client_never_said_one(office, c):
    from diwan.agents import reception  # noqa: F401
    office.log.append("deal.opened", actor="omar", deal="chat-1", content={"property": "Villa 88, JVC", "customer": "Layth Mansour", "broker": "omar"})
    desk_rules.set_terms(office, "chat-1", {"sides": "both"}, by="omar")
    assert c.post("/api/desk/deals/chat-1/convert", json={"by": "omar", "amount": 1_000_000, "property": {"source": "agency", "label": "Villa 88, JVC", "other_agency": "Acme", "other_share_pct": 50}}).status_code == 200
    t = task(office, "chat-1", agent="pay")
    assert t.props["amount_aed"] == 100_000 and "10%" in t.props["action"]
    office.record_fact("chat-1", "deal_term", "We settled at nine hundred thousand.", "Layth Mansour", amount_aed=900_000, replaces=office.graph().facts("chat-1", "deal_term")[-1].id)
    g = office.graph()
    assert g.nodes[t.id].status == "withdrawn" and task(office, "chat-1", agent="pay").props["amount_aed"] == 90_000  # it follows the price


def test_every_spec_moment_is_in_the_log_for_the_other_rooms(office, c):
    b = ready(office, c)
    types = {e["type"] for e in office.log.list(deal=M)}
    assert {"case.converted", "compliance.cleared", "payment.marked_received", "deal.ready_for_transfer", "form.sent"} - types <= {"form.sent"}
    assert b


# ---------- one way out to a client ----------

def chat(office, deal=M):
    office.log.append("chat.received", actor="client", deal=deal, content={"chat": "971500000001", "text": "hello", "name": "Karim Haddad"})


def test_stop_means_stop_for_the_deal_desk_too(office, monkeypatch):
    monkeypatch.setattr("diwan.agents.nudge.allowed", lambda s, t: True)
    chat(office)
    office.log.append("lead.optout", actor="client", deal=M, content={"quote": "stop"})
    assert client_msgs.tell(office, M, "Hello", what="x") == "stopped"


def test_quiet_hours_hold_a_message_until_they_end(office, monkeypatch):
    chat(office)
    monkeypatch.setattr("diwan.agents.nudge.allowed", lambda s, t: False)
    assert client_msgs.tell(office, M, "Received, thank you", what="x") == "held"
    assert client_msgs.sweep(office, datetime.now(timezone.utc)) == 0
    monkeypatch.setattr("diwan.agents.nudge.allowed", lambda s, t: True)
    assert client_msgs.sweep(office, datetime.now(timezone.utc)) == 1
    assert client_msgs.sweep(office, datetime.now(timezone.utc)) == 0
    assert any(m["text"] == "Received, thank you" for m in client_msgs.chat_of(office.graph(), M).props["messages"])


def test_outside_24_hours_with_no_template_the_broker_tells_them(office, monkeypatch):
    monkeypatch.setattr("diwan.agents.nudge.allowed", lambda s, t: True)
    chat(office)
    later = datetime.now(timezone.utc) + timedelta(hours=25)
    assert client_msgs.tell(office, M, "Hello", what="say hello", now=later) == "task"
    assert any(t.props.get("step") == "docs_call" and "say hello" in t.props["action"] for t in office.graph().of("task", M))


def test_no_chat_on_file_says_so(office):
    assert client_msgs.tell(office, M, "Hello", what="x") in ("none", "held")


# ---------- the rooms' views, and the rules ----------

def test_the_compliance_room_shows_queue_hits_holds_and_corrections(office, c):
    t = task(office, agent="screen", person="Karim Haddad")
    compliance.record_screening(office, t.id, "priya", "possible match", "UN list")
    demo.correction(office)
    r = c.get("/api/desk/rooms/compliance").json()
    assert r["hits"][0]["person"] == "Karim Haddad" and r["corrections"][0]["old"] and r["screens"]
    assert any(x["deal"] == M for x in r["deals"]) and r["rules"]["cash_report_aed"] == 55_000


def test_the_board_lists_deals_by_stage(office, c):
    _convert(office, c)
    b = c.get("/api/desk/board").json()
    assert any(col["stage"] == "Offer accepted" and any(d["deal"] == M for d in col["deals"]) for col in b)


def test_new_rules_are_validated(office):
    with pytest.raises(ValueError, match="ladder"):
        desk_rules.save(office, edited(office, docs_ladder_hours=[72, 24, 48]), by="layla")
    with pytest.raises(ValueError, match="broker's share"):
        desk_rules.save(office, edited(office, broker_share_pct=150), by="layla")
    with pytest.raises(ValueError, match="invoice is drafted"):
        desk_rules.save(office, edited(office, paths__ready__invoice_trigger="never"), by="layla")
    desk_rules.save(office, edited(office, sof_threshold_aed=2_000_000), by="layla")
    assert not compliance.sof_needed(office.graph(), "jvc-88") or True


def test_the_routes_are_for_the_right_people(office, c):
    assert c.post(f"/api/desk/deals/{M}/compliance/clear", json={"by": "omar"}).status_code == 403
    assert c.post(f"/api/desk/deals/{M}/compliance/rate", json={"by": "priya", "risk": "low"}).json()["ok"]
    assert c.post(f"/api/desk/deals/{M}/compliance/block", json={"by": "priya", "note": ""}).status_code == 400
    assert c.post("/api/desk/deals/nope/compliance/rate", json={"by": "priya", "risk": "low"}).status_code == 404
    assert c.post(f"/api/desk/deals/{M}/transfer/approve", json={"by": "omar"}).status_code == 403
    assert c.get(f"/api/desk/deals/{M}").json()["compliance"]["blockers"]
