"""Look at a chat in the scratch office: python e2e/case/peek.py <base> <phone>"""
import json
import sys

import httpx

base, phone = sys.argv[1], sys.argv[2]
c = httpx.Client(base_url=base, timeout=30)
c.post("/api/auth/login", json={"person": "layla", "password": "a good password"})
d = c.get(f"/api/chats/{phone}").json()
print("stage", d.get("stage"), "broker", d.get("broker"), "deal", d.get("deal"))
print("qualify", json.dumps(d.get("qualify"), ensure_ascii=False)[:1500])
print("facts", [(f["id"], f["kind"], f["text"][:80]) for f in d["facts"]])
print("cards", [(x["id"], x["text"][:170], x["who"]) for x in d["cards"]])
print("tasks", [t["text"][:90] for t in d["tasks"]])
print("spend", c.get("/api/case/spend").json())
