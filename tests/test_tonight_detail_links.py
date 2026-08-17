from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "public"


class TonightDetailLinkContractTest(unittest.TestCase):
    def test_template_loads_analytics_and_has_stable_detail_action(self) -> None:
        html = (ROOT / "tonight/index.html").read_text(encoding="utf-8")
        self.assertIn('src="../analytics.js" data-config="../analytics-config.json"', html)
        self.assertIn('class="action detail">詳細</a>', html)

    def test_js_fails_closed_using_canonical_indexability_fields(self) -> None:
        js = (ROOT / "tonight/tonight.js").read_text(encoding="utf-8")
        for token in (
            "generated_at",
            "canonical_name",
            "starts_at",
            "ends_at",
            "primary_action_url",
            "official_links",
            "review_required===true",
            "/^[A-Za-z0-9._-]{1,128}$/",
            "hasDetail(e)",
            "../events/${encodeURIComponent(stableId)}/",
            "event_detail_open",
        ):
            self.assertIn(token, js)


if __name__ == "__main__":
    unittest.main()
