from __future__ import annotations

import argparse
import re
from pathlib import Path

SKIP_LINK = '<a class="skip-link" href="#main-content">本文へスキップ</a>'
ACCESSIBILITY_CSS = """
.skip-link{position:fixed;left:12px;top:12px;z-index:1000;transform:translateY(-160%);padding:10px 14px;border-radius:10px;background:var(--ink);color:#fff;font-weight:800;text-decoration:none}
.skip-link:focus{transform:translateY(0)}
:where(a,button,input,select,summary):focus-visible{outline:3px solid #1f6feb;outline-offset:3px}
#main-content:focus{outline:none}
""".strip()
MAIN_RE = re.compile(r"<main\b(?P<attrs>[^>]*)>", re.IGNORECASE)


def _set_attribute(attrs: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(?P<prefix>\s){re.escape(name)}\s*=\s*(?P<quote>['\"])(?P<value>.*?)(?P=quote)", re.IGNORECASE)
    match = pattern.search(attrs)
    if match:
        return attrs[: match.start("value")] + value + attrs[match.end("value") :]
    return attrs + f' {name}="{value}"'


def _enforce_main_landmark(text: str) -> str:
    matches = list(MAIN_RE.finditer(text))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one main landmark, found {len(matches)}")
    match = matches[0]
    attrs = _set_attribute(match.group("attrs"), "id", "main-content")
    attrs = _set_attribute(attrs, "tabindex", "-1")
    replacement = f"<main{attrs}>"
    return text[: match.start()] + replacement + text[match.end() :]


def enforce(text: str) -> str:
    if SKIP_LINK not in text:
        if "<body>" not in text:
            raise ValueError("body marker missing")
        text = text.replace("<body>", f"<body>\n{SKIP_LINK}", 1)
    text = _enforce_main_landmark(text)
    if ACCESSIBILITY_CSS not in text:
        if "</style>" not in text:
            raise ValueError("style marker missing")
        text = text.replace("</style>", ACCESSIBILITY_CSS + "\n</style>", 1)
    return text


def verify(text: str) -> None:
    main_matches = list(MAIN_RE.finditer(text))
    valid_main = 0
    for match in main_matches:
        attrs = match.group("attrs")
        has_id = re.search(r"\sid\s*=\s*(['\"])main-content\1", attrs, re.IGNORECASE)
        has_tabindex = re.search(r"\stabindex\s*=\s*(['\"])-1\1", attrs, re.IGNORECASE)
        if has_id and has_tabindex:
            valid_main += 1
    if len(main_matches) != 1 or valid_main != 1:
        raise ValueError("accessibility contract requires exactly one main#main-content[tabindex=-1]")
    if text.count(SKIP_LINK) != 1:
        raise ValueError("accessibility contract requires exactly one skip link")
    required = (
        ":where(a,button,input,select,summary):focus-visible",
        ".skip-link:focus",
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise ValueError(f"accessibility contract missing: {missing}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enforce keyboard navigation invariants on the generated home page")
    parser.add_argument("path", nargs="?", default="public/index.html")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = Path(args.path)
    text = path.read_text(encoding="utf-8")
    if args.check:
        verify(text)
        return
    rendered = enforce(text)
    verify(rendered)
    path.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
