from __future__ import annotations

import argparse
from pathlib import Path

SKIP_LINK = '<a class="skip-link" href="#main-content">本文へスキップ</a>'
MAIN_TARGET = '<main id="main-content" class="shell" tabindex="-1">'
ACCESSIBILITY_CSS = """
.skip-link{position:fixed;left:12px;top:12px;z-index:1000;transform:translateY(-160%);padding:10px 14px;border-radius:10px;background:var(--ink);color:#fff;font-weight:800;text-decoration:none}
.skip-link:focus{transform:translateY(0)}
:where(a,button,input,select,summary):focus-visible{outline:3px solid #1f6feb;outline-offset:3px}
#main-content:focus{outline:none}
""".strip()


def enforce(text: str) -> str:
    if SKIP_LINK not in text:
        if "<body>" not in text:
            raise ValueError("body marker missing")
        text = text.replace("<body>", f"<body>\n{SKIP_LINK}", 1)
    if MAIN_TARGET not in text:
        marker = '<main class="shell">'
        if marker not in text:
            raise ValueError("main shell marker missing")
        text = text.replace(marker, MAIN_TARGET, 1)
    if ACCESSIBILITY_CSS not in text:
        if "</style>" not in text:
            raise ValueError("style marker missing")
        text = text.replace("</style>", ACCESSIBILITY_CSS + "\n</style>", 1)
    return text


def verify(text: str) -> None:
    required = (
        SKIP_LINK,
        MAIN_TARGET,
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
