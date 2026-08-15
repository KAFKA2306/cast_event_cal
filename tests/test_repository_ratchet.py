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


def test_yahoo_best_1000_is_read_only_benchmark() -> None:
    workflow = (ROOT / ".github" / "workflows" / "yahoo-best-1000.yml").read_text(encoding="utf-8")
    assert "name: Yahoo best 1000 benchmark" in workflow
    assert "contents: read" in workflow
    assert "--no-update-production" in workflow
    assert "push:" not in workflow
    assert "git push" not in workflow
    assert "Commit empirical result and production ledger" not in workflow
