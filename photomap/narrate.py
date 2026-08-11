"""写真につける「解説」を生成する。

2段構え:

1. ``RuleNarrator``  — メタデータだけから日本語のキャプションを組み立てる。
   ネットワークもAPIキーも不要で、必ず何かしらの説明が付く。
2. ``ClaudeNarrator`` — Anthropic API(Claude)で、その日の流れを踏まえた
   自然な解説と全体サマリを書かせる。``--vision`` を付けると写真そのものも
   見せるので、被写体に踏み込んだ解説になる。
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
from datetime import datetime

from .cluster import Stop, route_length_m
from .models import Photo

MODEL = "claude-opus-5"
MAX_VISION_IMAGES = 20
MAX_IMAGE_BYTES = 4 * 1024 * 1024
VISION_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}


# --- 共通の下ごしらえ ------------------------------------------------------


def _time_of_day(dt: datetime | None) -> str:
    if dt is None:
        return ""
    hour = dt.hour
    if hour < 5:
        return "深夜"
    if hour < 9:
        return "早朝"
    if hour < 12:
        return "午前"
    if hour < 15:
        return "昼過ぎ"
    if hour < 18:
        return "夕方"
    if hour < 21:
        return "夜"
    return "夜更け"


def _clock(dt: datetime | None) -> str:
    return dt.strftime("%H:%M") if dt else "時刻不明"


class RuleNarrator:
    """メタデータから機械的に日本語キャプションを組む。"""

    def narrate(self, photos: list[Photo], stops: list[Stop]) -> dict:
        previous: Photo | None = None
        for photo in photos:
            photo.caption = self._caption(photo, previous)
            previous = photo
        for stop in stops:
            stop.summary = self._stop_summary(stop)
        return {
            "title": self._title(photos, stops),
            "summary": self._day_summary(photos, stops),
        }

    def _caption(self, photo: Photo, previous: Photo | None) -> str:
        parts: list[str] = []
        when = _time_of_day(photo.taken_at)
        where = photo.place.label() if photo.place else ""
        if when and where:
            parts.append(f"{when}の{where}にて。")
        elif where:
            parts.append(f"{where}にて。")
        elif when:
            parts.append(f"{when}の一枚。")

        if photo.description:
            parts.append(photo.description.strip())

        if photo.place and photo.place.address and photo.place.address != where:
            parts.append(f"住所の目安は{photo.place.address}。")

        if not photo.has_geo:
            parts.append("この写真にはジオタグが無いため、地図上には配置していません。")

        camera = " ".join(x for x in (photo.camera_make, photo.camera_model) if x).strip()
        if camera:
            parts.append(f"撮影機材は {camera}。")

        if previous and previous.taken_at and photo.taken_at:
            gap = _safe_minutes(previous.taken_at, photo.taken_at)
            if gap is not None and gap >= 60:
                parts.append(f"前の一枚から約{int(gap // 60)}時間ぶりの撮影。")
        return " ".join(parts).strip()

    def _stop_summary(self, stop: Stop) -> str:
        span = f"{_clock(stop.start)}〜{_clock(stop.end)}"
        base = f"{span} に {len(stop.photos)} 枚。"
        if stop.place and stop.place.address:
            return base + f" {stop.place.address}"
        return base

    def _title(self, photos: list[Photo], stops: list[Stop]) -> str:
        date_label = ""
        for photo in photos:
            if photo.taken_at:
                date_label = photo.taken_at.strftime("%Y年%m月%d日")
                break
        head = next((s.label for s in stops if s.place), "")
        if date_label and head:
            return f"{date_label} — {head}を巡る一日"
        return date_label or "写真の記録"

    def _day_summary(self, photos: list[Photo], stops: list[Stop]) -> str:
        geo = [p for p in photos if p.has_geo]
        lines = [f"合計 {len(photos)} 枚のうち、{len(geo)} 枚にジオタグがありました。"]
        if stops:
            distance = route_length_m(stops) / 1000.0
            names = [s.label for s in stops[:6]]
            lines.append(
                f"立ち寄り地点は {len(stops)} か所({' → '.join(names)}"
                + ("…" if len(stops) > 6 else "")
                + f")、地点間の直線距離の合計は約 {distance:.1f} km です。"
            )
        times = [p.taken_at for p in photos if p.taken_at]
        if times:
            lines.append(f"撮影は {_clock(min(times))} から {_clock(max(times))} まで続きました。")
        return " ".join(lines)


def _safe_minutes(a: datetime, b: datetime) -> float | None:
    if (a.tzinfo is None) != (b.tzinfo is None):
        return None
    return abs((b - a).total_seconds()) / 60.0


# --- Claude による解説 -----------------------------------------------------

_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "ドキュメント全体のタイトル(30字以内)"},
        "summary": {
            "type": "string",
            "description": "その日の行程全体をまとめた導入文(200〜400字)",
        },
        "photos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "description": "入力で与えた通し番号"},
                    "caption": {
                        "type": "string",
                        "description": "その写真の解説(80〜150字の日本語)",
                    },
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["index", "caption", "tags"],
                "additionalProperties": False,
            },
        },
        "stops": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "summary": {"type": "string", "description": "その地点の紹介(60〜120字)"},
                },
                "required": ["index", "summary"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "summary", "photos", "stops"],
    "additionalProperties": False,
}

_SYSTEM = """あなたは旅の記録を編集するライターです。写真のメタデータ(撮影時刻・
緯度経度・逆ジオコーディングした地名・カメラ)と、必要に応じて写真そのものを
受け取り、地図付きドキュメントに載せる日本語の解説を書きます。

守ること:
- メタデータから確実に言えることだけを書く。訪問の目的、同行者、食べたもの、
  天候などをメタデータや画像から確認できないまま断定しない。
- 地名は与えられたものを使い、勝手に別の名所名に置き換えない。
- 前後の写真とのつながり(移動、時間の経過、同じ場所での滞在)に触れて、
  一日の流れが読み取れるようにする。
- 常体ではなく、落ち着いた敬体で書く。絵文字と誇張表現は使わない。
"""


class ClaudeNarrator:
    """Anthropic API で解説を書かせる。失敗時はルールベースにフォールバックする。"""

    def __init__(self, model: str = MODEL, use_vision: bool = False, effort: str = "high"):
        self.model = model
        self.use_vision = use_vision
        self.effort = effort
        self.fallback = RuleNarrator()

    def narrate(self, photos: list[Photo], stops: list[Stop]) -> dict:
        meta = self.fallback.narrate(photos, stops)  # まず必ず埋めておく
        try:
            import anthropic
        except ImportError:
            print("! anthropic パッケージが無いため、ルールベースの解説を使います "
                  "(pip install anthropic)")
            return meta

        try:
            client = anthropic.Anthropic()
            result = self._request(client, photos, stops)
        except Exception as exc:  # noqa: BLE001 - 解説生成の失敗で全体を落とさない
            print(f"! Claude による解説生成に失敗しました({exc})。ルールベースの解説を使います。")
            return meta

        self._apply(result, photos, stops)
        return {
            "title": result.get("title") or meta["title"],
            "summary": result.get("summary") or meta["summary"],
        }

    # --- 内部 ---
    def _request(self, client, photos: list[Photo], stops: list[Stop]) -> dict:
        content: list[dict] = [{"type": "text", "text": self._prompt(photos, stops)}]
        if self.use_vision:
            content.extend(self._image_blocks(photos))
        messages = [{"role": "user", "content": content}]

        try:
            # 安全性分類器に弾かれた場合にサーバ側で別モデルへ切り替えてもらう
            message = self._stream(client.beta.messages, messages, with_fallback=True)
        except (AttributeError, TypeError):
            # 古い anthropic SDK ではベータ引数を受け付けないので通常経路で再試行
            message = self._stream(client.messages, messages, with_fallback=False)

        if message.stop_reason == "refusal":
            raise RuntimeError("モデルが応答を拒否しました")
        text = next((b.text for b in message.content if b.type == "text"), "")
        return json.loads(text)

    def _stream(self, endpoint, messages: list[dict], with_fallback: bool):
        kwargs = {
            "model": self.model,
            "max_tokens": 32000,
            "system": _SYSTEM,
            "thinking": {"type": "adaptive"},
            "output_config": {
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": _SCHEMA},
            },
            "messages": messages,
        }
        if with_fallback:
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["fallbacks"] = "default"
        with endpoint.stream(**kwargs) as stream:
            return stream.get_final_message()

    def _prompt(self, photos: list[Photo], stops: list[Stop]) -> str:
        rows = []
        for i, photo in enumerate(photos):
            place = photo.place.label() if photo.place else ""
            address = photo.place.address if photo.place else ""
            rows.append(
                {
                    "index": i,
                    "filename": photo.filename,
                    "taken_at": photo.taken_at.isoformat() if photo.taken_at else None,
                    "latitude": photo.latitude,
                    "longitude": photo.longitude,
                    "place": place,
                    "address": address,
                    "camera": " ".join(
                        x for x in (photo.camera_make, photo.camera_model) if x
                    ).strip(),
                    "user_description": photo.description,
                }
            )
        stop_rows = [
            {
                "index": s.index,
                "label": s.label,
                "photo_indexes": [photos.index(p) for p in s.photos],
                "start": s.start.isoformat() if s.start else None,
                "end": s.end.isoformat() if s.end else None,
            }
            for s in stops
        ]
        vision_note = (
            "写真そのものも添付しています(番号順)。写っているものに触れて構いません。"
            if self.use_vision
            else "画像は添付していません。メタデータから言えることだけを書いてください。"
        )
        return (
            "以下は同じ日に撮影された写真のメタデータです。"
            f"{vision_note}\n\n"
            f"## 写真\n```json\n{json.dumps(rows, ensure_ascii=False, indent=1)}\n```\n\n"
            f"## 立ち寄り地点(近接する写真をまとめたもの)\n"
            f"```json\n{json.dumps(stop_rows, ensure_ascii=False, indent=1)}\n```\n\n"
            "すべての写真に1件ずつ解説を、すべての地点に1件ずつ紹介文を書いてください。"
            "index は入力の番号をそのまま返してください。"
        )

    def _image_blocks(self, photos: list[Photo]) -> list[dict]:
        blocks: list[dict] = []
        step = max(1, len(photos) // MAX_VISION_IMAGES)
        for i, photo in enumerate(photos[::step][:MAX_VISION_IMAGES]):
            path = photo.thumb_path or photo.source_path
            if not path or not os.path.exists(path):
                continue
            mime = mimetypes.guess_type(path)[0] or ""
            if mime not in VISION_MIME or os.path.getsize(path) > MAX_IMAGE_BYTES:
                continue
            with open(path, "rb") as fh:
                data = base64.standard_b64encode(fh.read()).decode("ascii")
            blocks.append(
                {"type": "text", "text": f"[index {i * step}] {photo.filename}"}
            )
            blocks.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": mime, "data": data},
                }
            )
        return blocks

    def _apply(self, result: dict, photos: list[Photo], stops: list[Stop]) -> None:
        for entry in result.get("photos", []):
            idx = entry.get("index")
            if isinstance(idx, int) and 0 <= idx < len(photos) and entry.get("caption"):
                photos[idx].caption = entry["caption"].strip()
                tags = entry.get("tags")
                if isinstance(tags, list):
                    photos[idx].tags = [str(t) for t in tags][:6]
        by_index = {s.index: s for s in stops}
        for entry in result.get("stops", []):
            stop = by_index.get(entry.get("index"))
            if stop and entry.get("summary"):
                stop.summary = entry["summary"].strip()
