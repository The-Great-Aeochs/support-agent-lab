import json
from pathlib import Path

SUPPORT_DATA = json.loads(Path(__file__).with_name("support_data.json").read_text(encoding="utf-8"))
TICKETS = SUPPORT_DATA["tickets"]
RUNBOOKS = SUPPORT_DATA["runbooks"]
