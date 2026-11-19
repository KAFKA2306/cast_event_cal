from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "canonical-flow.md"


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
