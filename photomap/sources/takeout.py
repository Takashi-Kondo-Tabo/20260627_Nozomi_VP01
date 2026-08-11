"""Google Takeout(データエクスポート)から写真を読み込む。

**これが最も確実なジオタグ取得経路。** Google フォト Library API の
``mediaMetadata`` には位置情報が含まれないため、緯度経度を安定して得るには
Takeout の JSON サイドカー(``geoData``)を読むのが定石。

想定するディレクトリ構造::

    Takeout/Google フォト/Photos from 2026/IMG_0001.JPG
    Takeout/Google フォト/Photos from 2026/IMG_0001.JPG.supplemental-metadata.json
"""

from __future__ import annotations

import glob
import json
import os
from datetime import datetime, timezone

from .. import exif as exif_mod
from ..models import Photo
from .base import DateWindow, is_image, is_media, sort_photos


def _load_json(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _sidecar_candidates(media_path: str) -> list[str]:
    """Takeout のサイドカー命名ゆれを吸収した候補パス一覧。"""
    base, ext = os.path.splitext(media_path)
    cands = [
        f"{media_path}.json",
        f"{media_path}.supplemental-metadata.json",
        f"{base}.json",
    ]
    # "IMG_0001(1).JPG" は "IMG_0001.JPG(1).json" に化けることがある
    if base.endswith(")") and "(" in base:
        stem, _, dup = base.rpartition("(")
        cands.append(f"{stem}{ext}({dup}.json")
    # 長いファイル名は 46〜51 文字で切り詰められる
    cands.extend(sorted(glob.glob(glob.escape(media_path) + ".s*.json")))
    cands.extend(sorted(glob.glob(glob.escape(media_path[:46]) + "*.json")))
    seen, out = set(), []
    for c in cands:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _geo_from(meta: dict, key: str) -> tuple[float, float, float | None] | None:
    block = meta.get(key)
    if not isinstance(block, dict):
        return None
    lat, lon = block.get("latitude"), block.get("longitude")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    if abs(lat) < 1e-9 and abs(lon) < 1e-9:
        return None  # 位置情報を剥がされた写真は 0,0 で埋められている
    alt = block.get("altitude")
    return float(lat), float(lon), float(alt) if isinstance(alt, (int, float)) else None


def _taken_at(meta: dict) -> datetime | None:
    for key in ("photoTakenTime", "creationTime"):
        block = meta.get(key)
        if isinstance(block, dict) and block.get("timestamp"):
            try:
                return datetime.fromtimestamp(int(block["timestamp"]), tz=timezone.utc)
            except (ValueError, TypeError, OSError):
                continue
    return None


def collect(root: str, window: DateWindow, include_videos: bool = False) -> list[Photo]:
    root = os.path.expanduser(root)
    if not os.path.isdir(root):
        raise FileNotFoundError(f"Takeout ディレクトリが見つかりません: {root}")

    accept = is_media if include_videos else is_image
    # サイドカーが名前で引けなかったときのため、title -> json の索引を作る
    by_title: dict[tuple[str, str], dict] = {}
    media_files: list[str] = []

    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            if name.lower().endswith(".json"):
                meta = _load_json(path)
                title = (meta or {}).get("title")
                if meta and isinstance(title, str) and title:
                    by_title.setdefault((dirpath, title), meta)
            elif accept(name):
                media_files.append(path)

    photos: list[Photo] = []
    for path in sorted(media_files):
        dirpath, name = os.path.split(path)
        meta: dict = {}
        for cand in _sidecar_candidates(path):
            loaded = _load_json(cand) if os.path.exists(cand) else None
            if loaded:
                meta = loaded
                break
        if not meta:
            meta = by_title.get((dirpath, name), {})

        photo = _build_photo(path, meta)
        if window.contains(photo.taken_at):
            photos.append(photo)

    return sort_photos(photos)


def _build_photo(path: str, meta: dict) -> Photo:
    tags = exif_mod.read_exif(path) if is_image(path) else {}

    taken = _taken_at(meta) or tags.get("taken_at")
    geo = _geo_from(meta, "geoData") or _geo_from(meta, "geoDataExif")
    if geo is None and tags.get("latitude") is not None:
        geo = (tags["latitude"], tags["longitude"], tags.get("altitude"))

    description = meta.get("description") or ""
    people = meta.get("people")
    tag_list = [p["name"] for p in people if isinstance(p, dict) and p.get("name")] if isinstance(people, list) else []

    return Photo(
        id=os.path.relpath(path),
        filename=os.path.basename(path),
        taken_at=taken,
        latitude=geo[0] if geo else None,
        longitude=geo[1] if geo else None,
        altitude=geo[2] if geo else None,
        width=tags.get("width"),
        height=tags.get("height"),
        camera_make=tags.get("camera_make", ""),
        camera_model=tags.get("camera_model", ""),
        title=meta.get("title") or os.path.basename(path),
        description=description if isinstance(description, str) else "",
        source_path=path,
        tags=tag_list,
        origin="takeout",
    )
