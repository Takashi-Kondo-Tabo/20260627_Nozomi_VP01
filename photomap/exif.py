"""依存パッケージなしの EXIF リーダ(GPS・撮影日時・カメラ情報)。

Google フォトの API はロケーション情報を返さないため、ジオタグは
「オリジナル画像の EXIF」か「Takeout の JSON サイドカー」から取る必要がある。
このモジュールは前者を担当する。

対応:
  * JPEG (APP1 / Exif)
  * それ以外(HEIC, TIFF, WebP など)は先頭数MBから ``Exif\\x00\\x00`` を
    総当たりで探すフォールバック。多くの端末の HEIC はこれで読める。
"""

from __future__ import annotations

import struct
from datetime import datetime, timedelta, timezone
from typing import Any

# --- TIFF タグ番号 -------------------------------------------------------
TAG_MAKE = 0x010F
TAG_MODEL = 0x0110
TAG_ORIENTATION = 0x0112
TAG_DATETIME = 0x0132
TAG_EXIF_IFD = 0x8769
TAG_GPS_IFD = 0x8825

TAG_EXIF_IMAGE_WIDTH = 0xA002
TAG_EXIF_IMAGE_HEIGHT = 0xA003
TAG_DATETIME_ORIGINAL = 0x9003
TAG_DATETIME_DIGITIZED = 0x9004
TAG_OFFSET_TIME_ORIGINAL = 0x9011

GPS_LAT_REF, GPS_LAT = 0x0001, 0x0002
GPS_LON_REF, GPS_LON = 0x0003, 0x0004
GPS_ALT_REF, GPS_ALT = 0x0005, 0x0006
GPS_TIMESTAMP, GPS_DATESTAMP = 0x0007, 0x001D

_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}

MAX_SCAN_BYTES = 8 * 1024 * 1024


class ExifError(Exception):
    pass


# --- JPEG セグメント走査 --------------------------------------------------


def _extract_exif_from_jpeg(data: bytes) -> bytes | None:
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    n = len(data)
    while i + 4 <= n:
        # 0xFF のフィルバイトを読み飛ばす
        if data[i] != 0xFF:
            i += 1
            continue
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            return None
        marker = data[i]
        i += 1
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            continue  # 長さフィールドを持たないマーカー
        if marker in (0xDA, 0xD9):
            return None  # 画像データ開始/終端。ここから先に EXIF は無い
        if i + 2 > n:
            return None
        (length,) = struct.unpack_from(">H", data, i)
        payload = data[i + 2 : i + length]
        i += length
        if marker == 0xE1 and payload[:6] == b"Exif\x00\x00":
            return payload[6:]
    return None


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _extract_exif_from_png(data: bytes) -> bytes | None:
    """PNG の ``eXIf`` チャンク(生の TIFF データ)を取り出す。"""
    if data[:8] != PNG_SIGNATURE:
        return None
    i = 8
    n = len(data)
    while i + 8 <= n:
        (length,) = struct.unpack_from(">I", data, i)
        chunk_type = data[i + 4 : i + 8]
        payload = data[i + 8 : i + 8 + length]
        if chunk_type == b"eXIf":
            # 前置きの "Exif\0\0" を付ける書き出し実装もあるので両方受ける
            return payload[6:] if payload[:6] == b"Exif\x00\x00" else payload
        if chunk_type == b"IDAT":
            return None  # 画像データに入ったら、以降にメタデータは無いとみなす
        i += 12 + length  # length + type + data + CRC
    return None


def _extract_exif_bruteforce(data: bytes) -> bytes | None:
    idx = data.find(b"Exif\x00\x00")
    while idx != -1:
        tiff = data[idx + 6 :]
        if tiff[:2] in (b"II", b"MM"):
            return tiff
        idx = data.find(b"Exif\x00\x00", idx + 1)
    return None


# --- TIFF/IFD パース -----------------------------------------------------


def _read_ifd(buf: bytes, offset: int, endian: str, depth: int = 0) -> dict[int, Any]:
    """IFD を1つ読み、{タグ番号: 値} を返す。"""
    out: dict[int, Any] = {}
    if depth > 4 or offset <= 0 or offset + 2 > len(buf):
        return out
    (count,) = struct.unpack_from(endian + "H", buf, offset)
    # 壊れたファイルで巨大な count を掴まないようガード
    if count > 4096:
        return out
    for k in range(count):
        entry = offset + 2 + k * 12
        if entry + 12 > len(buf):
            break
        tag, typ, n = struct.unpack_from(endian + "HHI", buf, entry)
        size = _TYPE_SIZES.get(typ)
        if size is None:
            continue
        total = size * n
        if total > 4:
            (value_off,) = struct.unpack_from(endian + "I", buf, entry + 8)
        else:
            value_off = entry + 8
        if value_off + total > len(buf) or total < 0:
            continue
        raw = buf[value_off : value_off + total]
        out[tag] = _decode_value(raw, typ, n, endian)
    return out


def _decode_value(raw: bytes, typ: int, n: int, endian: str) -> Any:
    if typ == 2:  # ASCII
        return raw.split(b"\x00", 1)[0].decode("utf-8", "replace").strip()
    if typ in (1, 6, 7):  # BYTE / SBYTE / UNDEFINED
        return raw if n > 1 else raw[0]
    fmt = {3: "H", 8: "h", 4: "I", 9: "i"}.get(typ)
    if fmt:
        vals = struct.unpack(endian + fmt * n, raw)
        return vals[0] if n == 1 else list(vals)
    if typ in (5, 10):  # RATIONAL / SRATIONAL
        fmt = "II" if typ == 5 else "ii"
        nums = struct.unpack(endian + fmt * n, raw)
        pairs = [
            (nums[i], nums[i + 1]) for i in range(0, len(nums), 2)
        ]
        rats = [(num / den) if den else 0.0 for num, den in pairs]
        return rats[0] if n == 1 else rats
    if typ in (11, 12):  # FLOAT / DOUBLE
        fmt = "f" if typ == 11 else "d"
        vals = struct.unpack(endian + fmt * n, raw)
        return vals[0] if n == 1 else list(vals)
    return raw


def _dms_to_deg(value: Any, ref: Any) -> float | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    deg = float(value[0])
    minutes = float(value[1])
    seconds = float(value[2]) if len(value) > 2 else 0.0
    dec = deg + minutes / 60.0 + seconds / 3600.0
    if isinstance(ref, bytes):
        ref = ref.decode("ascii", "replace")
    if isinstance(ref, str) and ref.upper().startswith(("S", "W")):
        dec = -dec
    return dec


def _parse_exif_datetime(text: Any) -> datetime | None:
    if not isinstance(text, str) or not text.strip():
        return None
    text = text.strip().replace("/", ":")
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y:%m:%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[: len(fmt) + 4], fmt)
        except ValueError:
            continue
    return None


def _parse_offset(text: Any) -> timezone | None:
    """``+09:00`` 形式のタイムゾーンオフセットを解釈する。"""
    if not isinstance(text, str) or len(text) < 6 or text[0] not in "+-":
        return None
    try:
        hours, minutes = int(text[1:3]), int(text[4:6])
    except ValueError:
        return None
    delta = timedelta(hours=hours, minutes=minutes)
    return timezone(-delta if text[0] == "-" else delta)


# --- 公開 API -------------------------------------------------------------


def read_exif(path: str) -> dict[str, Any]:
    """画像ファイルから必要なメタデータだけを抜き出す。

    読めない/EXIF が無い場合は空の dict を返す(例外は投げない)。
    """
    try:
        with open(path, "rb") as fh:
            data = fh.read(MAX_SCAN_BYTES)
    except OSError:
        return {}
    return read_exif_bytes(data)


def read_exif_bytes(data: bytes) -> dict[str, Any]:
    tiff = (
        _extract_exif_from_jpeg(data)
        or _extract_exif_from_png(data)
        or _extract_exif_bruteforce(data)
    )
    if not tiff or len(tiff) < 8:
        return {}

    if tiff[:2] == b"II":
        endian = "<"
    elif tiff[:2] == b"MM":
        endian = ">"
    else:
        return {}
    magic, ifd0_off = struct.unpack_from(endian + "HI", tiff, 2)
    if magic != 42:
        return {}

    ifd0 = _read_ifd(tiff, ifd0_off, endian)
    exif_ifd = _read_ifd(tiff, ifd0.get(TAG_EXIF_IFD, 0) or 0, endian, 1)
    gps_ifd = _read_ifd(tiff, ifd0.get(TAG_GPS_IFD, 0) or 0, endian, 1)

    out: dict[str, Any] = {}

    make = ifd0.get(TAG_MAKE)
    model = ifd0.get(TAG_MODEL)
    if isinstance(make, str):
        out["camera_make"] = make
    if isinstance(model, str):
        out["camera_model"] = model
    if isinstance(ifd0.get(TAG_ORIENTATION), int):
        out["orientation"] = ifd0[TAG_ORIENTATION]

    for key, tag in (("width", TAG_EXIF_IMAGE_WIDTH), ("height", TAG_EXIF_IMAGE_HEIGHT)):
        val = exif_ifd.get(tag)
        if isinstance(val, int):
            out[key] = val

    taken = (
        _parse_exif_datetime(exif_ifd.get(TAG_DATETIME_ORIGINAL))
        or _parse_exif_datetime(exif_ifd.get(TAG_DATETIME_DIGITIZED))
        or _parse_exif_datetime(ifd0.get(TAG_DATETIME))
    )
    if taken:
        tz = _parse_offset(exif_ifd.get(TAG_OFFSET_TIME_ORIGINAL))
        if tz is not None:
            taken = taken.replace(tzinfo=tz)
        out["taken_at"] = taken

    lat = _dms_to_deg(gps_ifd.get(GPS_LAT), gps_ifd.get(GPS_LAT_REF))
    lon = _dms_to_deg(gps_ifd.get(GPS_LON), gps_ifd.get(GPS_LON_REF))
    if lat is not None and lon is not None:
        out["latitude"] = lat
        out["longitude"] = lon
    alt = gps_ifd.get(GPS_ALT)
    if isinstance(alt, (int, float)):
        ref = gps_ifd.get(GPS_ALT_REF)
        ref_val = ref[0] if isinstance(ref, bytes) and ref else ref
        out["altitude"] = -float(alt) if ref_val == 1 else float(alt)

    gps_dt = _gps_datetime(gps_ifd)
    if gps_dt:
        out["gps_datetime"] = gps_dt
    return out


def _gps_datetime(gps_ifd: dict[int, Any]) -> datetime | None:
    date_s = gps_ifd.get(GPS_DATESTAMP)
    time_v = gps_ifd.get(GPS_TIMESTAMP)
    if not isinstance(date_s, str) or not isinstance(time_v, (list, tuple)) or len(time_v) < 3:
        return None
    try:
        y, m, d = (int(x) for x in date_s.replace("-", ":").split(":")[:3])
        return datetime(
            y, m, d, int(time_v[0]), int(time_v[1]), int(time_v[2]), tzinfo=timezone.utc
        )
    except (ValueError, TypeError):
        return None
