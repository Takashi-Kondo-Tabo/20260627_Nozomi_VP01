"""ローカルフォルダの画像を EXIF だけで読み込む。

Google フォトからスマホやPCに書き出したフォルダ、あるいは
Picker API 経由でダウンロードしたキャッシュを対象にできる。
"""

from __future__ import annotations

import os

from .. import exif as exif_mod
from ..models import Photo
from .base import DateWindow, is_image, sort_photos


def collect(root: str, window: DateWindow, recursive: bool = True) -> list[Photo]:
    root = os.path.expanduser(root)
    if not os.path.isdir(root):
        raise FileNotFoundError(f"フォルダが見つかりません: {root}")

    paths: list[str] = []
    if recursive:
        for dirpath, _dirnames, filenames in os.walk(root):
            paths.extend(os.path.join(dirpath, n) for n in filenames if is_image(n))
    else:
        paths = [
            os.path.join(root, n)
            for n in os.listdir(root)
            if is_image(n) and os.path.isfile(os.path.join(root, n))
        ]

    photos = []
    for path in sorted(paths):
        tags = exif_mod.read_exif(path)
        taken = tags.get("taken_at")
        if taken is None:
            # EXIF が無ければファイルの更新時刻で代用する
            from datetime import datetime

            taken = datetime.fromtimestamp(os.path.getmtime(path))
        if not window.contains(taken):
            continue
        photos.append(
            Photo(
                id=os.path.relpath(path, root),
                filename=os.path.basename(path),
                taken_at=taken,
                latitude=tags.get("latitude"),
                longitude=tags.get("longitude"),
                altitude=tags.get("altitude"),
                width=tags.get("width"),
                height=tags.get("height"),
                camera_make=tags.get("camera_make", ""),
                camera_model=tags.get("camera_model", ""),
                title=os.path.basename(path),
                source_path=path,
                origin="local",
            )
        )
    return sort_photos(photos)
