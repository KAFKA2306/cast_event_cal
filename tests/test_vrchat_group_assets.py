import json
import subprocess
import sys
from pathlib import Path

from scripts.enrich_vrchat_group_assets import extract_group_image, group_url


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "enrich_vrchat_group_assets.py"


def test_extract_group_image_from_open_graph_metadata() -> None:
    page = '<html><head><meta property="og:image" content="https://assets.vrchat.com/group.jpg"></head></html>'
    assert extract_group_image(page) == "https://assets.vrchat.com/group.jpg"


def test_extract_group_image_accepts_reversed_attribute_order() -> None:
    page = '<meta content="https://assets.vrchat.com/group.webp" name="twitter:image">'
    assert extract_group_image(page) == "https://assets.vrchat.com/group.webp"


def test_group_url_prefers_official_vrchat_group_link() -> None:
    event = {
        "url": "https://x.com/example/status/123",
        "official_links": [
            {
                "url": "https://vrchat.com/home/group/grp_db9d6929-5d48-4047-8aea-36d560bcec26",
                "kind": "vrchat_group",
            }
        ],
    }
    assert group_url(event) == "https://vrchat.com/home/group/grp_db9d6929-5d48-4047-8aea-36d560bcec26"


def test_direct_script_execution_matches_production_entrypoint(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir()
    (public / "events.json").write_text(json.dumps({"events": []}) + "\n", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    audit = json.loads((public / "image-reachability-audit.json").read_text(encoding="utf-8"))
    assert audit["checked_url_count"] == 0
    groups = json.loads((public / "vrchat-group-asset-audit.json").read_text(encoding="utf-8"))
    assert groups["image_reachability"]["checked_url_count"] == 0
