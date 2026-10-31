"""Tax invoices and receipts as PDFs (docs/deal-desk.md item 15). Diwan numbers each invoice it issues in one
sequence that never repeats (the owner's prefix, the year, then a running number), and prints our agency's name,
address and TRN, who it is billed to, what for, the amount before VAT, the VAT and the total in dirhams. A receipt is
printed for money a person marked received. Every figure comes from the record: the invoice from the commission worked
out on the price the client agreed, the receipt from what Finance saw arrive. Our accountant confirms the layout meets
the Federal Tax Authority's requirements before invoices go to clients.
"""
from __future__ import annotations

import re
from datetime import date

from diwan import desk_rules, pdf
from diwan.graph import Graph
from diwan.people import name

FROM = {"buyer": "customer", "tenant": "customer", "developer": "developer", "seller": "seller", "landlord": "landlord"}


def next_number(g: Graph, today: date) -> str:
    """The next invoice number in the owner's sequence: prefix, year, a running number never used before."""
    prefix = f"{desk_rules.rules(g)['invoice_prefix']}{today.year}-"
    used = [int(m.group(1)) for t in g.of("task") if t.props.get("agent") == "inv" and t.props.get("invoice")
            if (m := re.fullmatch(re.escape(prefix) + r"(\d+)", t.props["invoice"]))]
    return f"{prefix}{max(used, default=0) + 1:04d}"


def billed_to(g: Graph, deal: str, payer: str) -> str:
    d, t = g.nodes[f"deal:{deal}"].props, desk_rules.terms(g, deal)
    if payer in ("buyer", "tenant"):
        return d["customer"]
    if payer == "developer":
        return t.get("developer") or "the developer"
    return f"the {payer}"


def _agency(g: Graph) -> list[tuple]:
    a = desk_rules.rules(g)["agency"]
    return [("field", f"From|{a['name'] or '____________________  (to fill)'}"), ("field", f"Address|{a.get('address') or '____________________  (to fill)'}"),
            ("field", f"TRN|{a.get('trn') or '____________________  (to fill)'}"), ("field", f"Office number (ORN)|{a['orn'] or '—'}")]


def invoice_pdf(g: Graph, tid: str) -> bytes:
    """The commission invoice of a send or collect task: a draft preview before it is issued, the tax invoice after."""
    from diwan.agents import finance
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props.get("agent") != "inv" or t.props.get("step") not in ("send", "collect"):
        raise KeyError(tid)
    deal = t.deal
    d, c = g.nodes[f"deal:{deal}"].props, finance.commission(g, deal)
    if c.get("missing"):
        raise ValueError(c["missing"])
    payer = t.props.get("payer") or c["payer"]
    number = t.props.get("invoice")
    when = t.at[:10] if t.props.get("step") == "collect" else date.today().isoformat()  # issued when the collect step began
    trn = desk_rules.terms(g, deal).get("payer_trn")
    blocks = [("title", "Tax invoice" if number else "Tax invoice (draft: not issued)"),
              ("field", f"Invoice number|{number or 'given when issued'}"), ("field", f"Date|{when}"), ("h", "Supplier"), *_agency(g),
              ("h", "Billed to"), ("field", f"Name|{billed_to(g, deal, payer)}"), ("field", f"TRN|{trn or 'not registered / not given'}"),
              ("h", "For"),
              ("field", f"Description|Commission ({c['pct']}%) on the {'let' if c['path'] == 'rent' else 'sale'} of {d['property']}"),
              ("field", f"{c['base_label']}|AED {c['base']:,}"), ("field", f"Broker|{name(d['broker'])}"),
              ("h", "Amount"), ("field", f"Amount before VAT|AED {c['amount']:,.2f}"), ("field", f"VAT {c['vat_pct']}%|AED {c['vat']:,.2f}"),
              ("field", f"Total due|AED {c['total']:,.2f}"),
              ("p", "All amounts in UAE dirhams. Worked out from the price the client agreed and the agreement's rate; Diwan keeps the record it rests on.")]
    return pdf.render(blocks)


def receipt_pdf(g: Graph, tid: str) -> bytes:
    """A receipt for money a person marked received: a client's payment or a commission."""
    from diwan.agents import finance
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props.get("result") != "received" or t.props.get("agent") not in ("pay", "inv"):
        raise KeyError(tid)
    d = g.nodes[f"deal:{t.deal}"].props
    ref = re.sub(r"^(Received|Paid into .*?), (reference|receipt) ", "", t.props.get("reason") or "")
    if t.props["agent"] == "inv":
        what, amount = f"Commission, invoice {t.props.get('invoice')}", t.props.get("amount_aed")
        who = billed_to(g, t.deal, t.props.get("payer") or finance.commission(g, t.deal)["payer"])
    else:
        what, amount = t.props["action"].replace("Expect ", ""), t.props.get("amount_aed") or finance.expected(g, t, date.today()).get("amount_aed")
        who = d["customer"]
        if pays := [p for p in t.props.get("payments", []) if not p.get("held")]:  # what was really seen: the real payer, not the deal's customer
            amount, who = sum(p["amount"] for p in pays), pays[-1].get("payer") or who
            ref = ", ".join(p["reference"] for p in pays)
    blocks = [("title", "Receipt"), ("field", f"Receipt number|RCT-{t.id}"), ("field", f"Date|{date.today().isoformat()}"), ("h", "Received by"), *_agency(g),
              ("h", "Received from"), ("field", f"Name|{who}"), ("h", "For"), ("field", f"Description|{what}"), ("field", f"Property|{d['property']}"),
              ("field", f"Amount|AED {amount:,.2f}" if amount else "Amount|as on the reference"), ("field", f"Reference|{ref or '—'}"),
              ("p", "Recorded by Finance when the money was seen arriving.")]
    return pdf.render(blocks)
