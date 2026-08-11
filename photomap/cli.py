"""photomap — Google フォトの写真を日付で抽出し、地図付きドキュメントを作る。

使い方の例::

    # 1) Google Takeout を使う(最も確実にジオタグが取れる)
    photomap build --source takeout --path ~/Takeout --date 2026-06-27

    # 2) Google フォト Picker API を使う(ブラウザで写真を選択)
    photomap auth --client-secrets ~/client_secret.json
    photomap build --source picker --date 2026-06-27 --claude

    # 3) 手元のフォルダを使う
    photomap build --source local --path ~/Pictures/2026-06-27 --date 2026-06-27
"""

from __future__ import annotations

import argparse
import os
import sys

from . import assets as assets_mod
from . import google_auth
from .cluster import build_stops
from .geocode import Geocoder
from .models import Photo
from .narrate import ClaudeNarrator, RuleNarrator
from .render import geo as geo_render
from .render import html as html_render
from .render import markdown as md_render
from .sources import base as base_source
from .sources import google_photos, local, takeout
from .sources.base import DateWindow

DEFAULT_CACHE = os.path.expanduser("~/.cache/photomap/media")


# --- サブコマンド: auth ----------------------------------------------------


def cmd_auth(args: argparse.Namespace) -> int:
    scopes = [google_auth.SCOPE_PICKER]
    if args.library:
        scopes.append(google_auth.SCOPE_LIBRARY)
    creds = google_auth.authorize(
        args.client_secrets, scopes, args.token, open_browser=not args.no_browser
    )
    print(f"✓ 認証情報を保存しました: {creds.path}")
    return 0


# --- サブコマンド: build ---------------------------------------------------


def collect_photos(args: argparse.Namespace, window: DateWindow) -> list[Photo]:
    if args.source == "takeout":
        if not args.path:
            raise SystemExit("--source takeout には --path(Takeout の展開先)が必要です")
        return takeout.collect(args.path, window, include_videos=args.include_videos)

    if args.source == "local":
        if not args.path:
            raise SystemExit("--source local には --path(画像フォルダ)が必要です")
        return local.collect(args.path, window)

    creds = google_auth.load_credentials(args.token)

    if args.source == "picker":
        session = google_photos.create_picker_session(creds)
        print("\nブラウザで次のURLを開き、対象の日付の写真を選択してください:")
        print(f"\n  {session['pickerUri']}\n")
        print("選択が終わるまで待機します(最大15分)…")
        google_photos.wait_for_selection(creds, session)
        items = google_photos.list_picked_items(creds, session["id"])
        print(f"  {len(items)} 件が選択されました。オリジナルをダウンロードします…")
        photos = google_photos.fetch(
            creds, items, window, args.cache_dir, include_videos=args.include_videos
        )
        google_photos.delete_picker_session(creds, session["id"])
        return photos

    # source == "library"
    print(
        "! Library API はユーザーのライブラリ全体には原則アクセスできません"
        "(2025-03-31 の仕様変更)。取得できない場合は --source picker か takeout を使ってください。"
    )
    items = google_photos.search_library(creds, window)
    print(f"  {len(items)} 件が該当しました。オリジナルをダウンロードします…")
    return google_photos.fetch(
        creds, items, window, args.cache_dir, include_videos=args.include_videos
    )


def cmd_build(args: argparse.Namespace) -> int:
    window = DateWindow.parse(args.date, args.end_date, args.tz)
    print(f"■ 対象日: {window}({args.tz}) / 取得元: {args.source}")

    photos = base_source.normalize_times(collect_photos(args, window), window)
    if not photos:
        print("\n該当する写真が見つかりませんでした。確認してください:")
        print("  ・ --date と --tz が撮影時のタイムゾーンと合っているか")
        print("  ・ --path が正しいか(Takeout は展開後のルートを指定)")
        return 1

    geo_count = sum(1 for p in photos if p.has_geo)
    print(f"■ {len(photos)} 枚を抽出(うちジオタグあり {geo_count} 枚)")
    if geo_count == 0:
        print(
            "! ジオタグを持つ写真がありませんでした。Google フォトの API は位置情報を返さないため、\n"
            "  ジオタグは EXIF か Takeout の JSON から読み取ります。写真の位置情報が\n"
            "  削除されている場合、地図には配置できません。"
        )

    geocoder = Geocoder(
        provider=args.geocode,
        api_key=args.maps_key or os.environ.get("GOOGLE_MAPS_API_KEY", ""),
        language=args.language,
    )
    if args.geocode != "none" and geo_count:
        print(f"■ 逆ジオコーディング中({args.geocode})…")
        geocoder.annotate(photos)

    stops = build_stops(photos, radius_m=args.cluster_radius, gap_minutes=args.cluster_gap)
    print(f"■ 立ち寄り地点: {len(stops)} か所")

    os.makedirs(args.out, exist_ok=True)
    assets_mod.materialize(photos, args.out, embed=not args.no_images)

    narrator = (
        ClaudeNarrator(model=args.model, use_vision=args.vision, effort=args.effort)
        if args.claude
        else RuleNarrator()
    )
    print("■ 解説を生成中…" + ("(Claude)" if args.claude else "(メタデータから自動生成)"))
    meta = narrator.narrate(photos, stops)

    written = _write_outputs(args, photos, stops, meta, str(window))
    print("\n✓ 生成しました:")
    for path in written:
        print(f"  {path}")
    return 0


def _write_outputs(
    args: argparse.Namespace, photos, stops, meta: dict, date_label: str
) -> list[str]:
    written: list[str] = []
    formats = set(args.format)
    api_key = args.maps_key or os.environ.get("GOOGLE_MAPS_API_KEY", "")

    if "html" in formats:
        path = os.path.join(args.out, "index.html")
        _write(
            path,
            html_render.render(
                photos,
                stops,
                meta,
                map_provider=args.map,
                api_key=api_key,
                date_label=date_label,
            ),
        )
        written.append(path)

    if "md" in formats:
        path = os.path.join(args.out, "document.md")
        _write(path, md_render.render(photos, stops, meta, date_label=date_label))
        written.append(path)

    if "geojson" in formats:
        path = os.path.join(args.out, "photos.geojson")
        _write(path, geo_render.to_geojson(photos, stops))
        written.append(path)

    if "kml" in formats:
        path = os.path.join(args.out, "photos.kml")
        _write(path, geo_render.to_kml(photos, stops, meta.get("title", "写真の記録")))
        written.append(path)

    return written


def _write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


# --- サブコマンド: demo ----------------------------------------------------


def cmd_demo(args: argparse.Namespace) -> int:
    """Google アカウント無しで動作確認するためのサンプル生成 + ビルド。"""
    from .testkit import make_sample_takeout

    sample_root = os.path.join(args.out, "sample-data")
    print(f"■ サンプル写真(ジオタグ入り)を生成中: {sample_root}")
    takeout_root = make_sample_takeout(sample_root, day=args.date)

    demo_args = build_parser().parse_args(
        [
            "build",
            "--source",
            "takeout",
            "--path",
            takeout_root,
            "--date",
            args.date,
            "--out",
            args.out,
            "--geocode",
            args.geocode,
            "--format",
            "html",
            "md",
            "geojson",
            "kml",
        ]
    )
    return cmd_build(demo_args)


# --- 引数定義 --------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="photomap",
        description="Google フォトの写真を日付で抽出し、ジオタグを地図に載せたドキュメントを作ります。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    auth = sub.add_parser("auth", help="Google アカウントを認可してトークンを保存する")
    auth.add_argument("--client-secrets", required=True, help="デスクトップアプリの client_secret JSON")
    auth.add_argument("--token", default=google_auth.DEFAULT_TOKEN_PATH, help="トークンの保存先")
    auth.add_argument(
        "--library",
        action="store_true",
        help="Library API のスコープも要求する(レガシー・多くの場合ライブラリ全体は読めません)",
    )
    auth.add_argument("--no-browser", action="store_true", help="ブラウザを自動で開かない")
    auth.set_defaults(func=cmd_auth)

    build = sub.add_parser("build", help="写真を抽出してドキュメントを生成する")
    build.add_argument(
        "--source",
        choices=["takeout", "local", "picker", "library"],
        default="takeout",
        help="写真の取得元(既定: takeout)",
    )
    build.add_argument("--path", help="takeout / local のときの入力ディレクトリ")
    build.add_argument("--date", required=True, help="対象日 (YYYY-MM-DD)")
    build.add_argument("--end-date", help="範囲で指定する場合の終了日 (YYYY-MM-DD, 当日を含む)")
    build.add_argument("--tz", default="Asia/Tokyo", help="日付判定に使うタイムゾーン(既定: Asia/Tokyo)")
    build.add_argument("--out", default="out", help="出力ディレクトリ(既定: out)")
    build.add_argument(
        "--format",
        nargs="+",
        default=["html", "md", "geojson"],
        choices=["html", "md", "geojson", "kml"],
        help="出力形式(複数指定可)",
    )
    build.add_argument(
        "--map", choices=["leaflet", "google"], default="leaflet", help="地図の描画方式"
    )
    build.add_argument("--maps-key", default="", help="Google Maps / Geocoding API キー")
    build.add_argument(
        "--geocode",
        choices=["osm", "google", "none"],
        default="osm",
        help="逆ジオコーディングの提供元(既定: osm)",
    )
    build.add_argument("--language", default="ja", help="地名の言語(既定: ja)")
    build.add_argument("--claude", action="store_true", help="Claude で解説文を生成する")
    build.add_argument("--vision", action="store_true", help="Claude に写真そのものも見せる")
    build.add_argument("--model", default="claude-opus-5", help="使用する Claude モデル")
    build.add_argument(
        "--effort",
        choices=["low", "medium", "high", "xhigh", "max"],
        default="high",
        help="Claude の effort(既定: high)",
    )
    build.add_argument("--cluster-radius", type=float, default=250.0, help="同一地点とみなす半径(m)")
    build.add_argument("--cluster-gap", type=float, default=45.0, help="地点を区切る時間間隔(分)")
    build.add_argument("--no-images", action="store_true", help="画像をコピーせず本文だけ生成する")
    build.add_argument("--include-videos", action="store_true", help="動画も対象にする")
    build.add_argument("--cache-dir", default=DEFAULT_CACHE, help="API 経由でダウンロードした写真の保存先")
    build.add_argument("--token", default=google_auth.DEFAULT_TOKEN_PATH, help="トークンのパス")
    build.set_defaults(func=cmd_build)

    demo = sub.add_parser(
        "demo", help="サンプル写真を合成して、そのままドキュメントを生成する(動作確認用)"
    )
    demo.add_argument("--out", default="demo-out", help="出力ディレクトリ")
    demo.add_argument("--date", default="2026-06-27", help="サンプルの撮影日")
    demo.add_argument(
        "--geocode",
        choices=["osm", "google", "none"],
        default="none",
        help="逆ジオコーディング(既定: none = 外部通信なし)",
    )
    demo.set_defaults(func=cmd_demo)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except google_auth.AuthError as exc:
        print(f"認証/通信エラー: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"入力エラー: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"引数エラー: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n中断しました。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
