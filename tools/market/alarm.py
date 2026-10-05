"""Which sources need a GitHub issue opened or closed, read from each pack's health.json
(proposal › Keeping it alive): two failed runs in a row open one, a good run closes it."""
from __future__ import annotations

import json
from pathlib import Path

FAILURES_FOR_AN_ISSUE = 2


def alarms(root: Path) -> dict:
    failing, ok = [], []
    for path in sorted(Path(root).glob("*/health.json")):
        pack = path.parent.name
        for source, entry in sorted(json.loads(path.read_text(encoding="utf-8")).items()):
            if source.startswith("_") or not isinstance(entry, dict):
                continue
            if entry.get("ok"):
                ok.append(f"{pack}/{source}")
            elif int(entry.get("failures_in_a_row", 0)) >= FAILURES_FOR_AN_ISSUE:
                failing.append({"name": f"{pack}/{source}", "failures": entry["failures_in_a_row"],
                                "error": str(entry.get("error", ""))[:500], "last_ok": entry.get("last_ok", "never")})
    return {"failing": failing, "ok": ok}
