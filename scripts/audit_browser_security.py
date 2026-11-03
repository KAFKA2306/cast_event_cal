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
REQUIRED_SURFACES = (
    "web/index.template.html",
    "public/index.html",
    "public/tonight/index.html",
)
REPRESENTATIVE_GROUPS = ("events", "categories", "series")


def select_surfaces(root: Path) -> tuple[list[Path], list[str]]:
    """Inspect generated entry points plus one deterministic page per family."""
    candidates = [root / relative for relative in REQUIRED_SURFACES]
    missing = []
    for family in REPRESENTATIVE_GROUPS:
        sample = next(iter(sorted((root / "public" / family).glob("*/index.html"))), None)
        if sample is None:
            missing.append(f"public/{family}/*/index.html")
        else:
            candidates.append(sample)
    existing = [path for path in candidates if path.is_file()]
    missing.extend(str(path.relative_to(root)) for path in candidates if not path.is_file())
    return existing, missing
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


PRODUCTION_HEADERS = (
    "content-security-policy",
    "content-security-policy-report-only",
    "referrer-policy",
    "x-content-type-options",
    "permissions-policy",
    "x-frame-options",
)


def policy_directive_errors(policies: list[str]) -> list[str]:
    """Identify duplicate directives and contradictory 'none' source lists."""
    errors: list[str] = []
    for index, policy in enumerate(policies, start=1):
        seen: set[str] = set()
        for clause in policy.split(";"):
            parts = clause.strip().split()
            if not parts:
                continue
            directive, *sources = parts
            directive = directive.lower()
            if directive in seen:
                errors.append(f"CSP #{index}: duplicate directive {directive}")
            seen.add(directive)
            if "'none'" in sources and len(sources) > 1:
                errors.append(f"CSP #{index}: {directive} combines 'none' with other sources")
    return errors


def read_production_response(url: str) -> dict[str, object]:
    """Inspect the final GET response, not an intermediate redirect or HEAD."""
    request = Request(url, method="GET", headers={"User-Agent": "cast-event-cal-security-audit/1"})
    with urlopen(request, timeout=15) as response:
        observed: dict[str, list[str]] = {}
        for name in PRODUCTION_HEADERS:
            if hasattr(response.headers, "get_all"):
                values = response.headers.get_all(name) or []
            else:
                values = [value for key, value in response.headers.items() if key.lower() == name]
            observed[name] = values
        headers: dict[str, str | list[str]] = {
            name: values[0] if len(values) == 1 else values if values else "missing"
            for name, values in observed.items()
        }
        errors = policy_directive_errors(observed["content-security-policy"])
        errors.extend(policy_directive_errors(observed["content-security-policy-report-only"]))
        duplicates = {name: len(values) for name, values in observed.items() if len(values) > 1}
        return {
            "requested_url": url,
            "final_url": response.geturl() if hasattr(response, "geturl") else url,
            "status": getattr(response, "status", None),
            "headers": headers,
            "duplicate_header_counts": duplicates,
            "policy_errors": errors,
        }


def read_headers(url: str) -> dict[str, str | list[str]]:
    """Backward-compatible header-only view of the final response."""
    return read_production_response(url)["headers"]


def build_report(production_url: str | list[str] | None = None) -> dict[str, object]:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    surfaces = {}
    selected, missing = select_surfaces(ROOT)
    for path in selected:
        surfaces[str(path.relative_to(ROOT))] = inventory(path.read_text(encoding="utf-8"))
    report: dict[str, object] = {
        "policy_version": policy["version"],
        "mode": policy["mode"],
        "policy_errors": audit_policy(policy),
        "missing_surfaces": missing,
        "surfaces": surfaces,
    }
    if production_url:
        urls = [production_url] if isinstance(production_url, str) else production_url
        report["production"] = [read_production_response(url) for url in urls]
    return report


def check_report(report: dict[str, object]) -> list[str]:
    """Fail on malformed policies, but keep missing headers audit-only."""
    errors = list(report["policy_errors"])
    errors.extend(f"missing audit surface: {path}" for path in report.get("missing_surfaces", []))
    for entry in report.get("production", []):
        for error in entry["policy_errors"]:
            errors.append(f"{entry['final_url']}: {error}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-url", action="append", help="Repeat for home, Tonight, and an event detail URL")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report(args.production_url)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.check and check_report(report):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
