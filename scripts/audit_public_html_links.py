from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


class PublicAnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value is not None:
                self.hrefs.append(value)


def is_unsafe_external_href(raw: str) -> bool:
    """Audit static HTML links; relative first-party navigation is allowed."""
    value = raw.strip()
    if not value:
        return False
    # Browsers may normalize controls and backslashes into navigation targets.
    if any(ord(char) < 32 or ord(char) == 127 for char in raw):
        return True
    if "\\" in value or value.startswith("//"):
        return True
    try:
        parsed = urlsplit(value)
        if not parsed.scheme and not parsed.netloc:
            return False
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            return True
        if "@" in parsed.netloc or any(char.isspace() for char in parsed.netloc):
            return True
        _ = parsed.port  # malformed ports must fail closed
    except ValueError:
        return True
    return False


def audit_html(path: Path) -> list[str]:
    parser = PublicAnchorParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return [
        f"{path}: unsafe href {href!r}"
        for href in parser.hrefs
        if is_unsafe_external_href(href)
    ]


def audit_public_html(root: Path) -> list[str]:
    failures: list[str] = []
    for path in sorted(root.rglob("*.html")):
        failures.extend(audit_html(path))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit public HTML hrefs without network access"
    )
    parser.add_argument("root", nargs="?", type=Path, default=Path("public"))
    args = parser.parse_args()
    failures = audit_public_html(args.root)
    if failures:
        print("Unsafe public HTML navigation targets:")
        print("\n".join(failures))
        return 1
    print("Public HTML link audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
