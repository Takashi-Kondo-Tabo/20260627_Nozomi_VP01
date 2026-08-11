"""サンプルデータ生成ユーティリティ。

Google アカウントや実写真が無くても、パイプライン全体
(抽出 → 逆ジオコーディング → 地図 → ドキュメント)を動かして確認できるように、
ジオタグ入りの PNG と Google Takeout 形式の JSON サイドカーを合成する。

EXIF ライタとしても働くので、``exif.py`` のラウンドトリップテストにも使っている。
"""

from __future__ import annotations

import json
import os
import struct
import zlib
from datetime import datetime, timedelta, timezone

# --- TIFF/EXIF ライタ ------------------------------------------------------

TYPE_ASCII, TYPE_SHORT, TYPE_LONG, TYPE_RATIONAL = 2, 3, 4, 5
_TYPE_SIZE = {TYPE_ASCII: 1, TYPE_SHORT: 2, TYPE_LONG: 4, TYPE_RATIONAL: 8}


def _ascii(text: str) -> tuple[int, int, bytes]:
    raw = text.encode("ascii", "replace") + b"\x00"
    return TYPE_ASCII, len(raw), raw


def _long(value: int) -> tuple[int, int, bytes]:
    return TYPE_LONG, 1, struct.pack(">I", value)


def _rationals(values: list[tuple[int, int]]) -> tuple[int, int, bytes]:
    return TYPE_RATIONAL, len(values), b"".join(struct.pack(">II", n, d) for n, d in values)


def _deg_to_dms(value: float) -> list[tuple[int, int]]:
    value = abs(value)
    degrees = int(value)
    minutes_f = (value - degrees) * 60
    minutes = int(minutes_f)
    seconds = (minutes_f - minutes) * 60
    return [(degrees, 1), (minutes, 1), (int(round(seconds * 10000)), 10000)]


def _pack_ifd(entries: list[tuple[int, int, int, bytes]], ifd_offset: int, data_offset: int):
    """1つの IFD をバイト列に。戻り値は (ifd_bytes, data_bytes, 次のデータ位置)。"""
    entries = sorted(entries, key=lambda e: e[0])
    out = struct.pack(">H", len(entries))
    blob = b""
    cursor = data_offset
    for tag, typ, count, payload in entries:
        assert len(payload) == _TYPE_SIZE[typ] * count, f"tag {tag:#x} のサイズ不整合"
        if len(payload) <= 4:
            value_field = payload.ljust(4, b"\x00")
        else:
            value_field = struct.pack(">I", cursor)
            padded = payload + (b"\x00" if len(payload) % 2 else b"")
            blob += padded
            cursor += len(padded)
        out += struct.pack(">HHI", tag, typ, count) + value_field
    out += struct.pack(">I", 0)  # 次の IFD は無い
    assert len(out) == 2 + len(entries) * 12 + 4
    return out, blob, cursor


def build_exif(
    latitude: float,
    longitude: float,
    taken_at: datetime,
    *,
    camera_make: str = "PhotoMap",
    camera_model: str = "Sample Cam",
    width: int = 320,
    height: int = 240,
    tz_offset: str = "+09:00",
) -> bytes:
    """緯度経度・撮影日時を含む TIFF(EXIF 本体)を組み立てる。"""
    gps_entries = [
        (0x0001, *_ascii("N" if latitude >= 0 else "S")),
        (0x0002, *_rationals(_deg_to_dms(latitude))),
        (0x0003, *_ascii("E" if longitude >= 0 else "W")),
        (0x0004, *_rationals(_deg_to_dms(longitude))),
    ]
    exif_entries = [
        (0x9003, *_ascii(taken_at.strftime("%Y:%m:%d %H:%M:%S"))),
        (0x9011, *_ascii(tz_offset)),
        (0xA002, *_long(width)),
        (0xA003, *_long(height)),
    ]

    ifd0_size = 2 + 4 * 12 + 4
    exif_size = 2 + len(exif_entries) * 12 + 4
    gps_size = 2 + len(gps_entries) * 12 + 4

    ifd0_offset = 8
    exif_offset = ifd0_offset + ifd0_size
    gps_offset = exif_offset + exif_size
    data_offset = gps_offset + gps_size

    ifd0_entries = [
        (0x010F, *_ascii(camera_make)),
        (0x0110, *_ascii(camera_model)),
        (0x8769, *_long(exif_offset)),
        (0x8825, *_long(gps_offset)),
    ]

    ifd0_bytes, blob0, cursor = _pack_ifd(ifd0_entries, ifd0_offset, data_offset)
    exif_bytes, blob1, cursor = _pack_ifd(exif_entries, exif_offset, cursor)
    gps_bytes, blob2, _ = _pack_ifd(gps_entries, gps_offset, cursor)

    return (
        b"MM"
        + struct.pack(">HI", 42, ifd0_offset)
        + ifd0_bytes
        + exif_bytes
        + gps_bytes
        + blob0
        + blob1
        + blob2
    )


# --- PNG ライタ ------------------------------------------------------------


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def write_png(path: str, width: int, height: int, hue: int, exif: bytes | None = None) -> None:
    """グラデーションの PNG を書き出す(必要なら eXIf チャンク付き)。"""
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # フィルタ種別: None
        for x in range(width):
            rows += bytes(
                (
                    (hue * 37 + x * 255 // max(1, width - 1)) % 256,
                    (hue * 91 + y * 255 // max(1, height - 1)) % 256,
                    (hue * 53 + (x + y) % 256) % 256,
                )
            )
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    parts = [b"\x89PNG\r\n\x1a\n", _chunk(b"IHDR", ihdr)]
    if exif:
        parts.append(_chunk(b"eXIf", exif))
    parts.append(_chunk(b"IDAT", zlib.compress(bytes(rows), 6)))
    parts.append(_chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"".join(parts))


# --- Takeout 形式のサンプル一式 --------------------------------------------

# 京都の一日を想定した行程(緯度, 経度, 場所名, 出発からの経過分)
SAMPLE_ROUTE = [
    (34.9858, 135.7588, "京都駅", 0),
    (34.9871, 135.7590, "京都駅ビル 大階段", 18),
    (34.9948, 135.7850, "清水寺 参道", 75),
    (34.9949, 135.7849, "清水の舞台", 92),
    (35.0037, 135.7780, "八坂神社", 160),
    (35.0116, 135.7681, "鴨川 三条大橋", 215),
    (35.0394, 135.7292, "金閣寺", 320),
    (34.9858, 135.7588, "京都駅(帰路)", 430),
]


def make_sample_takeout(root: str, day: str = "2026-06-27", tz_hours: int = 9) -> str:
    """Takeout 相当のディレクトリを合成し、そのルートパスを返す。"""
    base_date = datetime.fromisoformat(day)
    tz = timezone(timedelta(hours=tz_hours))
    folder = os.path.join(root, "Takeout", "Google フォト", f"Photos from {base_date.year}")
    os.makedirs(folder, exist_ok=True)

    for i, (lat, lon, name, minutes) in enumerate(SAMPLE_ROUTE):
        taken_local = base_date.replace(hour=9, minute=10, tzinfo=tz) + timedelta(minutes=minutes)
        filename = f"IMG_{1000 + i}.png"
        image_path = os.path.join(folder, filename)

        # 3枚に1枚はジオタグ無し(位置情報を削除した写真の再現)
        has_geo = i % 4 != 3
        exif = (
            build_exif(
                lat,
                lon,
                taken_local.replace(tzinfo=None),
                tz_offset=f"+{tz_hours:02d}:00",
            )
            if has_geo
            else None
        )
        write_png(image_path, 480, 320, hue=i * 7 + 3, exif=exif)

        sidecar = {
            "title": filename,
            "description": f"{name}で撮影(サンプルデータ)",
            "photoTakenTime": {
                "timestamp": str(int(taken_local.timestamp())),
                "formatted": taken_local.isoformat(),
            },
            "geoData": (
                {"latitude": lat, "longitude": lon, "altitude": 0.0}
                if has_geo
                else {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0}
            ),
            "geoDataExif": {"latitude": lat if has_geo else 0.0, "longitude": lon if has_geo else 0.0},
        }
        with open(
            os.path.join(folder, f"{filename}.supplemental-metadata.json"), "w", encoding="utf-8"
        ) as fh:
            json.dump(sidecar, fh, ensure_ascii=False, indent=1)

    return os.path.join(root, "Takeout")
