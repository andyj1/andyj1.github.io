#!/usr/bin/env python3
"""Fetch Malmö forecast and patch weather blocks in res/malmo.html.

Updates weather UI only. Does not reshuffle the conference itinerary.
Among existing Lund open windows, marks the clearest day as a hint.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "res" / "malmo.html"

CONF_START = date(2026, 9, 7)
CONF_END = date(2026, 9, 13)
LAT = 55.605
LON = 13.0038

# Existing open Lund windows in the fixed itinerary (do not move schedule items).
LUND_CANDIDATES = {
    "2026-09-09": "Wed evening (after workshops ~17:30)",
    "2026-09-11": "Fri 9:00–14:30 (best half-day window)",
    "2026-09-12": "Sat after 12:30 poster",
}

DAY_META = {
    "2026-09-07": {"label": "Mon 7", "note": "Arrival"},
    "2026-09-08": {"label": "Tue 8", "note": "Workshops"},
    "2026-09-09": {"label": "Wed 9", "note": "Workshops"},
    "2026-09-10": {"label": "Thu 10", "note": "Grauman"},
    "2026-09-11": {"label": "Fri 11", "note": "LeCun"},
    "2026-09-12": {"label": "Sat 12", "note": "Poster day"},
    "2026-09-13": {"label": "Sun 13", "note": "Copenhagen"},
}


def wmo_to_ui(code: int) -> Tuple[str, str, str]:
    """Return (css_class, emoji, short description)."""
    if code == 0:
        return "sunny", "☀️", "Clear"
    if code == 1:
        return "sunny", "🌤️", "Mainly clear"
    if code == 2:
        return "partly", "⛅", "Partly cloudy"
    if code == 3:
        return "cloudy", "☁️", "Overcast"
    if code in (45, 48):
        return "cloudy", "🌫️", "Fog"
    if code in (51, 53, 55, 56, 57):
        return "rainy", "🌦️", "Drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "rainy", "🌧️", "Rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "cloudy", "🌨️", "Snow"
    if code in (95, 96, 99):
        return "rainy", "⛈️", "Thunderstorm"
    return "partly", "🌤️", "Mixed"


def clarity_score(code: int, precip_prob: int, precip_mm: float, tmax: float) -> float:
    """Higher = better outdoor day for Lund walking."""
    if code >= 61 and code not in (80,):  # heavy rain/snow/storm
        if code in (61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99):
            base = -50
        else:
            base = 0
    else:
        base = {
            0: 100,
            1: 92,
            2: 78,
            3: 55,
            45: 40,
            48: 35,
            51: 30,
            53: 20,
            55: 10,
        }.get(code, 25)
    score = float(base)
    score -= precip_prob * 0.55
    score -= min(precip_mm, 15.0) * 3.0
    score += max(0.0, min(tmax, 24.0) - 12.0) * 1.2
    # Prefer Fri half-day slightly when scores are close (longest open window).
    return score


def fetch_forecast() -> List[Dict[str, Any]]:
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
        "precipitation_probability_max,precipitation_sum"
        "&timezone=Europe%2FStockholm"
        f"&start_date={CONF_START.isoformat()}&end_date={CONF_END.isoformat()}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "andyj1-eccv-itinerary/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    daily = payload["daily"]
    days: List[Dict[str, Any]] = []
    for i, day in enumerate(daily["time"]):
        code = int(daily["weather_code"][i])
        css, icon, desc = wmo_to_ui(code)
        tmax = float(daily["temperature_2m_max"][i])
        tmin = float(daily["temperature_2m_min"][i])
        precip_prob = int(daily["precipitation_probability_max"][i] or 0)
        precip_mm = float(daily["precipitation_sum"][i] or 0.0)
        days.append(
            {
                "date": day,
                "code": code,
                "css": css,
                "icon": icon,
                "desc": desc,
                "tmax": round(tmax),
                "tmin": round(tmin),
                "precip_prob": precip_prob,
                "precip_mm": precip_mm,
                "score": clarity_score(code, precip_prob, precip_mm, tmax),
            }
        )
    return days


def replace_marked(html: str, start: str, end: str, inner: str) -> str:
    pattern = re.compile(
        rf"(<!-- {re.escape(start)} -->)(.*?)(<!-- {re.escape(end)} -->)",
        re.DOTALL,
    )
    if not pattern.search(html):
        raise RuntimeError(f"Missing markers {start}/{end} in {HTML_PATH}")
    return pattern.sub(rf"\1\n{inner}\n            \3", html)


def build_strip(days: List[Dict[str, Any]], lund_date: Optional[str]) -> str:
    cards = []
    for d in days:
        meta = DAY_META[d["date"]]
        lund_class = " lund-pick" if d["date"] == lund_date else ""
        lund_tag = (
            '\n                    <span class="wx-lund">🏛 Best for Lund</span>'
            if d["date"] == lund_date
            else ""
        )
        note = d["desc"]
        if d["date"] == "2026-09-12" and d["date"] != lund_date:
            note = "Poster day"
        elif d["date"] == "2026-09-13" and d["date"] != lund_date:
            note = "Copenhagen"
        cards.append(
            f"""                <div class="weather-day {d['css']}{lund_class}" data-wx-date="{d['date']}" role="listitem">
                    <span class="wx-label">{meta['label']}</span>
                    <span class="wx-icon">{d['icon']}</span>
                    <span class="wx-temp">{d['tmax']}°</span><span class="wx-lo"> / {d['tmin']}°</span>
                    <div class="wx-desc" style="color:#7F8C8D;margin-top:2px;">{note}</div>{lund_tag}
                </div>"""
        )
    return (
        '            <div class="weather-strip" role="list" aria-label="Daily weather overview">\n'
        + "\n".join(cards)
        + "\n            </div>"
    )


def build_pack(days: List[Dict[str, Any]], lund_date: Optional[str]) -> str:
    rainy = [d for d in days if d["css"] == "rainy" or d["precip_prob"] >= 50]
    if rainy:
        labels = ", ".join(DAY_META[d["date"]]["label"] for d in rainy)
        umbrella = f'☔ <strong>Umbrella</strong> — likely wet: {labels}'
    else:
        umbrella = "☔ <strong>Umbrella</strong> — optional (low rain odds)"
    lund_chip = (
        f'🏛 <strong>Lund weather</strong> — {DAY_META[lund_date]["label"]} looks clearest'
        if lund_date
        else "🏛 <strong>Lund</strong> — no clear outdoor day yet"
    )
    chips = [
        "🧥 <strong>Light jacket</strong> — evenings cool",
        umbrella,
        "👟 <strong>Walking shoes</strong> — cobblestones",
        "🩱 <strong>Swimsuit</strong> — sauna/bath (Thu)",
        lund_chip,
    ]
    inner = "\n".join(f'                <span class="pack-chip">{c}</span>' for c in chips)
    return f'            <div class="pack-chips">\n{inner}\n            </div>'


def badge_html(day: Dict[str, Any], is_lund: bool) -> str:
    note = ""
    style = ""
    if day["css"] == "rainy" or day["precip_prob"] >= 55:
        note = " · bring umbrella"
        style = ' style="background:#D6EAF8;color:#1A5276;"'
    elif is_lund:
        note = " · best for Lund"
        style = ' style="background:#FFF3CD;color:#856404;"'
    elif day["css"] == "sunny":
        style = ' style="background:#FFF3CD;color:#856404;"'
    elif day["tmax"] <= 15:
        note = " · layer up"
    text = f"{day['icon']} {day['tmax']}° / {day['tmin']}°{note}"
    return f'<span class="weather-badge" data-wx-badge="{day["date"]}"{style}>{text}</span>'


def pick_lund_day(days: List[Dict[str, Any]]) -> Optional[str]:
    candidates = [d for d in days if d["date"] in LUND_CANDIDATES]
    if not candidates:
        return None
    # Require "clear enough": not heavy rain and score above threshold.
    viable = [
        d
        for d in candidates
        if d["score"] >= 35
        and d["code"] not in (61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99)
        and d["precip_prob"] <= 60
    ]
    pool = viable or candidates
    # Tie-break: Fri half-day preferred among near-equal scores.
    best = max(
        pool,
        key=lambda d: (d["score"], 1 if d["date"] == "2026-09-11" else 0),
    )
    return best["date"]


def patch_html(html: str, days: List[Dict[str, Any]]) -> str:
    by_date = {d["date"]: d for d in days}
    lund_date = pick_lund_day(days)

    html = replace_marked(
        html, "AUTO_WEATHER_STRIP_START", "AUTO_WEATHER_STRIP_END", build_strip(days, lund_date)
    )
    html = replace_marked(
        html, "AUTO_WEATHER_PACK_START", "AUTO_WEATHER_PACK_END", build_pack(days, lund_date)
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    updated = f"Last auto-update: {now} · Open-Meteo Malmö"
    html = replace_marked(html, "AUTO_WEATHER_UPDATED_START", "AUTO_WEATHER_UPDATED_END", updated)

    if lund_date:
        slot = LUND_CANDIDATES[lund_date]
        d = by_date[lund_date]
        hint = (
            f'<p class="lund-wx-hint" id="lund-wx-hint">🌤 <strong>Clearest day for Lund this week:</strong> '
            f"<strong>{DAY_META[lund_date]['label']}</strong> "
            f"— {d['icon']} {d['desc']}, {d['tmax']}° / {d['tmin']}° "
            f"(precip ~{d['precip_prob']}%). Suggested window: {slot}.</p>"
        )
    else:
        hint = (
            '<p class="lund-wx-hint" id="lund-wx-hint">🌤 <strong>Clearest day for Lund this week:</strong> '
            "no clearly dry day yet among Wed evening / Fri morning / Sat afternoon.</p>"
        )
    html = replace_marked(html, "AUTO_LUND_WX_HINT_START", "AUTO_LUND_WX_HINT_END", hint)

    for day in days:
        overview = f"{day['icon']} {day['tmax']}°"
        html = re.sub(
            rf'(<td data-wx-overview="{day["date"]}">)(.*?)(</td>)',
            rf"\1{overview}\3",
            html,
            count=1,
            flags=re.DOTALL,
        )
        badge = badge_html(day, day["date"] == lund_date)
        html = re.sub(
            rf'<span class="weather-badge" data-wx-badge="{day["date"]}"[^>]*>.*?</span>',
            badge,
            html,
            count=1,
            flags=re.DOTALL,
        )

    return html


def main() -> int:
    today = date.today()
    if today > CONF_END:
        print(f"Conference ended ({CONF_END.isoformat()}); skipping weather update.")
        return 0

    if not HTML_PATH.exists():
        print(f"Missing {HTML_PATH}", file=sys.stderr)
        return 1

    try:
        days = fetch_forecast()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
        print(f"Forecast fetch failed: {exc}", file=sys.stderr)
        return 1

    if len(days) != 7:
        print(f"Expected 7 conference days, got {len(days)}", file=sys.stderr)
        return 1

    original = HTML_PATH.read_text(encoding="utf-8")
    updated = patch_html(original, days)
    if updated == original:
        print("Weather already up to date.")
        return 0

    HTML_PATH.write_text(updated, encoding="utf-8")
    lund = pick_lund_day(days)
    print("Updated weather in", HTML_PATH.relative_to(ROOT))
    for d in days:
        mark = " ← Lund pick" if d["date"] == lund else ""
        print(
            f"  {d['date']}: {d['icon']} {d['desc']} {d['tmax']}/{d['tmin']}° "
            f"precip {d['precip_prob']}% score={d['score']:.1f}{mark}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
