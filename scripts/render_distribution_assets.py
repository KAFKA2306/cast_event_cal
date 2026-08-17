from __future__ import annotations

import html
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CONFIG = Path("config/poster_config.json")
QR_IMAGE = Path("web/assets/cast-event-cal-qr.pbm")
PUBLIC_DIR = Path("public")
MEDIA_DIR = PUBLIC_DIR / "media"
USE_PAGE = PUBLIC_DIR / "use" / "index.html"
HOME_PAGE = PUBLIC_DIR / "index.html"

COLORS = {
    "bg": "#fbfaf7",
    "ink": "#243653",
    "muted": "#66758d",
    "blue": "#8fb5ec",
    "lav": "#b9a8e6",
    "mint": "#b7dbc8",
    "white": "#ffffff",
}


def load_config(path: Path = CONFIG) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {"site_url", "title", "tagline", "action", "posters"}
    missing = sorted(required - data.keys())
    if missing:
        raise ValueError(f"missing poster config keys: {', '.join(missing)}")
    return data


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=size)


def fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    start_size: int,
    min_size: int = 20,
) -> ImageFont.FreeTypeFont:
    for size in range(start_size, min_size - 1, -2):
        selected = font(size)
        if draw.textbbox((0, 0), text, font=selected)[2] <= max_width:
            return selected
    return font(min_size)


def render_poster(config: dict, qr_path: Path, output: Path, width: int, height: int) -> None:
    image = Image.new("RGB", (width, height), COLORS["bg"])
    draw = ImageDraw.Draw(image)
    margin = max(40, int(width * 0.065))
    radius = max(26, int(width * 0.035))

    draw.ellipse((-width * 0.2, -height * 0.12, width * 0.56, height * 0.62), fill=COLORS["blue"])
    draw.ellipse((width * 0.62, height * 0.02, width * 1.18, height * 0.52), fill=COLORS["lav"])
    draw.rounded_rectangle((margin, margin, width - margin, height - margin), radius=radius, fill=COLORS["white"])

    inner = margin + max(30, int(width * 0.045))
    top = inner
    eyebrow_font = font(max(18, int(width * 0.028)))
    draw.text((inner, top), "TODAY / THIS WEEK · JST", fill=COLORS["muted"], font=eyebrow_font)
    top += int(width * 0.075)

    title_font = fit_text(draw, config["title"], width - 2 * inner, int(width * 0.085), 34)
    draw.text((inner, top), config["title"], fill=COLORS["ink"], font=title_font)
    top += int(title_font.size * 1.28)

    tagline_font = fit_text(draw, config["tagline"], width - 2 * inner, int(width * 0.045), 24)
    draw.text((inner, top), config["tagline"], fill=COLORS["ink"], font=tagline_font)
    top += int(tagline_font.size * 1.7)

    with Image.open(qr_path) as source_qr:
        qr = source_qr.convert("RGB")
    qr_size = min(int(width * 0.42), int(height * 0.36))
    qr = qr.resize((qr_size, qr_size), Image.Resampling.NEAREST)
    qr_x = inner
    qr_y = max(top, height - margin - qr_size - int(height * 0.12))
    image.paste(qr, (qr_x, qr_y))

    text_x = qr_x + qr_size + max(24, int(width * 0.04))
    text_width = width - inner - text_x
    action_font = fit_text(draw, config["action"], text_width, int(width * 0.04), 22)
    url_text = config["site_url"].removeprefix("https://")
    url_font = fit_text(draw, url_text, text_width, int(width * 0.026), 16)

    draw.text((text_x, qr_y + int(qr_size * 0.15)), config["action"], fill=COLORS["ink"], font=action_font)
    draw.text((text_x, qr_y + int(qr_size * 0.62)), url_text, fill=COLORS["muted"], font=url_font)

    badge_y = height - margin - int(height * 0.07)
    badge_h = max(34, int(height * 0.045))
    badge_w = max(190, int(width * 0.34))
    draw.rounded_rectangle(
        (inner, badge_y, inner + badge_w, badge_y + badge_h),
        radius=badge_h // 2,
        fill=COLORS["mint"],
    )
    badge_font = font(max(16, int(width * 0.022)))
    draw.text(
        (inner + 16, badge_y + (badge_h - badge_font.size) // 2 - 1),
        "OPEN DATA · OFFICIAL LINKS",
        fill=COLORS["ink"],
        font=badge_font,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="WEBP", quality=88, method=6)


def render_use_page(config: dict, output: Path) -> None:
    site = html.escape(config["site_url"], quote=True)
    repo = "https://github.com/KAFKA2306/cast_event_cal"
    posters = "\n".join(
        (
            f'<li><a href="../media/{html.escape(item["filename"], quote=True)}">'
            f'{html.escape(item["filename"])}</a> — {item["width"]} × {item["height"]} WebP</li>'
        )
        for item in config["posters"]
    )
    document = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="VRChatイベントカレンダーのUnityワールド掲示・紹介・再利用向け公開素材">
<link rel="canonical" href="{site}use/">
<title>配布・紹介素材 | VRChatイベントカレンダー</title>
<style>
:root{{--bg:#fbfaf7;--surface:#fff;--ink:#243653;--muted:#66758d;--line:#dfe6ef}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Noto Sans JP",sans-serif}}
main{{width:min(880px,100%);margin:auto;padding:40px 18px 72px}}h1{{font-size:clamp(2rem,6vw,4rem);letter-spacing:-.045em;margin:.3em 0}}p,li{{line-height:1.8}}.lede{{color:var(--muted);font-size:1.05rem}}
section{{margin-top:22px;padding:22px;border:1px solid var(--line);border-radius:20px;background:var(--surface)}}a{{color:#355b91}}code{{overflow-wrap:anywhere}}.actions{{display:flex;gap:10px;flex-wrap:wrap}}.button{{display:inline-flex;padding:10px 14px;border:1px solid var(--line);border-radius:999px;text-decoration:none;font-weight:700}}.button.primary{{background:var(--ink);color:white;border-color:var(--ink)}}
</style>
</head>
<body><main>
<p><a href="../">← カレンダーへ戻る</a></p>
<h1>配布・紹介素材</h1>
<p class="lede">VRChatワールドへの掲示、記事・ブログでの紹介、カレンダー購読やデータ利用に使える正準URLをまとめています。</p>
<section><h2>Unity / VRChatワールド向けポスター</h2>
<p>固定URLの画像です。差し替え時もURLは変えません。VRChatのImage Loadingでは <code>*.github.io</code> が許可ドメインで、画像の最大解像度は2048 × 2048です。</p>
<ul>{posters}</ul>
</section>
<section><h2>正準リンク</h2><div class="actions">
<a class="button primary" href="{site}">Web</a>
<a class="button" href="../events.json">JSON</a>
<a class="button" href="../calendar.ics">ICS</a>
<a class="button" href="{repo}">GitHub</a>
</div></section>
<section><h2>紹介するとき</h2>
<p>記事・SNS・ワールド内掲示からは <code>{site}</code> をリンク先として使用してください。イベント参加前は各イベントの公式リンクで最新情報を確認してください。</p>
</section>
</main></body></html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")


def link_homepage(path: Path = HOME_PAGE) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    link = '<a href="use/">配布・紹介素材</a>'
    if link in text:
        return
    github = '<a href="https://github.com/KAFKA2306/cast_event_cal">GitHub</a>'
    if github not in text:
        raise ValueError("GitHub footer link not found in public/index.html")
    path.write_text(text.replace(github, f"{link} · {github}", 1), encoding="utf-8")


def main() -> None:
    config = load_config()
    if not QR_IMAGE.exists():
        raise FileNotFoundError(QR_IMAGE)
    for item in config["posters"]:
        render_poster(
            config,
            QR_IMAGE,
            MEDIA_DIR / item["filename"],
            int(item["width"]),
            int(item["height"]),
        )
    render_use_page(config, USE_PAGE)
    link_homepage()


if __name__ == "__main__":
    main()
