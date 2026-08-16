from __future__ import annotations

import argparse
import html
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from scripts.render_search_pages import BASE_URL, SAFE_ID, event_title, format_jst, indexable, parse_time


KIND_LABELS = {
    "registration": "応募・登録",
    "entry": "応募・登録",
    "participation": "参加方法",
    "join": "参加方法",
    "group": "グループ",
    "announcement": "公式告知",
    "official": "公式情報",
}


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def action_kind_label(value: object) -> str:
    kind = str(value or "official").lower()
    for token, label in KIND_LABELS.items():
        if token in kind:
            return label
    return "公式情報"


def category_title(label: str) -> str:
    return f"VRChat {label}イベント一覧 | VRChatイベントカレンダー"


def render_category_page(
    category_id: str,
    label: str,
    events: list[dict[str, object]],
    base_url: str,
) -> str:
    canonical = f"{base_url}/categories/{category_id}/"
    count = len(events)
    description = f"現在・今後開催予定のVRChat {label}イベントを{count}件掲載。開催日時と公式・参加情報を確認できます。"
    kinds = Counter(action_kind_label(event.get("primary_action_kind")) for event in events)
    kind_summary = "、".join(f"{name} {value}件" for name, value in kinds.most_common())
    items = "".join(
        '<li><a href="../../events/{id}/" data-track="event_detail_open" data-event-id="{id}" '
        'data-category="{category}">{title}</a><span>{date}</span></li>'.format(
            id=esc(event["id"]),
            category=esc(category_id),
            title=esc(event_title(event)),
            date=esc(format_jst(event.get("starts_at"))),
        )
        for event in events
    )
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(category_title(label))}</title>
<meta name="description" content="{esc(description)}">
<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:locale" content="ja_JP">
<meta property="og:site_name" content="VRChatイベントカレンダー">
<meta property="og:title" content="{esc(category_title(label))}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta name="twitter:card" content="summary">
<style>
:root{{--bg:#fbfaf7;--surface:#fff;--ink:#243653;--muted:#66758d;--line:#dfe6ef}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Noto Sans JP",sans-serif}}main{{width:min(900px,100%);margin:auto;padding:28px 18px 64px}}a{{color:inherit}}nav{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:28px}}nav a{{font-weight:700}}.eyebrow{{font-size:.78rem;font-weight:800;letter-spacing:.1em;color:#58729a}}h1{{font-size:clamp(1.9rem,6vw,3.4rem);line-height:1.08;letter-spacing:-.035em;margin:.5rem 0 1rem}}.summary{{line-height:1.8;color:var(--muted)}}.facts{{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}}.fact{{padding:10px 14px;border:1px solid var(--line);border-radius:999px;background:var(--surface)}}ul{{list-style:none;padding:0;margin:30px 0 0}}li{{display:flex;justify-content:space-between;gap:18px;padding:16px 0;border-top:1px solid var(--line)}}li a{{font-weight:800}}li span{{color:var(--muted);white-space:nowrap}}@media(max-width:620px){{li{{display:grid;gap:5px}}li span{{white-space:normal}}}}
</style>
<script src="../../analytics.js" data-config="../../analytics-config.json" defer></script>
</head>
<body data-page-kind="category-landing" data-category="{esc(category_id)}">
<main>
<nav><a href="../../">イベント一覧へ戻る</a><a href="../../calendar.ics" data-track="calendar_download">カレンダーを購読</a></nav>
<div class="eyebrow">VRCHAT EVENT CATEGORY</div>
<h1>{esc(label)}</h1>
<p class="summary">{esc(description)}</p>
<div class="facts"><span class="fact">掲載 {count}件</span><span class="fact">参加情報: {esc(kind_summary)}</span></div>
<ul>{items}</ul>
</main>
</body>
</html>
'''


def render(
    events_path: Path,
    ontology_path: Path,
    public_root: Path,
    base_url: str = BASE_URL,
) -> dict[str, int]:
    payload = json.loads(events_path.read_text(encoding="utf-8"))
    generated_at = parse_time(payload.get("generated_at"))
    if generated_at is None:
        raise ValueError("events.json generated_at is missing or invalid")
    rows = payload.get("events")
    if not isinstance(rows, list):
        raise ValueError("events.json events must be a list")

    ontology = json.loads(ontology_path.read_text(encoding="utf-8"))
    categories = ontology.get("categories")
    if not isinstance(categories, list):
        raise ValueError("category ontology categories must be a list")

    labels: dict[str, str] = {}
    for row in categories:
        if not isinstance(row, dict):
            continue
        category_id = str(row.get("id") or "")
        if category_id == "other" or not SAFE_ID.fullmatch(category_id):
            continue
        if int(row.get("priority") or 0) <= 0:
            continue
        label = str(row.get("label") or "").strip()
        if label:
            labels[category_id] = label

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict) or not indexable(row, generated_at):
            continue
        category_id = str(row.get("category") or "")
        if category_id in labels:
            grouped[category_id].append(row)

    for events in grouped.values():
        events.sort(key=lambda row: (parse_time(row.get("starts_at")) or generated_at, str(row.get("id"))))

    categories_root = public_root / "categories"
    shutil.rmtree(categories_root, ignore_errors=True)
    categories_root.mkdir(parents=True, exist_ok=True)

    generated_ids = sorted(category_id for category_id, events in grouped.items() if events)
    for category_id in generated_ids:
        target = categories_root / category_id
        target.mkdir()
        (target / "index.html").write_text(
            render_category_page(category_id, labels[category_id], grouped[category_id], base_url),
            encoding="utf-8",
        )

    sitemap_path = public_root / "sitemap.xml"
    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    existing = [node.text or "" for node in root.findall(f"{namespace}url/{namespace}loc")]
    category_urls = [f"{base_url}/categories/{category_id}/" for category_id in generated_ids]
    if any("/categories/" in url for url in existing):
        raise ValueError("category URLs already present before category render")
    lastmod = generated_at.isoformat().replace("+00:00", "Z")
    for url in category_urls:
        node = ET.SubElement(root, f"{namespace}url")
        ET.SubElement(node, f"{namespace}loc").text = url
        ET.SubElement(node, f"{namespace}lastmod").text = lastmod
    ET.register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
    tree.write(sitemap_path, encoding="utf-8", xml_declaration=True)

    return {
        "category_count": len(generated_ids),
        "category_event_links": sum(len(grouped[category_id]) for category_id in generated_ids),
        "sitemap_url_count": len(existing) + len(category_urls),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, default=Path("public/events.json"))
    parser.add_argument("--ontology", type=Path, default=Path("public/category-ontology.json"))
    parser.add_argument("--public-root", type=Path, default=Path("public"))
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args()
    result = render(args.events, args.ontology, args.public_root, args.base_url.rstrip("/"))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
