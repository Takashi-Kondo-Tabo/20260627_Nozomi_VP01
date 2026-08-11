"""Markdown 版のドキュメント(ブログ下書き・Notion 貼り付け用)。"""

from __future__ import annotations

from datetime import datetime

from ..cluster import Stop, route_length_m
from ..models import Photo


def _clock(dt: datetime | None) -> str:
    return dt.strftime("%H:%M") if dt else "--:--"


def render(photos: list[Photo], stops: list[Stop], meta: dict, date_label: str = "") -> str:
    geo = [p for p in photos if p.has_geo]
    lines: list[str] = [
        f"# {meta.get('title', '写真の記録')}",
        "",
        f"**{date_label}** ・ 写真 {len(photos)} 枚(ジオタグあり {len(geo)} 枚)"
        f" ・ 立ち寄り {len(stops)} か所 ・ 直線距離 約 {route_length_m(stops) / 1000:.1f} km",
        "",
        meta.get("summary", ""),
        "",
    ]

    if stops:
        lines += ["## その日の行程", ""]
        for stop in stops:
            link = f"https://www.google.com/maps/search/?api=1&query={stop.latitude:.6f},{stop.longitude:.6f}"
            lines.append(
                f"{stop.index}. **[{stop.label}]({link})** "
                f"（{_clock(stop.start)}–{_clock(stop.end)} ・ {len(stop.photos)} 枚）"
            )
            if stop.summary:
                lines.append(f"   - {stop.summary}")
        lines.append("")

    lines += ["## 写真と解説", ""]
    for photo in photos:
        head = f"### {_clock(photo.taken_at)}"
        if photo.place and photo.place.label():
            head += f' — {photo.place.label()}'
        lines.append(head)
        lines.append("")
        if photo.asset_path:
            lines.append(f"![{photo.filename}]({photo.asset_path})")
            lines.append("")
        if photo.caption:
            lines.append(photo.caption)
            lines.append("")
        details = []
        if photo.has_geo:
            details.append(
                f"[{photo.latitude:.5f}, {photo.longitude:.5f}]"
                f"(https://www.google.com/maps/search/?api=1&query={photo.latitude:.6f},{photo.longitude:.6f})"
            )
        else:
            details.append("ジオタグなし")
        camera = " ".join(x for x in (photo.camera_make, photo.camera_model) if x).strip()
        if camera:
            details.append(camera)
        details.append(photo.filename)
        lines.append("<small>" + " ・ ".join(details) + "</small>")
        lines.append("")

    return "\n".join(lines)
