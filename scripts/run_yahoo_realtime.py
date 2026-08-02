from __future__ import annotations

import re

from scripts import fetch_yahoo_realtime as implementation


def configure() -> None:
    # Python's Unicode word boundary does not exist between "VRC" and Japanese
    # characters because both are word characters. Reject only continuations by
    # Latin letters, so VRCイベント / VRC初心者 / VRC2年 remain detectable.
    implementation.VRCHAT_RE = re.compile(r"(?:#?vrchat|#?vrc)(?![a-z])", re.IGNORECASE)
    implementation.PARSER_VERSION = "1.3"


def main() -> int:
    configure()
    return implementation.main()


if __name__ == "__main__":
    raise SystemExit(main())
