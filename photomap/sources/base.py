"""取得元(ソース)共通のユーティリティ。"""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from ..models import Photo

IMAGE_EXTS = {
    ".jpg",
    ".jpeg",
    ".jpe",
    ".png",
    ".heic",
    ".heif",
    ".webp",
    ".tif",
    ".tiff",
    ".dng",
    ".avif",
}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".3gp", ".avi", ".mkv"}


class DateWindow:
    """「この日の写真」を判定するローカル時刻の範囲。"""

    def __init__(self, start: date, end: date | None, tz: str):
        self.tz = ZoneInfo(tz)
        self.start = datetime.combine(start, time.min, tzinfo=self.tz)
        last = end or start
        self.end = datetime.combine(last, time.min, tzinfo=self.tz) + timedelta(days=1)

    @classmethod
    def parse(cls, start: str, end: str | None, tz: str) -> "DateWindow":
        s = date.fromisoformat(start)
        e = date.fromisoformat(end) if end else None
        if e and e < s:
            raise ValueError(f"--end-date ({end}) が --date ({start}) より前です")
        return cls(s, e, tz)

    def localize(self, dt: datetime) -> datetime:
        """naive な日時は「現地時刻そのもの」とみなし、aware ならタイムゾーン変換する。"""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=self.tz)
        return dt.astimezone(self.tz)

    def contains(self, dt: datetime | None) -> bool:
        if dt is None:
            return False
        return self.start <= self.localize(dt) < self.end

    def __str__(self) -> str:
        last = (self.end - timedelta(days=1)).date()
        if last == self.start.date():
            return self.start.date().isoformat()
        return f"{self.start.date().isoformat()} 〜 {last.isoformat()}"


def is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in IMAGE_EXTS


def is_media(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in IMAGE_EXTS or ext in VIDEO_EXTS


def sort_key(photo: Photo) -> tuple[int, float, str]:
    """naive / aware が混在しても比較できるソートキー。"""
    dt = photo.taken_at
    if dt is None:
        return (1, 0.0, photo.filename)
    if dt.tzinfo is None:
        # naive 同士・aware 同士の比較しかできないので、素の壁時計として数値化する
        stamp = (dt - datetime(1970, 1, 1)).total_seconds()
    else:
        stamp = dt.timestamp()
    return (0, stamp, photo.filename)


def sort_photos(photos: list[Photo]) -> list[Photo]:
    """撮影時刻順。時刻不明のものは末尾へ。"""
    return sorted(photos, key=sort_key)


def normalize_times(photos: list[Photo], window: DateWindow) -> list[Photo]:
    """撮影時刻を表示用タイムゾーンに揃える。

    取得元によって時刻の持ち方が違う(Takeout は UTC エポック、EXIF は
    現地の壁時計)。揃えておかないと「09:10 に撮った写真が 00:10 と表示される」
    といったズレや、naive/aware 混在による比較エラーが起きる。
    """
    for photo in photos:
        if photo.taken_at is not None:
            photo.taken_at = window.localize(photo.taken_at)
    return sort_photos(photos)
