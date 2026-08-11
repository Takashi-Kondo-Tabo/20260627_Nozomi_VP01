"""photomap のユニットテスト。``python -m unittest discover tests`` で実行。"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from photomap import cli, cluster, exif, testkit  # noqa: E402
from photomap.models import Photo, Place, haversine_m  # noqa: E402
from photomap.narrate import ClaudeNarrator, RuleNarrator  # noqa: E402
from photomap.render import geo as geo_render  # noqa: E402
from photomap.render import html as html_render  # noqa: E402
from photomap.render import markdown as md_render  # noqa: E402
from photomap.sources import base, local, takeout  # noqa: E402
from photomap.sources.base import DateWindow  # noqa: E402


class ExifRoundTripTest(unittest.TestCase):
    """testkit で書いた EXIF を exif.py が読み戻せること。"""

    def _write(self, path: str, lat: float, lon: float, when: datetime) -> None:
        testkit.write_png(path, 32, 24, hue=3, exif=testkit.build_exif(lat, lon, when))

    def test_reads_gps_and_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.png")
            when = datetime(2026, 6, 27, 14, 35, 12)
            self._write(path, 34.9948, 135.7850, when)

            tags = exif.read_exif(path)
            self.assertAlmostEqual(tags["latitude"], 34.9948, places=4)
            self.assertAlmostEqual(tags["longitude"], 135.7850, places=4)
            self.assertEqual(tags["taken_at"].replace(tzinfo=None), when)
            self.assertEqual(tags["taken_at"].utcoffset(), timedelta(hours=9))
            self.assertEqual(tags["camera_make"], "PhotoMap")
            self.assertEqual(tags["width"], 320)

    def test_southern_western_hemisphere(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "b.png")
            self._write(path, -33.8688, -151.2093, datetime(2026, 1, 2, 3, 4, 5))
            tags = exif.read_exif(path)
            self.assertLess(tags["latitude"], 0)
            self.assertLess(tags["longitude"], 0)
            self.assertAlmostEqual(tags["latitude"], -33.8688, places=4)

    def test_missing_exif_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "plain.png")
            testkit.write_png(path, 8, 8, hue=1)
            self.assertEqual(exif.read_exif(path), {})
            self.assertEqual(exif.read_exif(os.path.join(tmp, "missing.png")), {})

    def test_jpeg_app1_segment_is_parsed(self):
        payload = b"Exif\x00\x00" + testkit.build_exif(
            35.0, 135.0, datetime(2026, 6, 27, 10, 0, 0)
        )
        import struct

        jpeg = b"\xff\xd8" + b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
        jpeg += b"\xff\xda\x00\x02\x00"  # SOS(ここから先は走査しない)
        tags = exif.read_exif_bytes(jpeg)
        self.assertAlmostEqual(tags["latitude"], 35.0, places=4)


class DateWindowTest(unittest.TestCase):
    def test_single_day_boundaries(self):
        window = DateWindow.parse("2026-06-27", None, "Asia/Tokyo")
        tz = timezone(timedelta(hours=9))
        self.assertTrue(window.contains(datetime(2026, 6, 27, 0, 0, tzinfo=tz)))
        self.assertTrue(window.contains(datetime(2026, 6, 27, 23, 59, tzinfo=tz)))
        self.assertFalse(window.contains(datetime(2026, 6, 28, 0, 0, tzinfo=tz)))
        self.assertFalse(window.contains(None))

    def test_utc_timestamp_is_converted_to_local_day(self):
        window = DateWindow.parse("2026-06-27", None, "Asia/Tokyo")
        # UTC 2026-06-26 20:00 は日本時間では 6/27 05:00 → その日に含まれる
        self.assertTrue(window.contains(datetime(2026, 6, 26, 20, 0, tzinfo=timezone.utc)))
        # UTC 2026-06-27 16:00 は日本時間では 6/28 01:00 → 含まれない
        self.assertFalse(window.contains(datetime(2026, 6, 27, 16, 0, tzinfo=timezone.utc)))

    def test_naive_datetime_is_treated_as_local(self):
        window = DateWindow.parse("2026-06-27", None, "Asia/Tokyo")
        self.assertTrue(window.contains(datetime(2026, 6, 27, 12, 0)))

    def test_range_and_validation(self):
        window = DateWindow.parse("2026-06-27", "2026-06-29", "UTC")
        self.assertTrue(window.contains(datetime(2026, 6, 29, 23, 0, tzinfo=timezone.utc)))
        self.assertFalse(window.contains(datetime(2026, 6, 30, 0, 0, tzinfo=timezone.utc)))
        with self.assertRaises(ValueError):
            DateWindow.parse("2026-06-27", "2026-06-01", "UTC")


class GeoTest(unittest.TestCase):
    def test_zero_island_is_not_a_geotag(self):
        self.assertFalse(Photo(id="x", filename="x", latitude=0.0, longitude=0.0).has_geo)
        self.assertTrue(Photo(id="x", filename="x", latitude=35.0, longitude=135.0).has_geo)
        self.assertFalse(Photo(id="x", filename="x", latitude=35.0).has_geo)

    def test_haversine_matches_known_distance(self):
        kyoto = Photo(id="a", filename="a", latitude=34.9858, longitude=135.7588)
        kinkakuji = Photo(id="b", filename="b", latitude=35.0394, longitude=135.7292)
        # 京都駅〜金閣寺は直線でおよそ 6.4 km
        self.assertAlmostEqual(haversine_m(kyoto, kinkakuji) / 1000, 6.4, delta=0.4)


class ClusterTest(unittest.TestCase):
    def _photo(self, minute: int, lat: float, lon: float) -> Photo:
        return Photo(
            id=str(minute),
            filename=f"{minute}.jpg",
            taken_at=datetime(2026, 6, 27, 9, 0) + timedelta(minutes=minute),
            latitude=lat,
            longitude=lon,
        )

    def test_splits_on_distance_and_time(self):
        photos = [
            self._photo(0, 34.9858, 135.7588),
            self._photo(5, 34.9859, 135.7589),  # 同じ場所・直後 → 同じ地点
            self._photo(60, 34.9948, 135.7850),  # 大きく移動 → 別地点
            self._photo(200, 34.9948, 135.7850),  # 同じ場所だが時間が空いた → 別地点
        ]
        stops = cluster.build_stops(photos, radius_m=250, gap_minutes=45)
        self.assertEqual([len(s.photos) for s in stops], [2, 1, 1])
        self.assertEqual([s.index for s in stops], [1, 2, 3])

    def test_photos_without_geotag_are_excluded(self):
        photos = [self._photo(0, 34.98, 135.75), Photo(id="n", filename="n.jpg")]
        stops = cluster.build_stops(photos)
        self.assertEqual(len(stops), 1)
        self.assertEqual(len(stops[0].photos), 1)


class TakeoutTest(unittest.TestCase):
    def test_reads_sidecar_geodata_and_filters_by_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = testkit.make_sample_takeout(tmp, day="2026-06-27")
            window = DateWindow.parse("2026-06-27", None, "Asia/Tokyo")
            photos = takeout.collect(root, window)

            self.assertEqual(len(photos), len(testkit.SAMPLE_ROUTE))
            self.assertEqual(
                [p.taken_at for p in photos], sorted(p.taken_at for p in photos)
            )
            geo = [p for p in photos if p.has_geo]
            self.assertEqual(len(geo), 6)  # 4枚に1枚は位置情報なし
            self.assertAlmostEqual(geo[0].latitude, 34.9858, places=3)
            self.assertIn("京都駅", photos[0].description)

            other_day = DateWindow.parse("2026-06-28", None, "Asia/Tokyo")
            self.assertEqual(takeout.collect(root, other_day), [])

    def test_geodata_falls_back_to_geodataexif(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "Takeout", "Google Photos")
            os.makedirs(folder)
            path = os.path.join(folder, "x.png")
            testkit.write_png(path, 8, 8, hue=1)
            with open(path + ".json", "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "title": "x.png",
                        "photoTakenTime": {"timestamp": "1782000000"},
                        "geoData": {"latitude": 0.0, "longitude": 0.0},
                        "geoDataExif": {"latitude": 35.5, "longitude": 139.5},
                    },
                    fh,
                )
            taken = datetime.fromtimestamp(1782000000, tz=timezone.utc).astimezone(
                timezone(timedelta(hours=9))
            )
            window = DateWindow.parse(taken.date().isoformat(), None, "Asia/Tokyo")
            photos = takeout.collect(os.path.join(tmp, "Takeout"), window)
            self.assertEqual(len(photos), 1)
            self.assertTrue(photos[0].has_geo)
            self.assertAlmostEqual(photos[0].latitude, 35.5)


class LocalSourceTest(unittest.TestCase):
    def test_reads_exif_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "img.png")
            testkit.write_png(
                path,
                16,
                16,
                hue=2,
                exif=testkit.build_exif(35.6812, 139.7671, datetime(2026, 6, 27, 8, 0, 0)),
            )
            window = DateWindow.parse("2026-06-27", None, "Asia/Tokyo")
            photos = local.collect(tmp, window)
            self.assertEqual(len(photos), 1)
            self.assertAlmostEqual(photos[0].longitude, 139.7671, places=3)


class NormalizeTimesTest(unittest.TestCase):
    """取得元ごとに違う時刻表現を、表示用タイムゾーンへ揃える。"""

    def test_utc_timestamps_are_shown_as_local_time(self):
        window = DateWindow.parse("2026-06-27", None, "Asia/Tokyo")
        photos = [Photo(id="1", filename="a", taken_at=datetime(2026, 6, 27, 0, 10, tzinfo=timezone.utc))]
        base.normalize_times(photos, window)
        # UTC 00:10 は日本時間の 09:10
        self.assertEqual(photos[0].taken_at.strftime("%H:%M"), "09:10")

    def test_naive_exif_time_is_kept_as_wall_clock(self):
        window = DateWindow.parse("2026-06-27", None, "Asia/Tokyo")
        photos = [Photo(id="1", filename="a", taken_at=datetime(2026, 6, 27, 9, 10))]
        base.normalize_times(photos, window)
        self.assertEqual(photos[0].taken_at.strftime("%H:%M"), "09:10")
        self.assertIsNotNone(photos[0].taken_at.tzinfo)

    def test_mixed_naive_and_aware_can_be_sorted(self):
        window = DateWindow.parse("2026-06-27", None, "Asia/Tokyo")
        photos = [
            Photo(id="1", filename="late", taken_at=datetime(2026, 6, 27, 18, 0)),
            Photo(id="2", filename="early", taken_at=datetime(2026, 6, 27, 0, 10, tzinfo=timezone.utc)),
            Photo(id="3", filename="unknown"),
        ]
        ordered = base.normalize_times(photos, window)
        self.assertEqual([p.filename for p in ordered], ["early", "late", "unknown"])


class DemoEndToEndTest(unittest.TestCase):
    """`photomap demo` が外部通信なしで一式を生成できること。"""

    def test_demo_generates_all_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = cli.main(["demo", "--out", tmp, "--date", "2026-06-27", "--geocode", "none"])
            self.assertEqual(code, 0)
            for name in ("index.html", "document.md", "photos.geojson", "photos.kml"):
                self.assertTrue(os.path.exists(os.path.join(tmp, name)), name)

            with open(os.path.join(tmp, "index.html"), encoding="utf-8") as fh:
                page = fh.read()
            self.assertIn("09:10", page)  # UTC ではなく現地時刻で表示される
            self.assertNotIn("00:10", page)
            self.assertIn("assets/", page)  # 画像が出力ディレクトリに置かれている

            data = json.loads(
                page.split('id="photomap-data">')[1].split("</script>")[0].replace("<\\/", "</")
            )
            self.assertEqual(len(data["photos"]), 8)
            self.assertEqual(len(data["stops"]), 5)
            self.assertEqual(sum(1 for p in data["photos"] if p["hasGeo"]), 6)

    def test_missing_date_is_rejected(self):
        with self.assertRaises(SystemExit):
            cli.main(["build", "--source", "local", "--path", "/nonexistent"])


class RenderTest(unittest.TestCase):
    def _fixture(self):
        photos = [
            Photo(
                id="1",
                filename="a.png",
                taken_at=datetime(2026, 6, 27, 9, 30),
                latitude=34.9858,
                longitude=135.7588,
                place=Place(name="京都駅", address="京都府京都市下京区"),
                caption="朝の京都駅から一日が始まりました。",
                asset_path="assets/a.png",
            ),
            Photo(id="2", filename="b.png", taken_at=datetime(2026, 6, 27, 12, 0)),
        ]
        stops = cluster.build_stops(photos)
        meta = RuleNarrator().narrate(photos, stops)
        return photos, stops, meta

    def test_html_is_self_describing_and_escaped(self):
        photos, stops, meta = self._fixture()
        photos[0].caption = 'テスト <script>alert("x")</script> & 引用'
        out = html_render.render(photos, stops, meta, date_label="2026-06-27")

        self.assertIn("<!doctype html>", out)
        self.assertIn("京都駅", out)
        self.assertIn("ジオタグなし", out)  # 位置情報の無い写真に印が付く
        self.assertNotIn('<script>alert("x")</script>', out)
        self.assertIn("&lt;script&gt;", out)
        # 埋め込み JSON が </script> でパースを壊さないこと
        self.assertNotIn("</script>", out.split('id="photomap-data">')[1].split("<\/")[0])

    def test_html_payload_is_valid_json(self):
        photos, stops, meta = self._fixture()
        out = html_render.render(photos, stops, meta)
        raw = out.split('id="photomap-data">')[1].split("</script>")[0]
        data = json.loads(raw.replace("<\\/", "</"))
        self.assertEqual(len(data["photos"]), 2)
        self.assertEqual(data["photos"][0]["place"], "京都駅")
        self.assertFalse(data["photos"][1]["hasGeo"])

    def test_markdown_and_geojson(self):
        photos, stops, meta = self._fixture()
        md = md_render.render(photos, stops, meta, date_label="2026-06-27")
        self.assertIn("# ", md)
        self.assertIn("![a.png](assets/a.png)", md)

        data = json.loads(geo_render.to_geojson(photos, stops))
        points = [f for f in data["features"] if f["geometry"]["type"] == "Point"]
        self.assertEqual(len(points), 1)  # ジオタグのある写真だけ
        self.assertEqual(points[0]["geometry"]["coordinates"], [135.7588, 34.9858])

        kml = geo_render.to_kml(photos, stops)
        self.assertIn("<kml", kml)
        self.assertIn("135.758800,34.985800", kml)


class NarratorTest(unittest.TestCase):
    def test_rule_based_captions_mention_place_and_missing_geotag(self):
        photos = [
            Photo(
                id="1",
                filename="a.png",
                taken_at=datetime(2026, 6, 27, 7, 30),
                latitude=34.9858,
                longitude=135.7588,
                place=Place(name="京都駅"),
                camera_make="Canon",
                camera_model="EOS R8",
            ),
            Photo(id="2", filename="b.png", taken_at=datetime(2026, 6, 27, 19, 0)),
        ]
        stops = cluster.build_stops(photos)
        meta = RuleNarrator().narrate(photos, stops)

        self.assertIn("京都駅", photos[0].caption)
        self.assertIn("早朝", photos[0].caption)
        self.assertIn("Canon EOS R8", photos[0].caption)
        self.assertIn("ジオタグが無い", photos[1].caption)
        self.assertIn("2026年06月27日", meta["title"])
        self.assertIn("2 枚", meta["summary"])


class _Block:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _Message:
    def __init__(self, text: str, stop_reason: str = "end_turn"):
        self.content = [_Block(text)]
        self.stop_reason = stop_reason


class _FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.message


class _FakeEndpoint:
    def __init__(self, message, recorder: dict):
        self.message = message
        self.recorder = recorder

    def stream(self, **kwargs):
        self.recorder.update(kwargs)
        return _FakeStream(self.message)


class _FakeClient:
    def __init__(self, message, recorder):
        self.messages = _FakeEndpoint(message, recorder)
        self.beta = type("Beta", (), {"messages": _FakeEndpoint(message, recorder)})()


class ClaudeNarratorTest(unittest.TestCase):
    """Claude 経路のオフライン検証(実 API は呼ばない)。"""

    def _fixture(self):
        photos = [
            Photo(
                id="1",
                filename="a.png",
                taken_at=datetime(2026, 6, 27, 9, 0),
                latitude=34.9858,
                longitude=135.7588,
                place=Place(name="京都駅"),
            ),
            Photo(id="2", filename="b.png", taken_at=datetime(2026, 6, 27, 12, 0)),
        ]
        return photos, cluster.build_stops(photos)

    def _install_fake(self, client_factory):
        fake = types.ModuleType("anthropic")
        fake.Anthropic = client_factory
        self.addCleanup(sys.modules.pop, "anthropic", None)
        sys.modules["anthropic"] = fake

    def test_applies_model_output(self):
        photos, stops = self._fixture()
        payload = json.dumps(
            {
                "title": "京都の一日",
                "summary": "駅から歩き始めた一日の記録です。",
                "photos": [
                    {"index": 0, "caption": "朝の京都駅。", "tags": ["駅", "朝"]},
                    {"index": 1, "caption": "昼の一枚。", "tags": []},
                ],
                "stops": [{"index": 1, "summary": "京都駅周辺での滞在。"}],
            },
            ensure_ascii=False,
        )
        recorder: dict = {}
        self._install_fake(lambda: _FakeClient(_Message(payload), recorder))

        meta = ClaudeNarrator(use_vision=False).narrate(photos, stops)

        self.assertEqual(meta["title"], "京都の一日")
        self.assertEqual(photos[0].caption, "朝の京都駅。")
        self.assertEqual(photos[0].tags, ["駅", "朝"])
        self.assertEqual(stops[0].summary, "京都駅周辺での滞在。")
        # 送信パラメータが意図どおりか
        self.assertEqual(recorder["thinking"], {"type": "adaptive"})
        self.assertEqual(recorder["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(recorder["fallbacks"], "default")
        self.assertEqual(recorder["model"], "claude-opus-5")
        self.assertEqual(recorder["betas"], ["server-side-fallback-2026-07-01"])
        # 画像を添付していないので、送るのはテキストブロックのみ
        self.assertEqual([b["type"] for b in recorder["messages"][0]["content"]], ["text"])

    def test_falls_back_when_sdk_missing(self):
        photos, stops = self._fixture()
        self.addCleanup(sys.modules.pop, "anthropic", None)
        sys.modules["anthropic"] = None  # import anthropic が ImportError になる

        meta = ClaudeNarrator().narrate(photos, stops)
        self.assertIn("京都駅", photos[0].caption)  # ルールベースの解説が残る
        self.assertTrue(meta["summary"])

    def test_falls_back_on_refusal(self):
        photos, stops = self._fixture()
        self._install_fake(lambda: _FakeClient(_Message("", stop_reason="refusal"), {}))

        meta = ClaudeNarrator().narrate(photos, stops)
        self.assertIn("京都駅", photos[0].caption)
        self.assertTrue(meta["title"])

    def test_retries_without_beta_params_on_old_sdk(self):
        photos, stops = self._fixture()
        payload = json.dumps(
            {"title": "T", "summary": "S", "photos": [], "stops": []}, ensure_ascii=False
        )
        recorder: dict = {}

        class OldBetaEndpoint:
            def stream(self, **kwargs):
                raise TypeError("unexpected keyword argument 'fallbacks'")

        def factory():
            client = _FakeClient(_Message(payload), recorder)
            client.beta = type("Beta", (), {"messages": OldBetaEndpoint()})()
            return client

        self._install_fake(factory)
        meta = ClaudeNarrator().narrate(photos, stops)

        self.assertEqual(meta["title"], "T")
        self.assertNotIn("fallbacks", recorder)  # 通常経路で再試行されている


if __name__ == "__main__":
    unittest.main()
