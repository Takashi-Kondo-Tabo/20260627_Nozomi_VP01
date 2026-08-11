"""逆ジオコーディング(緯度経度 → 地名)。結果はディスクにキャッシュする。

* ``google``: Google Geocoding API(``GOOGLE_MAPS_API_KEY`` が必要・高精度)
* ``osm``: OpenStreetMap Nominatim(キー不要・1リクエスト/秒の利用規約を遵守)
* ``none``: 逆ジオコーディングを行わない
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
from typing import Iterable

from .google_auth import AuthError, http_json
from .models import Photo, Place

NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
GOOGLE_GEOCODE = "https://maps.googleapis.com/maps/api/geocode/json"

# 同一地点とみなす丸め精度(小数4桁 ≒ 11m)
_PRECISION = 4


class Geocoder:
    def __init__(self, provider: str = "osm", api_key: str = "", cache_path: str = "", language: str = "ja"):
        self.provider = provider
        self.api_key = api_key
        self.language = language
        self.cache_path = cache_path or os.path.expanduser("~/.cache/photomap/geocode.json")
        self.cache: dict[str, dict] = {}
        self._last_call = 0.0
        self._load()

    # --- キャッシュ ---
    def _load(self) -> None:
        try:
            with open(self.cache_path, "r", encoding="utf-8") as fh:
                self.cache = json.load(fh)
        except (OSError, json.JSONDecodeError):
            self.cache = {}

    def save(self) -> None:
        if self.provider == "none":
            return
        os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
        try:
            with open(self.cache_path, "w", encoding="utf-8") as fh:
                json.dump(self.cache, fh, ensure_ascii=False)
        except OSError:
            pass

    # --- 本体 ---
    def lookup(self, lat: float, lon: float) -> Place | None:
        if self.provider == "none":
            return None
        key = f"{round(lat, _PRECISION)},{round(lon, _PRECISION)}"
        if key in self.cache:
            return Place(**self.cache[key])
        try:
            place = self._fetch(lat, lon)
        except (AuthError, KeyError, ValueError):
            return None
        if place is None:
            return None
        self.cache[key] = place.__dict__.copy()
        return place

    def annotate(self, photos: Iterable[Photo]) -> None:
        for photo in photos:
            if photo.has_geo and photo.place is None:
                photo.place = self.lookup(photo.latitude, photo.longitude)
        self.save()

    def _throttle(self, min_interval: float) -> None:
        wait = min_interval - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.time()

    def _fetch(self, lat: float, lon: float) -> Place | None:
        if self.provider == "google":
            return self._fetch_google(lat, lon)
        return self._fetch_osm(lat, lon)

    def _fetch_google(self, lat: float, lon: float) -> Place | None:
        if not self.api_key:
            raise AuthError("Google 逆ジオコーディングには GOOGLE_MAPS_API_KEY が必要です。")
        self._throttle(0.05)
        query = urllib.parse.urlencode(
            {"latlng": f"{lat},{lon}", "key": self.api_key, "language": self.language}
        )
        data = http_json(f"{GOOGLE_GEOCODE}?{query}")
        results = data.get("results") or []
        if not results:
            return None
        best = results[0]
        parts = {
            comp_type: comp.get("long_name", "")
            for comp in best.get("address_components", [])
            for comp_type in comp.get("types", [])
        }
        name = (
            parts.get("point_of_interest")
            or parts.get("premise")
            or parts.get("sublocality_level_1")
            or parts.get("locality")
            or ""
        )
        return Place(
            name=name,
            address=best.get("formatted_address", ""),
            locality=parts.get("locality", "") or parts.get("sublocality_level_1", ""),
            admin_area=parts.get("administrative_area_level_1", ""),
            country=parts.get("country", ""),
        )

    def _fetch_osm(self, lat: float, lon: float) -> Place | None:
        self._throttle(1.1)  # Nominatim の利用規約: 最大 1req/s
        query = urllib.parse.urlencode(
            {
                "lat": f"{lat}",
                "lon": f"{lon}",
                "format": "jsonv2",
                "zoom": "17",
                "addressdetails": "1",
                "accept-language": self.language,
            }
        )
        # http_json は User-Agent を付けないため、ここだけ明示的に組み立てる
        import urllib.request

        req = urllib.request.Request(
            f"{NOMINATIM}?{query}",
            headers={
                "User-Agent": "photomap/1.0 (https://github.com/; Google Photos map document builder)",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
        except Exception:  # noqa: BLE001 - 逆ジオコーディングは best-effort
            return None
        addr = data.get("address", {}) or {}
        locality = (
            addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or addr.get("suburb")
            or addr.get("county")
            or ""
        )
        name = data.get("name") or addr.get("amenity") or addr.get("neighbourhood") or locality
        return Place(
            name=name or "",
            address=data.get("display_name", ""),
            locality=locality,
            admin_area=addr.get("state", "") or addr.get("province", ""),
            country=addr.get("country", ""),
        )
