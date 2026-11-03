#!/usr/bin/env python3
"""Audit browser capabilities without changing production headers."""
from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config/browser-security-policy.json"
SURFACES = (ROOT / "web/index.template.html",)
ORIGIN_RE = re.compile(r"https://[^\s\"'<>`)]+")


class _ActiveBlockCounter(HTMLParser):
    """Count executable inline scripts separately from external and data scripts."""

    def __init__(self) -> None:
        super().__init__()
        self.inline_scripts = 0
        self.external_scripts = 0
        self.inline_styles = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "style":
            self.inline_styles += 1
        elif tag == "script":
            if attributes.get("src"):
                self.external_scripts += 1
            else:
                script_type = (attributes.get("type") or "").split(";", 1)[0].strip().lower()
                if script_type in {"", "module", "text/javascript", "application/javascript"}:
                    self.inline_scripts += 1


def inventory(text: str) -> dict[str, object]:
    origins = sorted({m.group(0).split('/', 3)[2] for m in ORIGIN_RE.finditer(text)})
    counter = _ActiveBlockCounter()
    counter.feed(text)
    return {
        "origins": origins,
        "inline_script_blocks": counter.inline_scripts,
        "external_script_blocks": counter.external_scripts,
        "inline_style_blocks": counter.inline_styles,
        "eval_calls": len(re.findall(r"\beval\s*\(", text)),
        "dynamic_script_injection": bool(re.search(r"createElement\s*\(\s*['\"]script['\"]", text)),
    }

def audit_policy(policy: dict[str, object]) -> list[str]:
    errors: list[str] = []
    directives = policy.get("directives", {})
    forbidden = set(policy.get("forbidden_tokens", []))
    for name, values in directives.items():
        bad = forbidden.intersection(values)
        if bad:
            errors.append(f"{name} contains forbidden tokens: {sorted(bad)}")
    required_headers = {"Referrer-Policy", "X-Content-Type-Options", "Permissions-Policy"}
    missing = required_headers - set(policy.get("headers", {}))
    if missing:
        errors.append(f"missing headers: {sorted(missing)}")
    if directives.get("frame-ancestors") != ["'none'"]:
        errors.append("frame-ancestors must deny framing in the audit candidate")
    return errors


def read_headers(url: str) -> dict[str, str]:
    request = Request(url, method="HEAD", headers={"User-Agent": "cast-event-cal-security-audit/1"})
    with urlopen(request, timeout=15) as response:
        wanted = ("content-security-policy", "referrer-policy", "x-content-type-options", "permissions-policy")
        observed = {k.lower(): v for k, v in response.headers.items()}
        return {name: observed.get(name, "missing") for name in wanted}


def build_report(production_url: str | None = None) -> dict[str, object]:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    surfaces = {}
    for path in SURFACES:
        surfaces[str(path.relative_to(ROOT))] = inventory(path.read_text(encoding="utf-8"))
    report: dict[str, object] = {
        "policy_version": policy["version"],
        "mode": policy["mode"],
        "policy_errors": audit_policy(policy),
        "surfaces": surfaces,
    }
    if production_url:
        report["production"] = {"url": production_url, "headers": read_headers(production_url)}
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report(args.production_url)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.check and report["policy_errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
