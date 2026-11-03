#!/usr/bin/env python3
"""Browser-level regression for untrusted Tonight URL state and bounded DOM work.

Runs against the checked-in public/ build and a deterministic, intercepted
canonical event payload. No production data or external services are changed.
"""
import functools
import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def fixture():
    start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "events": [
            {
                "id": f"fixture-{index}",
                "title": f"サンプルイベント{index}",
                "start_at": start,
                "category": "VRChat",
                "source": "official",
                "official_url": "https://example.org/event",
            }
            for index in range(350)
        ],
    }


def inspect(page, base, query):
    page.goto(base + query, wait_until="domcontentloaded")
    page.wait_for_function("document.querySelector('#loading')?.hidden === true")
    assert page.locator("#error").is_hidden(), page.locator("#error").inner_text()
    return {
        "url": page.url,
        "cards": page.locator("#list .event-card").count(),
        "summary": page.locator("#summary").inner_text(),
        "query": page.locator("#q").input_value(),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="tonight-url-browser-audit")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(QuietHandler, directory=str(Path("public").resolve()))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/tonight/"
    findings = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                payload = json.dumps(fixture(), ensure_ascii=False)
                page.route("**/events.json", lambda route: route.fulfill(
                    status=200, content_type="application/json", body=payload
                ))
                page.route("https://**", lambda route: route.abort())

                bounded = inspect(page, base, "?range=all&limit=999999990")
                assert bounded["cards"] == 300, bounded
                assert "条件一致 350件" in bounded["summary"], bounded
                findings.append({"case": "valid_huge_limit_clamped", **bounded})

                invalid = inspect(
                    page, base, "?range=all&limit=999999999&category=bogus&source=bogus"
                )
                assert invalid["cards"] == 30, invalid
                assert "limit=" not in invalid["url"], invalid
                assert "category=" not in invalid["url"], invalid
                assert "source=" not in invalid["url"], invalid
                findings.append({"case": "invalid_values_canonicalized", **invalid})

                invalid_range = inspect(page, base, "?range=garbage&limit=Infinity")
                assert "range=" not in invalid_range["url"], invalid_range
                assert "limit=" not in invalid_range["url"], invalid_range
                findings.append({"case": "invalid_range_default", **invalid_range})

                oversized = inspect(page, base, "?range=all&q=" + quote("あ" * 257))
                assert oversized["query"] == "", oversized
                assert "256文字" in oversized["summary"], oversized
                assert "q=" not in oversized["url"], oversized
                findings.append({"case": "oversized_query_rejected", **oversized})

                valid = inspect(
                    page, base,
                    "?range=all&category=VRChat&source=official&q="
                    + quote("サンプルイベント349") + "&limit=90",
                )
                assert valid["cards"] == 1, valid
                assert valid["query"] == "サンプルイベント349", valid
                assert "category=VRChat" in valid["url"], valid
                assert "source=official" in valid["url"], valid
                assert "limit=90" in valid["url"], valid
                findings.append({"case": "valid_japanese_roundtrip", **valid})

                assert not errors, errors
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
    report = {"status": "pass", "fixture_events": 350, "cases": findings}
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "pass", "cases": len(findings)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
