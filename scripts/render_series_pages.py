from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from scripts.render_search_pages import BASE_URL, SAFE_ID, event_title, format_jst, https_url, indexable, parse_time
except ModuleNotFoundError:
    from render_search_pages import BASE_URL, SAFE_ID, event_title, format_jst, https_url, indexable, parse_time

MIN_OBSERVATIONS = 2
SERIES_LINK_START = "<!-- series-link:start -->"
SERIES_LINK_END = "<!-- series-link:end -->"


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def official_links(entry: dict[str, object]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in entry.get("official_links") or []:
        if not isinstance(item, dict):
            continue
        url = https_url(item.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        rows.append(
            {
                "url": url,
                "label": str(item.get("label") or "公式情報"),
                "kind": str(item.get("kind") or "official"),
            }
        )
    return rows[:8]


def recurring_entries(ontology: dict[str, object]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for row in ontology.get("entries") or []:
        if not isinstance(row, dict):
            continue
        series_id = str(row.get("canonical_id") or "")
        name = str(row.get("canonical_name") or "").strip()
        schedule = row.get("schedule") if isinstance(row.get("schedule"), dict) else {}
        curation = row.get("curation") if isinstance(row.get("curation"), dict) else {}
        if (
            not SAFE_ID.fullmatch(series_id)
            or not name
            or schedule.get("type") != "recurring"
            or curation.get("status") != "human_curated"
            or not official_links(row)
        ):
            continue
        if series_id in result:
            raise ValueError(f"duplicate canonical series ID: {series_id}")
        result[series_id] = row
    return result


def observation_counts(ontology: dict[str, object]) -> tuple[Counter[str], dict[str, str]]:
    counts: Counter[str] = Counter()
    latest: dict[str, str] = {}
    ambiguous: list[str] = []
    for entity in ontology.get("observed_entities") or []:
        if not isinstance(entity, dict):
            continue
        matched = entity.get("matched_ontology_ids")
        if not isinstance(matched, dict):
            continue
        positive: dict[str, int] = {}
        for key, value in matched.items():
            try:
                count = int(value)
            except (TypeError, ValueError):
                continue
            if count > 0:
                positive[str(key)] = count
        if len(positive) > 1:
            ambiguous.append(str(entity.get("entity_id") or "unknown"))
            continue
        if not positive:
            continue
        series_id, count = next(iter(positive.items()))
        counts[series_id] += count
        observed = str(entity.get("latest_observed_start") or "")
        if observed and observed > latest.get(series_id, ""):
            latest[series_id] = observed
    if ambiguous:
        raise ValueError("ambiguous ontology series matches: " + ", ".join(sorted(ambiguous)))
    return counts, latest


def render_series_page(
    series_id: str,
    entry: dict[str, object],
    observed_count: int,
    latest_observed: str,
    events: list[dict[str, object]],
    category_page_exists: bool,
    base_url: str,
) -> str:
    name = str(entry["canonical_name"])
    canonical = f"{base_url}/series/{series_id}/"
    schedule = entry.get("schedule") if isinstance(entry.get("schedule"), dict) else {}
    cadence = str(schedule.get("cadence") or schedule.get("label") or "定期開催")
    introduction = str(entry.get("introduction") or "").strip()
    participation = str(entry.get("participation_method") or "").strip()
    first_time = str(entry.get("first_time_guide") or "").strip()
    organizers = [str(value).strip() for value in entry.get("organizers") or [] if str(value).strip()]
    organizer = " / ".join(organizers)
    category = str(entry.get("category") or "")
    latest = format_jst(latest_observed)
    links = official_links(entry)
    description = f"VRChatの{name}について、次回開催・参加方法・公式情報をまとめています。観測{observed_count}回。"
    page_title = f"{name} 開催情報 | VRChatイベントカレンダー"

    event_items = "".join(
        '<li><a href="../../events/{id}/" data-track="event_detail_open" data-event-id="{id}" '
        'data-category="{category}" data-destination-type="series_to_event">{title}</a>'
        '<span>{date}</span></li>'.format(
            id=esc(event["id"]),
            category=esc(event.get("category")),
            title=esc(event_title(event)),
            date=esc(format_jst(event.get("starts_at"))),
        )
        for event in events
    )
    events_section = (
        f'<section><h2>今後の開催</h2><ul class="events">{event_items}</ul></section>'
        if event_items
        else '<section><h2>今後の開催</h2><p>現在、このカレンダーで確認できる次回開催はありません。最新情報は公式リンクを確認してください。</p></section>'
    )
    link_items = "".join(
        '<li><a href="{url}" target="_blank" rel="noopener noreferrer" data-track="official_link_click" '
        'data-destination-type="{kind}">{label}</a></li>'.format(
            url=esc(row["url"]), kind=esc(row["kind"]), label=esc(row["label"])
        )
        for row in links
    )
    highlights = "".join(f"<li>{esc(value)}</li>" for value in entry.get("highlights") or [])
    category_link = (
        f'<a href="../../categories/{esc(category)}/">同じカテゴリを見る</a>'
        if category_page_exists
        else ""
    )
    nav_links = "".join(
        part
        for part in (
            '<a href="../../">イベント一覧へ戻る</a>',
            category_link,
            '<a href="../../calendar.ics" data-track="calendar_download">カレンダーを購読</a>',
        )
        if part
    )
    facts = [
        ("開催傾向", cadence),
        ("観測回数", f"{observed_count}回"),
        ("直近の観測", latest),
        ("主催", organizer),
    ]
    facts_html = "".join(
        f"<div><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>"
        for label, value in facts
        if value
    )
    participation_html = f"<p>{esc(participation)}</p>" if participation else ""
    first_time_html = f"<p>{esc(first_time)}</p>" if first_time else ""
    intro_html = f'<p class="intro">{esc(introduction)}</p>' if introduction else ""
    highlights_html = f"<ul>{highlights}</ul>" if highlights else ""

    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(page_title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:locale" content="ja_JP">
<meta property="og:site_name" content="VRChatイベントカレンダー">
<meta property="og:title" content="{esc(page_title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta name="twitter:card" content="summary">
<style>
:root{{--bg:#fbfaf7;--surface:#fff;--ink:#243653;--muted:#66758d;--line:#dfe6ef}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Noto Sans JP",sans-serif}}main{{width:min(900px,100%);margin:auto;padding:28px 18px 64px}}a{{color:inherit}}nav{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:28px}}nav a{{font-weight:700}}.eyebrow{{font-size:.78rem;font-weight:800;letter-spacing:.1em;color:#58729a}}h1{{font-size:clamp(1.9rem,6vw,3.4rem);line-height:1.08;letter-spacing:-.035em;margin:.5rem 0 1rem}}h2{{margin-top:34px}}.intro,p{{line-height:1.8}}dl{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}dl div{{padding:14px;border:1px solid var(--line);border-radius:14px;background:var(--surface)}}dt{{font-size:.75rem;color:var(--muted);font-weight:800}}dd{{margin:5px 0 0}}ul{{padding-left:1.25rem}}.events{{list-style:none;padding:0}}.events li{{display:flex;justify-content:space-between;gap:18px;padding:14px 0;border-top:1px solid var(--line)}}.events a{{font-weight:800}}.events span{{color:var(--muted);white-space:nowrap}}@media(max-width:620px){{dl{{grid-template-columns:1fr}}.events li{{display:grid;gap:5px}}.events span{{white-space:normal}}}}
</style>
<script src="../../analytics.js" data-config="../../analytics-config.json" defer></script>
</head>
<body data-page-kind="series-landing" data-series-id="{esc(series_id)}" data-category="{esc(category)}">
<main>
<nav>{nav_links}</nav>
<div class="eyebrow">VRCHAT EVENT SERIES · {esc(cadence)}</div>
<h1>{esc(name)}</h1>
{intro_html}
<dl>{facts_html}</dl>
{events_section}
<section><h2>参加方法</h2>{participation_html}{first_time_html}</section>
<section><h2>特徴</h2>{highlights_html}</section>
<section><h2>公式情報</h2><ul>{link_items}</ul></section>
<p>開催日時・参加条件は変更される場合があります。参加前に最新の公式情報を確認してください。</p>
</main>
</body>
</html>
'''


def clear_series_links(events_root: Path) -> None:
    pattern = re.compile(re.escape(SERIES_LINK_START) + r".*?" + re.escape(SERIES_LINK_END), re.S)
    for path in events_root.glob("*/index.html"):
        text = path.read_text(encoding="utf-8")
        cleaned = pattern.sub("", text)
        if cleaned != text:
            path.write_text(cleaned, encoding="utf-8")


def add_series_link(path: Path, series_id: str, event: dict[str, object]) -> None:
    text = path.read_text(encoding="utf-8")
    marker = "</nav>"
    if marker not in text:
        raise ValueError(f"event detail nav missing: {path}")
    link = (
        f'{SERIES_LINK_START}<a href="../../series/{esc(series_id)}/" data-track="series_open" '
        f'data-event-id="{esc(event.get("id"))}" data-category="{esc(event.get("category"))}" '
        f'data-destination-type="series">このシリーズを見る</a>{SERIES_LINK_END}'
    )
    text = text.replace(marker, link + marker, 1)
    path.write_text(text, encoding="utf-8")


def render(
    events_path: Path,
    ontology_path: Path,
    public_root: Path,
    base_url: str = BASE_URL,
) -> dict[str, int]:
    event_doc = json.loads(events_path.read_text(encoding="utf-8"))
    generated_at = parse_time(event_doc.get("generated_at"))
    if generated_at is None:
        raise ValueError("events.json generated_at is missing or invalid")
    rows = event_doc.get("events")
    if not isinstance(rows, list):
        raise ValueError("events.json events must be a list")

    ontology = json.loads(ontology_path.read_text(encoding="utf-8"))
    entries = recurring_entries(ontology)
    counts, latest = observation_counts(ontology)
    eligible_ids = sorted(
        series_id
        for series_id, entry in entries.items()
        if counts[series_id] >= MIN_OBSERVATIONS and official_links(entry)
    )

    future_events: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict) or not indexable(row, generated_at):
            continue
        series_id = str(row.get("ontology_id") or "")
        if series_id in eligible_ids:
            future_events[series_id].append(row)
    for events in future_events.values():
        events.sort(key=lambda row: (parse_time(row.get("starts_at")) or generated_at, str(row.get("id"))))

    series_root = public_root / "series"
    shutil.rmtree(series_root, ignore_errors=True)
    series_root.mkdir(parents=True, exist_ok=True)
    for series_id in eligible_ids:
        entry = entries[series_id]
        category = str(entry.get("category") or "")
        target = series_root / series_id
        target.mkdir()
        (target / "index.html").write_text(
            render_series_page(
                series_id,
                entry,
                counts[series_id],
                latest.get(series_id, ""),
                future_events.get(series_id, []),
                (public_root / "categories" / category / "index.html").is_file(),
                base_url,
            ),
            encoding="utf-8",
        )

    events_root = public_root / "events"
    clear_series_links(events_root)
    reverse_links = 0
    for series_id, events in future_events.items():
        for event in events:
            path = events_root / str(event["id"]) / "index.html"
            if not path.is_file():
                raise ValueError(f"indexable event detail missing: {event['id']}")
            add_series_link(path, series_id, event)
            reverse_links += 1

    sitemap_path = public_root / "sitemap.xml"
    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    for node in list(root.findall(f"{namespace}url")):
        loc = node.find(f"{namespace}loc")
        if loc is not None and isinstance(loc.text, str) and "/series/" in loc.text:
            root.remove(node)
    existing = [node.text or "" for node in root.findall(f"{namespace}url/{namespace}loc")]
    lastmod = generated_at.isoformat().replace("+00:00", "Z")
    series_urls = [f"{base_url}/series/{series_id}/" for series_id in eligible_ids]
    for url in series_urls:
        node = ET.SubElement(root, f"{namespace}url")
        ET.SubElement(node, f"{namespace}loc").text = url
        ET.SubElement(node, f"{namespace}lastmod").text = lastmod
    ET.register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
    tree.write(sitemap_path, encoding="utf-8", xml_declaration=True)

    return {
        "series_count": len(eligible_ids),
        "series_event_links": sum(len(future_events.get(series_id, [])) for series_id in eligible_ids),
        "event_series_reverse_links": reverse_links,
        "series_observations": sum(counts[series_id] for series_id in eligible_ids),
        "sitemap_url_count": len(existing) + len(series_urls),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, default=Path("public/events.json"))
    parser.add_argument("--ontology", type=Path, default=Path("public/event-ontology.json"))
    parser.add_argument("--public-root", type=Path, default=Path("public"))
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args()
    result = render(args.events, args.ontology, args.public_root, args.base_url.rstrip("/"))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
