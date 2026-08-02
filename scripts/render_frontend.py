from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cast_event_cal.ontology import main as enrich_event_ontology

TEMPLATE = Path("web/index.template.html")
EVENTS = Path("public/events.json")
OUTPUT = Path("public/index.html")


def main() -> int:
    enrich_event_ontology()
    payload = json.loads(EVENTS.read_text(encoding="utf-8"))
    generated_at = str(payload.get("generated_at") or "")
    html = TEMPLATE.read_text(encoding="utf-8").replace("{{GENERATED_AT}}", generated_at)
    if "VRChat Event Calendar" not in html or 'id="agenda"' not in html:
        raise ValueError("frontend template validation failed")
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"rendered {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
