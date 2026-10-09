from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "public" / "tonight" / "tonight.js"


def test_tonight_preserves_last_valid_snapshot_for_transient_fetch_failure():
    source = JS.read_text(encoding="utf-8")

    assert "CACHE_KEY='vrc-tonight-last-valid-v1'" in source
    assert "cacheSnapshot(data)" in source
    assert "const cached=cachedSnapshot()" in source
    assert "保存済みイベント" in source
    assert "前回の正常データ" in source
    assert "公式情報で開催状況を確認" in source


def test_invalid_or_empty_network_snapshot_is_not_cached():
    source = JS.read_text(encoding="utf-8")

    snapshot_pos = source.index("snap=snapshot(data)")
    cache_pos = source.index("cacheSnapshot(data)", snapshot_pos)
    apply_pos = source.index("applySnapshot(snap)", cache_pos)
    assert snapshot_pos < cache_pos < apply_pos
