from __future__ import annotations

import os
from urllib.parse import urlsplit

DEFAULT_PUBLIC_ORIGIN = "https://vrc-cast-event-calender.pages.dev"
ENV_NAME = "CAST_EVENT_CAL_PUBLIC_ORIGIN"


def public_origin() -> str:
    raw = os.environ.get(ENV_NAME, DEFAULT_PUBLIC_ORIGIN).strip().rstrip("/")
    parsed = urlsplit(raw)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"}:
        raise ValueError(f"{ENV_NAME} must be an HTTPS origin without a path")
    return raw
