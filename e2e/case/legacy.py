"""The older browser checks (off-plan, rental, every deal desk path, the calendar, calls, the front door), forced into the visible window: python e2e/case/legacy.py <flow.py> <base> <out dir>"""
import runpy
import sys
from pathlib import Path

from playwright.sync_api import BrowserType

real = BrowserType.launch


def seen(self, **k):
    k.update(headless=False, channel="msedge")
    k.setdefault("slow_mo", 100)
    return real(self, **k)


BrowserType.launch = seen
flow = sys.argv[1]
sys.argv = [flow] + sys.argv[2:]
runpy.run_path(str(Path(__file__).parents[1] / flow), run_name="__main__")
