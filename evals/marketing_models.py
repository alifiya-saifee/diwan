"""Which model for which Marketing job? The same fixed jobs on each setting, on the fictional demo data (the free endpoint is for fictional data only).
Scored by the code's own checks and by one blind judge, with the time and the estimated cost of each.

    DIWAN_TAPE=off PYTHONPATH=. python evals/marketing_models.py [out.json]
"""
import json
import os
import statistics
import sys
import time
from datetime import timedelta

from diwan import brand, business, config, costs, demo
from diwan.agents import marketing, planner, qa, rhythm, studio
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import meta

SETTINGS = [("Muse Glimmer (free)", "nvidia", "low"), ("Muse Spark, low effort", "meta", "low"), ("Muse Spark, medium effort", "meta", "medium"), ("Muse Spark, high effort", "meta", "high")]
REFS = ["MC-1204", "JVC-88", "K1"]
JUDGE = {"name": "score", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["score", "why"], "properties": {"score": {"type": "integer"}, "why": {"type": "string"}}}}


def office() -> Office:
    o = Office(EventLog())
    demo.seed(o)
    business.save(o, {"industry": "Real estate brokerage", "country": "AE", "posted_before": "yes"}, by="maya")
    brand.save(o, {"name": "Diwan Realty", "positioning": "A Dubai brokerage that tells buyers the whole cost before they commit.", "voice": "warm, straight-talking"}, by="maya")
    return o


def judge(what: str, text: str) -> int | None:
    """Always the same model and effort, and it never sees which setting wrote it."""
    token = config.TRIAL.set({"provider": "meta"})
    try:
        return meta.look(f"You are a demanding head of marketing at a Dubai real-estate brokerage. Score this {what} from 1 to 5: is it specific, natural to say aloud, true to its facts, and would it stop a buyer scrolling? "
                         "Most work is a 3. Give 5 only to work you would publish untouched.", text[:1800], [], JUDGE, agent="mkt")["score"]
    except meta.MetaError:
        return None
    finally:
        config.TRIAL.reset(token)


def spend() -> float:
    return costs.summary()["spend_usd"]


def timed(fn) -> dict:
    t, c = time.time(), spend()
    try:
        out = fn()
        return {"ok": True, "out": out, "seconds": round(time.time() - t, 1), "usd": round(spend() - c, 4)}
    except Exception as e:  # noqa: BLE001  a setting that fails is a result
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}", "seconds": round(time.time() - t, 1), "usd": round(spend() - c, 4)}


def jobs(o: Office) -> dict:
    res: dict = {}
    idea = {"id": None, "pick": {"title": "The whole cost, before you commit", "cards": []}}

    def sc(ref):
        s = studio.script(o, ref, idea, None, None, None, angle="walkthrough", why="test")
        return {"s": s, "fails": [f["check"] for f in qa.review(o, "script", ref, s, cause=None, attempt=1)], "via": s.get("via")}

    res["script"] = [timed(lambda r=r: sc(r)) for r in REFS]
    res["idea"] = [timed(lambda r=r: studio.ideas(o, r, [], None)) for r in REFS[:2]]

    def plan():
        today = marketing._today(o)
        days = [{"date": (today + timedelta(days=i)).isoformat(), "ref": None, "why": "", "type": "listing", "status": "pending"} for i in range(5)]
        got, by = planner.choose(o, days, today, set())
        return {"days": [d.get("ref") for d in got], "whys": [d.get("why") for d in got], "by": by}

    res["plan"] = [timed(plan)]

    def caption():
        sc_ = studio.script(o, "MC-1204", idea, None, None, None, angle="lifestyle", why="test")
        old = studio.post_text(o, "MC-1204", sc_, None)
        new = studio.rewrite_caption(o, "MC-1204", "Make it shorter, one idea only", None)
        return {"old": len(old["text"]), "new": len(new["text"]), "kept_code": (old.get("code") or "") in new["text"], "text": new["text"]}

    res["caption"] = [timed(caption)]
    return res


def score(res: dict) -> dict:
    rows = {}
    for job, runs in res.items():
        ok = [r for r in runs if r["ok"]]
        quality = []
        for r in ok:
            o_ = r["out"]
            if job == "script":
                r["score"] = judge("video script", " / ".join([o_["s"]["hook_en"], *o_["s"]["lines_en"]])) if "template" not in str(o_["via"]) else 1
            elif job == "idea":
                r["score"] = judge("post idea", json.dumps(o_.get("pick"), ensure_ascii=False)) if o_.get("via") != "rules" else 1
            elif job == "plan":
                r["score"] = judge("week of posts and the reason for each", json.dumps(o_, ensure_ascii=False)) if o_["by"] != "rules" else 1
            else:
                r["score"] = judge("shortened post caption", o_["text"]) if o_["new"] < o_["old"] and o_["kept_code"] else 1
            if r["score"]:
                quality.append(r["score"])
        rows[job] = {"quality": round(statistics.mean(quality), 1) if quality else None, "worked": f"{len(ok)} of {len(runs)}", "seconds": round(statistics.mean(r["seconds"] for r in runs), 1),
                     "usd": round(sum(r["usd"] for r in runs) / len(runs), 4), "check_fails": sum(len(r["out"]["fails"]) for r in ok) if job == "script" else None,
                     "errors": [r["error"] for r in runs if not r["ok"]][:1]}
    return rows


def main() -> None:
    out = {}
    start = spend()
    for name, provider, effort in [x for x in SETTINGS if os.environ.get("ONLY", "") in x[0]]:
        os.environ["DIWAN_REASONING"] = effort
        token = config.TRIAL.set({"provider": provider})
        try:
            res = jobs(office())
        finally:
            config.TRIAL.reset(token)
        os.environ["DIWAN_REASONING"] = "low"
        out[name] = {"rows": score(res), "samples": {"script": next((" / ".join([r["out"]["s"]["hook_en"], *r["out"]["s"]["lines_en"][:2]]) for r in res["script"] if r["ok"]), "")}}
        print(name, json.dumps(out[name]["rows"]), flush=True)
    out["total_usd"] = round(spend() - start, 3)
    print("TOTAL", out["total_usd"])
    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    rhythm  # keeps the import order the app uses
    main()
