from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "web" / "index.template.html"


def template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_template_preserves_accessible_grouping_contract() -> None:
    source = template_text()
    assert '<div class="chips" role="group" aria-label="期間">' in source
    assert '<div id="agenda" class="agenda" aria-live="polite"></div>' in source
    assert '<section id="agenda"' not in source


def test_template_preserves_browser_quality_fixes() -> None:
    source = template_text()
    assert '<link rel="icon" href="data:,">' in source
    assert '.detail b{display:block;color:#52627a;' in source
    assert '.detail b{display:block;color:var(--muted);' not in source


def test_template_exposes_datetime_provenance_without_changing_default_future_view() -> None:
    source = template_text()
    assert 'id="metric-evidence"' in source
    assert "日時根拠あり" in source
    assert "date_resolution_method" in source
    assert "date_resolution_evidence?.matched_text" in source
    assert "['日時根拠',datetimeEvidence]" in source
    assert "new Date(event.starts_at)>=now" in source
