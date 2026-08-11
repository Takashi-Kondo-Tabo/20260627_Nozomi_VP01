"""Google フォト API から写真を取得する。

重要な前提(2025-03-31 の仕様変更):

* Library API の ``photoslibrary.readonly`` では、もはやユーザーのライブラリ
  全体を読むことはできない(アプリが自分で作成したメディアのみ)。ユーザーが
  選んだ写真にアクセスする正式な経路は **Picker API**。
* ``mediaItems`` の ``mediaMetadata`` には **位置情報が含まれない**。
  そのため本モジュールは ``baseUrl=d`` でオリジナルをダウンロードし、
  そのファイルの EXIF から緯度経度を読み取る。
  (Google フォト側で「位置情報を削除」した写真には、そもそもジオタグが無い。)
"""

from __future__ import annotations

import os
import time
from datetime import datetime

from .. import exif as exif_mod
from ..google_auth import AuthError, Credentials, download, http_json
from ..models import Photo
from .base import DateWindow, sort_photos

PICKER_ROOT = "https://photospicker.googleapis.com/v1"
LIBRARY_ROOT = "https://photoslibrary.googleapis.com/v1"


# --- Picker API ----------------------------------------------------------


def create_picker_session(creds: Credentials) -> dict:
    return http_json(f"{PICKER_ROOT}/sessions", method="POST", token=creds.token(), body={})


def wait_for_selection(creds: Credentials, session: dict, timeout: int = 900) -> dict:
    """ユーザーが Picker で写真を選び終えるまでポーリングする。"""
    session_id = session["id"]
    interval = _duration_seconds(session.get("pollingConfig", {}).get("pollInterval"), 5.0)
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = http_json(f"{PICKER_ROOT}/sessions/{session_id}", token=creds.token())
        if current.get("mediaItemsSet"):
            return current
        interval = _duration_seconds(
            current.get("pollingConfig", {}).get("pollInterval"), interval
        )
        time.sleep(max(1.0, min(interval, 15.0)))
    raise AuthError("写真の選択がタイムアウトしました。")


def _duration_seconds(value: object, default: float) -> float:
    """protobuf Duration(``"5s"`` 形式)を秒に変換する。"""
    if isinstance(value, str) and value.endswith("s"):
        try:
            return float(value[:-1])
        except ValueError:
            return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def list_picked_items(creds: Credentials, session_id: str) -> list[dict]:
    items, page = [], None
    while True:
        url = f"{PICKER_ROOT}/mediaItems?sessionId={session_id}&pageSize=100"
        if page:
            url += f"&pageToken={page}"
        data = http_json(url, token=creds.token())
        items.extend(data.get("mediaItems", []))
        page = data.get("nextPageToken")
        if not page:
            return items


def delete_picker_session(creds: Credentials, session_id: str) -> None:
    try:
        http_json(f"{PICKER_ROOT}/sessions/{session_id}", method="DELETE", token=creds.token())
    except AuthError:
        pass  # 後片付けの失敗で処理を止めない


# --- Library API(レガシー) ---------------------------------------------


def search_library(creds: Credentials, window: DateWindow) -> list[dict]:
    start, end = window.start.date(), (window.end.date())
    body = {
        "pageSize": 100,
        "filters": {
            "dateFilter": {
                "ranges": [
                    {
                        "startDate": {
                            "year": start.year,
                            "month": start.month,
                            "day": start.day,
                        },
                        "endDate": {"year": end.year, "month": end.month, "day": end.day},
                    }
                ]
            }
        },
    }
    items, page = [], None
    while True:
        if page:
            body["pageToken"] = page
        data = http_json(
            f"{LIBRARY_ROOT}/mediaItems:search",
            method="POST",
            token=creds.token(),
            body=body,
        )
        items.extend(data.get("mediaItems", []))
        page = data.get("nextPageToken")
        if not page:
            return items


# --- 共通: ダウンロードして Photo に正規化 --------------------------------


def _normalize(item: dict) -> dict:
    """Picker API と Library API のレスポンス差を吸収する。"""
    media_file = item.get("mediaFile")
    if isinstance(media_file, dict):  # Picker API
        meta = media_file.get("mediaFileMetadata", {}) or {}
        return {
            "id": item.get("id", ""),
            "filename": media_file.get("filename") or f"{item.get('id', 'photo')}.jpg",
            "base_url": media_file.get("baseUrl", ""),
            "mime_type": media_file.get("mimeType", ""),
            "create_time": item.get("createTime", ""),
            "width": _as_int(meta.get("width")),
            "height": _as_int(meta.get("height")),
            "camera_make": meta.get("cameraMake", "") or "",
            "camera_model": meta.get("cameraModel", "") or "",
            "description": "",
        }
    meta = item.get("mediaMetadata", {}) or {}  # Library API
    photo_meta = meta.get("photo", {}) or {}
    return {
        "id": item.get("id", ""),
        "filename": item.get("filename") or f"{item.get('id', 'photo')}.jpg",
        "base_url": item.get("baseUrl", ""),
        "mime_type": item.get("mimeType", ""),
        "create_time": meta.get("creationTime", ""),
        "width": _as_int(meta.get("width")),
        "height": _as_int(meta.get("height")),
        "camera_make": photo_meta.get("cameraMake", "") or "",
        "camera_model": photo_meta.get("cameraModel", "") or "",
        "description": item.get("description", "") or "",
    }


def _as_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _parse_rfc3339(text: str) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch(
    creds: Credentials,
    items: list[dict],
    window: DateWindow,
    cache_dir: str,
    include_videos: bool = False,
) -> list[Photo]:
    """メディア項目をダウンロードし、EXIF を読んで `Photo` に変換する。"""
    os.makedirs(cache_dir, exist_ok=True)
    photos: list[Photo] = []

    for raw in items:
        item = _normalize(raw)
        if not include_videos and item["mime_type"].startswith("video/"):
            continue
        created = _parse_rfc3339(item["create_time"])
        if created and not window.contains(created):
            continue
        if not item["base_url"]:
            continue

        safe_name = f"{item['id'][:24]}_{os.path.basename(item['filename'])}".replace("/", "_")
        dest = os.path.join(cache_dir, safe_name)
        if not os.path.exists(dest):
            # "=d" でオリジナル(EXIF 込み)を取得する。"=w800-h800" 等はメタデータが落ちる
            download(item["base_url"] + "=d", dest, token=creds.token())

        tags = exif_mod.read_exif(dest)
        taken = tags.get("taken_at") or created
        if not window.contains(taken):
            continue

        photos.append(
            Photo(
                id=item["id"] or safe_name,
                filename=item["filename"],
                taken_at=taken,
                latitude=tags.get("latitude"),
                longitude=tags.get("longitude"),
                altitude=tags.get("altitude"),
                width=item["width"] or tags.get("width"),
                height=item["height"] or tags.get("height"),
                camera_make=item["camera_make"] or tags.get("camera_make", ""),
                camera_model=item["camera_model"] or tags.get("camera_model", ""),
                title=item["filename"],
                description=item["description"],
                source_path=dest,
                origin="google-photos",
            )
        )
    return sort_photos(photos)
