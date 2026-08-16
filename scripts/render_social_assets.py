from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlencode

from PIL import Image, ImageDraw, ImageFont

try:
    from scripts.render_search_pages import BASE_URL, event_title, format_jst, indexable, parse_time
except ModuleNotFoundError:
    from render_search_pages import BASE_URL, event_title, format_jst, indexable, parse_time

WIDTH = 1200
HEIGHT = 630
SOCIAL_META_START = "<!-- social-meta:start -->"
SOCIAL_META_END = "<!-- social-meta:end -->"
SHARE_START = "<!-- share-controls:start -->"
SHARE_END = "<!-- share-controls:end -->"
FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def strip_block(text: str, start: str, end: str) -> str:
    return re.sub(re.escape(start) + r".*?" + re.escape(end), "", text, flags=re.S)


def resolve_font(explicit: Path | None = None) -> Path | None:
    candidates = [explicit, Path(os.environ["OG_FONT_PATH"]) if os.environ.get("OG_FONT_PATH") else None]
    candidates.extend(Path(value) for value in FONT_CANDIDATES)
    return next((path for path in candidates if path and path.is_file()), None)


def load_font(path: Path | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.truetype(str(path), size=size) if path else ImageFont.load_default(size=size)


def fit_lines(draw: ImageDraw.ImageDraw, value: str, font: ImageFont.ImageFont, max_width: int, max_lines: int) -> list[str]:
    value = " ".join(value.split())
    if not value:
        return [""]
    lines: list[str] = []
    current = ""
    for char in value:
        candidate = current + char
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = char
            if len(lines) == max_lines:
                break
        else:
            current = candidate
    if len(lines) < max_lines and current:
        lines.append(current)
    consumed = "".join(lines)
    if len(consumed) < len(value) and lines:
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > max_width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return lines[:max_lines]


def accent_for(category: str) -> tuple[int, int, int]:
    palette = (
        (203, 224, 255),
        (220, 236, 211),
        (250, 220, 222),
        (244, 226, 194),
        (224, 218, 244),
        (208, 235, 232),
    )
    digest = hashlib.sha256(category.encode("utf-8")).digest()[0]
    return palette[digest % len(palette)]


def draw_card(event: dict[str, object], target: Path, font_path: Path | None) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), (251, 250, 247))
    draw = ImageDraw.Draw(image)
    ink = (36, 54, 83)
    muted = (95, 110, 132)
    category = str(event.get("category_label") or event.get("category") or "VRChat EVENT")
    accent = accent_for(str(event.get("category") or category))
    title = event_title(event)
    start = format_jst(event.get("starts_at"))

    brand_font = load_font(font_path, 28)
    pill_font = load_font(font_path, 27)
    title_font = load_font(font_path, 62)
    date_font = load_font(font_path, 34)
    foot_font = load_font(font_path, 24)

    draw.rounded_rectangle((48, 44, WIDTH - 48, HEIGHT - 44), radius=34, fill=(255, 255, 255), outline=(223, 230, 239), width=2)
    draw.rounded_rectangle((48, 44, WIDTH - 48, 70), radius=13, fill=accent)
    draw.text((84, 94), "VRCHAT EVENT CALENDAR", font=brand_font, fill=muted)

    pill_box = draw.textbbox((0, 0), category, font=pill_font)
    pill_width = min(WIDTH - 168, pill_box[2] - pill_box[0] + 44)
    draw.rounded_rectangle((84, 150, 84 + pill_width, 198), radius=24, fill=accent)
    draw.text((106, 157), category, font=pill_font, fill=ink)

    y = 236
    for line in fit_lines(draw, title, title_font, WIDTH - 168, 3):
        draw.text((84, y), line, font=title_font, fill=ink)
        y += 78

    draw.text((84, 490), start, font=date_font, fill=ink)
    draw.line((84, 548, WIDTH - 84, 548), fill=(223, 230, 239), width=2)
    draw.text((84, 566), "詳細URLを共有して、参加前に最新の公式情報を確認", font=foot_font, fill=muted)

    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG", optimize=True, compress_level=9)


def social_meta(event: dict[str, object], base_url: str) -> str:
    event_id = str(event["id"])
    title = event_title(event)
    image = f"{base_url}/og/events/{event_id}.png"
    return (
        f'{SOCIAL_META_START}\n'
        f'<meta property="og:image" content="{esc(image)}">\n'
        '<meta property="og:image:type" content="image/png">\n'
        f'<meta property="og:image:alt" content="{esc(title)}">\n'
        f'<meta property="og:image:width" content="{WIDTH}">\n'
        f'<meta property="og:image:height" content="{HEIGHT}">\n'
        '<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:image" content="{esc(image)}">\n'
        f'<meta name="twitter:image:alt" content="{esc(title)}">\n'
        f'{SOCIAL_META_END}'
    )


def share_controls(event: dict[str, object], base_url: str) -> str:
    event_id = str(event["id"])
    category = str(event.get("category") or "")
    title = event_title(event)
    canonical = f"{base_url}/events/{event_id}/"
    native_url = canonical + "?" + urlencode({"utm_source": "share", "utm_medium": "social", "utm_campaign": "event_share"})
    x_url = canonical + "?" + urlencode({"utm_source": "x", "utm_medium": "social", "utm_campaign": "event_share"})
    intent = "https://x.com/intent/tweet?" + urlencode({"text": title, "url": x_url})
    return (
        f'{SHARE_START}<div class="actions share-actions">'
        f'<button class="action" type="button" data-share-native data-share-url="{esc(native_url)}" '
        f'data-share-title="{esc(title)}" data-track="share_click" data-event-id="{esc(event_id)}" '
        f'data-category="{esc(category)}" data-destination-type="native">共有 / URLコピー</button>'
        f'<a class="action" href="{esc(intent)}" target="_blank" rel="noopener noreferrer" '
        f'data-track="share_click" data-event-id="{esc(event_id)}" data-category="{esc(category)}" '
        'data-destination-type="x">Xで共有</a>'
        '<span class="share-status" aria-live="polite"></span>'
        f'</div>{SHARE_END}'
    )


def patch_event_page(path: Path, event: dict[str, object], base_url: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = strip_block(text, SOCIAL_META_START, SOCIAL_META_END)
    text = re.sub(r'<meta property="og:image(?::[^\"]+)?"[^>]*>\n?', "", text)
    text = re.sub(r'<meta name="twitter:(?:card|image|image:alt)"[^>]*>\n?', "", text)
    marker = f'<meta property="og:url" content="{esc(base_url)}/events/{esc(event["id"])}/">'
    if marker not in text:
        raise ValueError(f"event page canonical social marker missing: {event['id']}")
    text = text.replace(marker, marker + "\n" + social_meta(event, base_url), 1)

    text = strip_block(text, SHARE_START, SHARE_END)
    notice = '<p class="notice">'
    if notice not in text:
        raise ValueError(f"event page notice marker missing: {event['id']}")
    text = text.replace(notice, share_controls(event, base_url) + "\n" + notice, 1)
    if 'src="../../share.js"' not in text:
        text = text.replace("</head>", '<script src="../../share.js" defer></script>\n</head>', 1)
    path.write_text(text, encoding="utf-8")


def write_share_script(root: Path) -> None:
    script = r'''(() => {
  const copy = async value => {
    if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(value);
    const area = document.createElement('textarea');
    area.value = value;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    area.remove();
  };
  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-share-native]');
    if (!button) return;
    const url = button.dataset.shareUrl || location.href;
    const title = button.dataset.shareTitle || document.title;
    const status = button.parentElement?.querySelector('.share-status');
    try {
      if (navigator.share) {
        await navigator.share({ title, url });
        if (status) status.textContent = '共有しました';
      } else {
        await copy(url);
        if (status) status.textContent = '共有URLをコピーしました';
      }
    } catch (error) {
      if (error?.name !== 'AbortError' && status) status.textContent = '共有できませんでした';
    }
  });
})();
'''
    (root / "share.js").write_text(script, encoding="utf-8")


def render(events_path: Path, public_root: Path, base_url: str = BASE_URL, font_path: Path | None = None) -> dict[str, int]:
    payload = json.loads(events_path.read_text(encoding="utf-8"))
    generated_at = parse_time(payload.get("generated_at"))
    if generated_at is None:
        raise ValueError("events.json generated_at is missing or invalid")
    rows = payload.get("events")
    if not isinstance(rows, list):
        raise ValueError("events.json events must be a list")
    selected = [row for row in rows if isinstance(row, dict) and indexable(row, generated_at)]
    selected.sort(key=lambda row: (parse_time(row.get("starts_at")) or generated_at, str(row.get("id"))))

    resolved_font = resolve_font(font_path)
    og_root = public_root / "og" / "events"
    shutil.rmtree(og_root, ignore_errors=True)
    og_root.mkdir(parents=True, exist_ok=True)
    for event in selected:
        event_id = str(event["id"])
        page = public_root / "events" / event_id / "index.html"
        if not page.is_file():
            raise ValueError(f"indexable event page missing: {event_id}")
        draw_card(event, og_root / f"{event_id}.png", resolved_font)
        patch_event_page(page, event, base_url)
    write_share_script(public_root)

    images = list(og_root.glob("*.png"))
    if len(images) != len(selected):
        raise ValueError("OG image coverage mismatch")
    return {
        "indexable_count": len(selected),
        "og_image_count": len(images),
        "share_enabled_count": len(selected),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, default=Path("public/events.json"))
    parser.add_argument("--public-root", type=Path, default=Path("public"))
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--font", type=Path)
    args = parser.parse_args()
    result = render(args.events, args.public_root, args.base_url.rstrip("/"), args.font)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
