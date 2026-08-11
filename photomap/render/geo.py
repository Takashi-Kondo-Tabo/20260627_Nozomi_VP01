"""GeoJSON / KML 書き出し。

Google マイマップ(My Maps)は KML と GeoJSON をインポートできるので、
生成した KML を取り込めば「Google マップ上のマイマップ」として共有できる。
"""

from __future__ import annotations

import html
import json

from ..cluster import Stop
from ..models import Photo


def to_geojson(photos: list[Photo], stops: list[Stop]) -> str:
    features = []
    for i, photo in enumerate(photos):
        if not photo.has_geo:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [photo.longitude, photo.latitude]},
                "properties": {
                    "index": i,
                    "filename": photo.filename,
                    "taken_at": photo.taken_at.isoformat() if photo.taken_at else None,
                    "place": photo.place.label() if photo.place else "",
                    "caption": photo.caption,
                    "image": photo.asset_path,
                },
            }
        )
    if len(stops) > 1:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[s.longitude, s.latitude] for s in stops],
                },
                "properties": {"name": "移動ルート(直線近似)"},
            }
        )
    return json.dumps(
        {"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2
    )


def to_kml(photos: list[Photo], stops: list[Stop], title: str = "写真の記録") -> str:
    def esc(text: str) -> str:
        return html.escape(text or "")

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
        f"<name>{esc(title)}</name>",
    ]
    for photo in photos:
        if not photo.has_geo:
            continue
        when = photo.taken_at.strftime("%H:%M") if photo.taken_at else ""
        name = f"{when} {photo.place.label() if photo.place else photo.filename}".strip()
        parts += [
            "<Placemark>",
            f"<name>{esc(name)}</name>",
            f"<description><![CDATA[{html.escape(photo.caption, quote=False)}]]></description>",
            f"<Point><coordinates>{photo.longitude:.6f},{photo.latitude:.6f},0</coordinates></Point>",
            "</Placemark>",
        ]
    if len(stops) > 1:
        coords = " ".join(f"{s.longitude:.6f},{s.latitude:.6f},0" for s in stops)
        parts += [
            "<Placemark><name>移動ルート(直線近似)</name>",
            f"<LineString><tessellate>1</tessellate><coordinates>{coords}</coordinates></LineString>",
            "</Placemark>",
        ]
    parts.append("</Document></kml>")
    return "\n".join(parts)
