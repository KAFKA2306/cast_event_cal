from pathlib import Path


CSS = Path("public/tonight/tonight.css").read_text(encoding="utf-8")


def test_tonight_keyboard_focus_and_touch_targets_are_explicit() -> None:
    assert "min-height:44px" in CSS
    assert ":focus-visible" in CSS
    assert "outline:3px solid #1d63aa" in CSS


def test_tonight_respects_motion_and_forced_color_preferences() -> None:
    assert "@media(prefers-reduced-motion:reduce)" in CSS
    assert "animation:none!important" in CSS
    assert "@media(forced-colors:active)" in CSS
    assert "outline-color:Highlight" in CSS
    assert "color:HighlightText" in CSS
