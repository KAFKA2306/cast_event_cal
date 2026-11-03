#!/usr/bin/env python3
"""Read-only Chromium audit of the generated Tonight navigation.

Run: python scripts/audit_mobile_navigation.py --output-dir mobile-audit
Requires: pip install playwright && python -m playwright install chromium
The default is report-only; --strict fails when navigation invariants fail.
"""
import argparse
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

WIDTHS = (320, 360, 390, 430, 768)
EXPECTED = ("絞り込み", "今夜", "カレンダー購読", "データ監査")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def inspect(page, width, zoom):
    page.set_viewport_size({"width": width, "height": 844})
    page.goto(page.audit_url, wait_until="domcontentloaded")
    page.locator("header nav a").first.wait_for()
    if zoom != 1:
        # Text-only scaling proxy: preserve layout dimensions and enlarge computed
        # font sizes, unlike CSS zoom which magnifies every box and control.
        page.evaluate("""(factor) => {
          const elements = Array.from(document.querySelectorAll('*'));
          const sizes = elements.map(el => [el, parseFloat(getComputedStyle(el).fontSize)]);
          for (const [el, size] of sizes) {
            if (Number.isFinite(size) && size > 0) {
              el.style.setProperty('font-size', String(size * factor) + 'px', 'important');
            }
          }
        }""", zoom)
    return page.evaluate("""() => {
      const links = Array.from(document.querySelectorAll('header nav a'));
      const viewport = window.innerWidth;
      const rect = el => {
        const r = el.getBoundingClientRect();
        return { left: r.left, right: r.right, width: r.width, height: r.height };
      };
      const items = links.map(el => {
        const r = rect(el);
        return {
          text: el.textContent.trim(),
          href: el.getAttribute('href'),
          initially_visible: r.left >= -1 && r.right <= viewport + 1,
          touch_target_44: r.width >= 44 && r.height >= 44,
          rect: r
        };
      });
      return {
        viewport, document_width: document.documentElement.scrollWidth,
        horizontal_overflow: document.documentElement.scrollWidth > viewport + 1,
        nav_scroll_width: document.querySelector('header nav')?.scrollWidth,
        nav_client_width: document.querySelector('header nav')?.clientWidth,
        links: items
      };
    }""")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="mobile-audit")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(QuietHandler, directory=str(Path("public").resolve()))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/tonight/"
    results = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.audit_url = url
                for width in WIDTHS:
                    for zoom in (1, 2) if width in (320, 390) else (1,):
                        result = inspect(page, width, zoom)
                        result["text_only_zoom_proxy"] = zoom != 1
                        result["requested_width"] = width
                        result["text_zoom_factor"] = zoom
                        result["expected_links"] = list(EXPECTED)
                        result["labels_match"] = [x["text"] for x in result["links"]] == list(EXPECTED)
                        result["all_initially_visible"] = all(x["initially_visible"] for x in result["links"])
                        result["all_touch_targets_44"] = all(x["touch_target_44"] for x in result["links"])
                        result["keyboard_focusable"] = []
                        for index in range(len(result["links"])):
                            link = page.locator("header nav a").nth(index)
                            link.focus()
                            result["keyboard_focusable"].append(link.evaluate("(el) => document.activeElement === el"))
                        result["pass"] = (
                            result["labels_match"] and result["all_initially_visible"]
                            and result["all_touch_targets_44"] and all(result["keyboard_focusable"])
                            and not result["horizontal_overflow"]
                        )
                        page.screenshot(path=str(output / f"tonight-{width}-zoom{zoom}.png"), full_page=True)
                        results.append(result)
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
    summary = {"scope": "generated public/tonight/ navigation only", "mode": "read-only",
               "zoom_note": "Computed font-size scaling proxy; not native browser text-only zoom",
               "status": "pass" if all(x["pass"] for x in results) else "findings",
               "results": results}
    (output / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": summary["status"], "cases": len(results),
                      "failed": [f"{x['requested_width']}px text{x['text_zoom_factor']}x" for x in results if not x["pass"]]},
                     ensure_ascii=False))
    if args.strict and summary["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
