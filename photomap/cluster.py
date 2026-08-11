"""写真を「立ち寄りスポット」単位にまとめる。

地図上のマーカーが1箇所に何十個も重なるのを避け、ドキュメントを
「その日の行程」として読めるようにするための前処理。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .models import Photo, Place, haversine_m


@dataclass
class Stop:
    """同じ場所・同じ時間帯にまとまった写真の集合。"""

    index: int
    photos: list[Photo] = field(default_factory=list)
    latitude: float = 0.0
    longitude: float = 0.0
    place: Place | None = None
    summary: str = ""

    @property
    def start(self) -> datetime | None:
        times = [p.taken_at for p in self.photos if p.taken_at]
        return min(times) if times else None

    @property
    def end(self) -> datetime | None:
        times = [p.taken_at for p in self.photos if p.taken_at]
        return max(times) if times else None

    @property
    def label(self) -> str:
        if self.place and self.place.label():
            return self.place.label()
        return f"地点 {self.index}"


def build_stops(
    photos: list[Photo], radius_m: float = 250.0, gap_minutes: float = 45.0
) -> list[Stop]:
    """撮影順に走査し、距離が離れたか時間が空いたところで区切る。"""
    geo_photos = [p for p in photos if p.has_geo]
    stops: list[Stop] = []
    current: list[Photo] = []

    for photo in geo_photos:
        if not current:
            current = [photo]
            continue
        previous = current[-1]
        moved = haversine_m(previous, photo) > radius_m
        elapsed = _minutes_between(previous.taken_at, photo.taken_at)
        if moved or (elapsed is not None and elapsed > gap_minutes):
            stops.append(_finalize(len(stops) + 1, current))
            current = [photo]
        else:
            current.append(photo)

    if current:
        stops.append(_finalize(len(stops) + 1, current))
    return stops


def _minutes_between(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None:
        return None
    if (a.tzinfo is None) != (b.tzinfo is None):
        return None  # naive と aware は比較できない
    return abs((b - a).total_seconds()) / 60.0


def _finalize(index: int, photos: list[Photo]) -> Stop:
    lat = sum(p.latitude for p in photos) / len(photos)
    lon = sum(p.longitude for p in photos) / len(photos)
    place = next((p.place for p in photos if p.place), None)
    return Stop(index=index, photos=list(photos), latitude=lat, longitude=lon, place=place)


def route_length_m(stops: list[Stop]) -> float:
    """スポット間を直線で結んだときの総移動距離。"""
    total = 0.0
    for a, b in zip(stops, stops[1:]):
        pa = Photo(id="", filename="", latitude=a.latitude, longitude=a.longitude)
        pb = Photo(id="", filename="", latitude=b.latitude, longitude=b.longitude)
        total += haversine_m(pa, pb)
    return total
