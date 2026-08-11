"""ドキュメントから参照する画像を出力ディレクトリに用意する。

Pillow があればサムネイルを生成し、無ければ元ファイルをコピーする。
どちらも失敗した場合は画像なしのドキュメントとして成立させる。
"""

from __future__ import annotations

import os
import shutil

from .models import Photo

THUMB_MAX = 1280
DISPLAY_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}


def _pillow():
    try:
        from PIL import Image  # type: ignore

        return Image
    except ImportError:
        return None


def materialize(photos: list[Photo], out_dir: str, embed: bool = True) -> None:
    """各写真の ``asset_path``(HTML から参照する相対パス)を埋める。"""
    if not embed:
        return
    assets_dir = os.path.join(out_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)
    image_mod = _pillow()

    for i, photo in enumerate(photos):
        src = photo.source_path
        if not src or not os.path.exists(src):
            continue
        stem = f"{i:03d}_{_safe_name(photo.filename)}"
        if image_mod is not None:
            dest = os.path.join(assets_dir, os.path.splitext(stem)[0] + ".jpg")
            if _thumbnail(image_mod, src, dest):
                photo.asset_path = os.path.relpath(dest, out_dir).replace(os.sep, "/")
                photo.thumb_path = dest
                continue
        # フォールバック: 表示できる形式ならそのままコピー
        if os.path.splitext(src)[1].lower() in DISPLAY_EXTS:
            dest = os.path.join(assets_dir, stem)
            try:
                if not os.path.exists(dest):
                    shutil.copy2(src, dest)
                photo.asset_path = os.path.relpath(dest, out_dir).replace(os.sep, "/")
                photo.thumb_path = dest
            except OSError:
                pass


def _thumbnail(image_mod, src: str, dest: str) -> bool:
    if os.path.exists(dest):
        return True
    try:
        with image_mod.open(src) as img:
            img = _apply_orientation(img)
            img.thumbnail((THUMB_MAX, THUMB_MAX))
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(dest, "JPEG", quality=82, optimize=True)
        return True
    except Exception:  # noqa: BLE001 - HEIC など未対応形式はコピーにフォールバック
        return False


def _apply_orientation(img):
    """EXIF Orientation に従って回転させる(Pillow の ImageOps があれば利用)。"""
    try:
        from PIL import ImageOps  # type: ignore

        return ImageOps.exif_transpose(img)
    except Exception:  # noqa: BLE001
        return img


def _safe_name(name: str) -> str:
    keep = "-_."
    cleaned = "".join(c if c.isalnum() or c in keep else "_" for c in name)
    return cleaned[:80] or "photo.jpg"
