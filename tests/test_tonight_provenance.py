import json
from pathlib import Path

import pytest

from scripts.build_tonight_provenance import build
from scripts.verify_tonight_provenance import verify

SHA_A = "a" * 40
SHA_B = "b" * 40


def write_artifact(root: Path, commit: str) -> None:
    root.mkdir()
    (root / "index.html").write_text('<link rel="publication-provenance" href="./provenance.json">', encoding="utf-8")
    (root / "kafka-signal.js").write_text("fetch('./provenance.json')", encoding="utf-8")
    (root / "provenance.json").write_text(json.dumps(build(commit, production=True)), encoding="utf-8")


def test_fixture_revision_is_single_authority(tmp_path: Path) -> None:
    root = tmp_path / "tonight"
    write_artifact(root, SHA_A)
    verify(root, production=True)
    (root / "provenance.json").write_text(json.dumps(build(SHA_B, production=True)), encoding="utf-8")
    verify(root, production=True)
    assert SHA_A not in (root / "provenance.json").read_text(encoding="utf-8")


def test_verifier_rejects_hand_maintained_revision(tmp_path: Path) -> None:
    root = tmp_path / "tonight"
    write_artifact(root, SHA_A)
    (root / "kafka-signal.js").write_text(f"const commit = '{SHA_B}';", encoding="utf-8")
    with pytest.raises(ValueError, match="hand-maintained"):
        verify(root, production=True)


def test_production_rejects_unresolved_revision() -> None:
    with pytest.raises(ValueError, match="resolved"):
        build("LOCAL", production=True)
    assert build("LOCAL", production=False)["verified"] is False
