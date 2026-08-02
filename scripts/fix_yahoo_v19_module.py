from pathlib import Path

path = Path("scripts/yahoo_classifier_v19.py")
text = path.read_text(encoding="utf-8")
if "def strong_occurrence" not in text or "def allow_inferred_datetime" not in text:
    raise RuntimeError("final v1.9 classifier safeguards are missing")
path.write_text(text, encoding="utf-8")

test_path = Path("tests/test_yahoo_selection_policy.py")
test_text = test_path.read_text(encoding="utf-8")n