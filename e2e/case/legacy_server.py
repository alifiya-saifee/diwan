"""The older browser checks predate "the agent confirms a viewing": this serves them the rule they were written for, offline, with sign-in off. Only ever used by e2e/case.

    python e2e/case/legacy_server.py 8041 <folder>
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
folder = Path(sys.argv[2])
folder.mkdir(parents=True, exist_ok=True)
os.environ.update(DIWAN_AUTH="off", DIWAN_OFFLINE="1", DIWAN_TAPE="off", DIWAN_LOCAL_ASR="0", DIWAN_REPLY_WAIT="0", DIWAN_DB=str(folder / "legacy.db"), DIWAN_MEDIA=str(folder / "media"))

import uvicorn  # noqa: E402

from diwan.agents import reception  # noqa: E402

reception.agent_confirms = lambda g: False
from diwan import app as A  # noqa: E402

uvicorn.run(A.app, host="127.0.0.1", port=int(sys.argv[1]), log_level="warning")
