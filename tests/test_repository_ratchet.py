from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "canonical-flow.md"


def test_canonical_flow_contract_exists() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "cast_event_cal` is the canonical repository" in text
    assert "vrc_cast_event_calender` is a projection-only distribution repository" in text
    assert "public/events.json" in text
    assert "public/calendar.ics" in text


def test_ratchet_kpis_are_limited_to_three() -> None:
    text = DOC.read_text(encoding="utf-8")
    expected = {
        "acceptance_precision",
        "publication_freshness",
        "publication_success_rate",
    }
    found = {name for name in expected if f"`{name}`" in text}
    assert found == expected
    assert text.count(" — ") >= 3


def test_obsolete_noncanonical_workflows_are_absent() -> None:
    obsolete = {
        "weekly-repo-research.yml",
        "materialize-yahoo-v19-once.yml",
    }
    workflow_dir = ROOT / ".github" / "workflows"
    present = sorted(name for name in obsolete if (workflow_dir / name).exists())
    assert present == []


def test_delivery_owned_cloudflare_routes_are_absent() -> None:
    assert not (ROOT / "public" / "_routes.json").exists()
    text = DOC.read_text(encoding="utf-8")
    assert "Cloudflare Pages routing such as `_routes.json` is owned by `KAFKA2306/vrc_cast_event_calender`" in text


def test_tracked_backup_files_are_absent() -> None:
    assert list(ROOT.rglob("*.bak")) == []


def test_obsolete_v1_scaffold_is_absent() -> None:
    assert all(not (ROOT / path).exists() for path in ("pipelines", "src", "models", "web_frontend"))
    assert all(not (ROOT / path).exists() for path in ("config/main_config.yaml", "config/scraping_targets.yaml"))
    assert list(ROOT.rglob("*.log")) == []
