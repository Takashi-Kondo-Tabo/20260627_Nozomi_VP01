"""写真1枚を表す共通データモデル。

どの取得元(Google Takeout / ローカル / Google Photos Picker API)から来た写真も、
最終的にこの `Photo` に正規化してから地図描画・解説生成に渡す。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


@dataclass
class Place:
    """逆ジオコーディング結果。"""

    name: str = ""
    address: str = ""
    locality: str = ""  # 市区町村
    admin_area: str = ""  # 都道府県
    country: str = ""

    def label(self) -> str:
        for candidate in (self.name, self.locality, self.admin_area, self.address):
            if candidate:
                return candidate
        return ""


@dataclass
class Photo:
    id: str
    filename: str
    taken_at: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None

    width: int | None = None
    height: int | None = None
    camera_make: str = ""
    camera_model: str = ""

    # Google Photos / Takeout 由来のユーザー入力
    title: str = ""
    description: str = ""

    # ファイルの実体(ローカルパス)と、ドキュメントから参照する相対パス
    source_path: str = ""
    asset_path: str = ""
    thumb_path: str = ""

    # 後段で埋まるもの
    place: Place | None = None
    caption: str = ""
    tags: list[str] = field(default_factory=list)

    origin: str = ""  # "takeout" / "local" / "picker" など

    @property
    def has_geo(self) -> bool:
        return (
            self.latitude is not None
            and self.longitude is not None
            # (0, 0) は「ジオタグ無し」を 0 で埋めた壊れたメタデータであることが多い
            and not (abs(self.latitude) < 1e-9 and abs(self.longitude) < 1e-9)
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["taken_at"] = self.taken_at.isoformat() if self.taken_at else None
        data["has_geo"] = self.has_geo
        return data


def haversine_m(a: Photo, b: Photo) -> float:
    """2枚の写真の撮影地点間の距離(メートル)。"""
    if not (a.has_geo and b.has_geo):
        return float("inf")
    r = 6371008.8
    lat1, lon1 = math.radians(a.latitude), math.radians(a.longitude)
    lat2, lon2 = math.radians(b.latitude), math.radians(b.longitude)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))
