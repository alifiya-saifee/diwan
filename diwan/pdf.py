"""A plain-text PDF, enough for a form to print, sign and scan: A4 pages, the standard Helvetica fonts (nothing
embedded, nothing installed), lines wrapped to the page. Text outside Latin-1 is replaced, never dropped silently.
"""
from __future__ import annotations

import textwrap

W, H, MARGIN = 595, 842, 56


def _esc(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    s = s.encode("latin-1", "replace").decode("latin-1")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render(blocks: list[tuple[str, str]]) -> bytes:
    """blocks: (style, text) with style "title", "h" (a heading), "p" (a paragraph), "field" ("Label|value") or "gap"."""
    rows: list[tuple[int, list[tuple[str, int, str, int]]]] = []  # (height, runs of (font, size, text, x)) on one baseline
    for style, text in blocks:
        if style == "title":
            rows += [(20, [("F2", 15, t, MARGIN)]) for t in textwrap.wrap(text, 58)] + [(8, [])]
        elif style == "h":
            rows += [(10, []), (16, [("F2", 11, text, MARGIN)])]
        elif style == "p":
            rows += [(13, [("F1", 9, t, MARGIN)]) for t in textwrap.wrap(text, 100)]
        elif style == "field":
            label, _, value = text.partition("|")
            vals = textwrap.wrap(value, 62) or [""]
            rows.append((16, [("F2", 10, label, MARGIN), ("F1", 10, vals[0], MARGIN + 170)]))
            rows += [(14, [("F1", 10, v, MARGIN + 170)]) for v in vals[1:]]
        elif style == "gap":
            rows.append((18, []))
    pages, page, y = [], [], H - MARGIN
    for height, runs in rows:
        if y - height < MARGIN:
            pages.append(page)
            page, y = [], H - MARGIN
        y -= height
        page += [(f, sz, t, x, y) for f, sz, t, x in runs]
    pages.append(page)

    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>"]
    kids = []
    for n, pg in enumerate(pages, 1):
        body = "".join(f"BT /{f} {s} Tf {x} {y} Td ({_esc(t)}) Tj ET\n" for f, s, t, x, y in pg if t)
        body += f"BT /F1 8 Tf {MARGIN} 30 Td (Page {n} of {len(pages)}) Tj ET\n"
        objs.append(f"<< /Length {len(body.encode('latin-1'))} >>\nstream\n{body}endstream")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {W} {H}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {len(objs)} 0 R >>")
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out
