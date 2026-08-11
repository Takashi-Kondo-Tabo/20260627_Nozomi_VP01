"""地図付き HTML ドキュメントを生成する。

* ``--map google`` … Google Maps JavaScript API(要 API キー)
* ``--map leaflet`` … Leaflet + OpenStreetMap タイル(キー不要・既定)

生成物は1枚の HTML ファイル(+ assets/ の画像)。ブラウザで開けばそのまま読め、
印刷/PDF 出力にも耐えるスタイルを当ててある。
"""

from __future__ import annotations

import html
import json
import os
from datetime import datetime

from ..cluster import Stop, route_length_m
from ..models import Photo


def _esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def _clock(dt: datetime | None) -> str:
    return dt.strftime("%H:%M") if dt else "--:--"


def build_payload(photos: list[Photo], stops: list[Stop]) -> dict:
    index_of = {id(p): i for i, p in enumerate(photos)}
    return {
        "photos": [
            {
                "i": i,
                "filename": p.filename,
                "time": _clock(p.taken_at),
                "datetime": p.taken_at.isoformat() if p.taken_at else None,
                "lat": p.latitude,
                "lng": p.longitude,
                "place": p.place.label() if p.place else "",
                "address": p.place.address if p.place else "",
                "caption": p.caption,
                "tags": p.tags,
                "camera": " ".join(x for x in (p.camera_make, p.camera_model) if x).strip(),
                "asset": p.asset_path,
                "hasGeo": p.has_geo,
            }
            for i, p in enumerate(photos)
        ],
        "stops": [
            {
                "index": s.index,
                "label": s.label,
                "lat": s.latitude,
                "lng": s.longitude,
                "summary": s.summary,
                "photos": [index_of[id(p)] for p in s.photos],
                "start": _clock(s.start),
                "end": _clock(s.end),
            }
            for s in stops
        ],
    }


def render(
    photos: list[Photo],
    stops: list[Stop],
    meta: dict,
    *,
    map_provider: str = "leaflet",
    api_key: str = "",
    date_label: str = "",
) -> str:
    payload = build_payload(photos, stops)
    payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

    geo_count = sum(1 for p in photos if p.has_geo)
    distance_km = route_length_m(stops) / 1000.0
    stats = [
        ("写真", f"{len(photos)} 枚"),
        ("ジオタグあり", f"{geo_count} 枚"),
        ("立ち寄り地点", f"{len(stops)} か所"),
        ("移動(直線距離)", f"{distance_km:.1f} km"),
    ]
    stats_html = "\n".join(
        f'<div class="stat"><span class="stat-label">{_esc(k)}</span>'
        f'<span class="stat-value">{_esc(v)}</span></div>'
        for k, v in stats
    )

    cards = "\n".join(_card_html(i, p) for i, p in enumerate(photos))
    stop_list = "\n".join(_stop_html(s) for s in stops)

    if map_provider == "google" and api_key:
        map_head = (
            '<script defer '
            f'src="https://maps.googleapis.com/maps/api/js?key={_esc(api_key)}'
            '&callback=initMap&loading=async&language=ja&region=JP"></script>'
        )
        map_script = _GOOGLE_MAP_JS
        # Maps JS API 側が callback=initMap を呼ぶので、こちらからは起動しない
        map_boot = "/* Google Maps JS API の callback が initMap を呼びます */"
    else:
        map_head = (
            '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>\n'
            '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
        )
        map_script = _LEAFLET_MAP_JS
        map_boot = "initMap();"

    no_geo = [p for p in photos if not p.has_geo]
    no_geo_note = ""
    if no_geo:
        no_geo_note = (
            '<p class="note">'
            f"{len(no_geo)} 枚にはジオタグがありません(Google フォト側で位置情報を削除した写真、"
            "位置情報オフで撮影した写真、スクリーンショットなど)。"
            "これらは地図には配置せず、時系列にのみ収録しています。</p>"
        )

    return (
        _TEMPLATE.replace("{{TITLE}}", _esc(meta.get("title", "写真の記録")))
        .replace("{{DATE_LABEL}}", _esc(date_label))
        .replace("{{SUMMARY}}", _esc(meta.get("summary", "")))
        .replace("{{STATS}}", stats_html)
        .replace("{{STOPS}}", stop_list)
        .replace("{{CARDS}}", cards)
        .replace("{{NO_GEO_NOTE}}", no_geo_note)
        .replace("{{MAP_HEAD}}", map_head)
        .replace("{{MAP_SCRIPT}}", map_script)
        .replace("{{MAP_BOOT}}", map_boot)
        .replace("{{PAYLOAD}}", payload_json)
        .replace("{{GENERATED}}", _esc(datetime.now().strftime("%Y-%m-%d %H:%M")))
    )


def _card_html(index: int, photo: Photo) -> str:
    img = (
        f'<img loading="lazy" src="{_esc(photo.asset_path)}" alt="{_esc(photo.filename)}">'
        if photo.asset_path
        else '<div class="noimg">画像なし</div>'
    )
    place = photo.place.label() if photo.place else ""
    badges = []
    if place:
        badges.append(f'<span class="badge">{_esc(place)}</span>')
    if not photo.has_geo:
        badges.append('<span class="badge badge-warn">ジオタグなし</span>')
    for tag in photo.tags[:4]:
        badges.append(f'<span class="badge badge-tag">{_esc(tag)}</span>')

    coords = ""
    if photo.has_geo:
        coords = (
            f'<a class="coords" target="_blank" rel="noopener" '
            f'href="https://www.google.com/maps/search/?api=1&amp;query={photo.latitude:.6f},{photo.longitude:.6f}">'
            f"{photo.latitude:.5f}, {photo.longitude:.5f}</a>"
        )

    return f"""<article class="card" id="photo-{index}" data-index="{index}">
  <div class="card-media">{img}</div>
  <div class="card-body">
    <header>
      <span class="time">{_esc(_clock(photo.taken_at))}</span>
      <span class="fname">{_esc(photo.filename)}</span>
    </header>
    <div class="badges">{''.join(badges)}</div>
    <p class="caption">{_esc(photo.caption)}</p>
    <footer>{coords}{f'<span class="camera">{_esc(" ".join(x for x in (photo.camera_make, photo.camera_model) if x))}</span>' if photo.camera_make or photo.camera_model else ''}</footer>
  </div>
</article>"""


def _stop_html(stop: Stop) -> str:
    return f"""<li class="stop" data-stop="{stop.index}">
  <span class="stop-no">{stop.index}</span>
  <div>
    <div class="stop-name">{_esc(stop.label)}</div>
    <div class="stop-meta">{_esc(_clock(stop.start))}–{_esc(_clock(stop.end))} ・ {len(stop.photos)} 枚</div>
    <p class="stop-summary">{_esc(stop.summary)}</p>
  </div>
</li>"""


_LEAFLET_MAP_JS = """
function initMap() {
  if (typeof L === 'undefined') { mapUnavailable(); return; }
  const pts = DATA.stops.map(s => [s.lat, s.lng]);
  const map = L.map('map', { scrollWheelZoom: false });
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  if (pts.length > 1) {
    L.polyline(pts, { color: '#c2410c', weight: 3, opacity: 0.7, dashArray: '6 6' }).addTo(map);
  }
  DATA.stops.forEach(stop => {
    const icon = L.divIcon({
      className: 'pin-wrap',
      html: '<div class="pin">' + stop.index + '</div>',
      iconSize: [30, 30], iconAnchor: [15, 15]
    });
    const marker = L.marker([stop.lat, stop.lng], { icon }).addTo(map);
    marker.bindPopup(popupHtml(stop), { maxWidth: 260 });
    marker.on('click', () => focusStop(stop.index, false));
    markers[stop.index] = marker;
  });

  if (pts.length === 1) map.setView(pts[0], 15);
  else if (pts.length > 1) map.fitBounds(L.latLngBounds(pts).pad(0.15));
  else { mapUnavailable(); return; }

  api = {
    focus(stop) {
      map.setView([stop.lat, stop.lng], Math.max(map.getZoom(), 15), { animate: true });
      markers[stop.index] && markers[stop.index].openPopup();
    }
  };
}
"""

_GOOGLE_MAP_JS = """
function initMap() {
  if (!window.google || !google.maps) { mapUnavailable(); return; }
  if (!DATA.stops.length) { mapUnavailable(); return; }
  const map = new google.maps.Map(document.getElementById('map'), {
    mapTypeControl: false, streetViewControl: false, scrollwheel: false
  });
  const bounds = new google.maps.LatLngBounds();
  const info = new google.maps.InfoWindow();

  new google.maps.Polyline({
    path: DATA.stops.map(s => ({ lat: s.lat, lng: s.lng })),
    strokeColor: '#c2410c', strokeOpacity: 0.75, strokeWeight: 3, map
  });

  DATA.stops.forEach(stop => {
    const pos = { lat: stop.lat, lng: stop.lng };
    bounds.extend(pos);
    const marker = new google.maps.Marker({
      position: pos, map, label: { text: String(stop.index), color: '#fff', fontSize: '12px' },
      title: stop.label
    });
    marker.addListener('click', () => {
      info.setContent(popupHtml(stop));
      info.open({ anchor: marker, map });
      focusStop(stop.index, false);
    });
    markers[stop.index] = marker;
  });

  if (DATA.stops.length === 1) { map.setCenter(bounds.getCenter()); map.setZoom(15); }
  else { map.fitBounds(bounds, 48); }

  api = {
    focus(stop) {
      map.panTo({ lat: stop.lat, lng: stop.lng });
      if (map.getZoom() < 15) map.setZoom(15);
      info.setContent(popupHtml(stop));
      info.open({ anchor: markers[stop.index], map });
    }
  };
}
window.initMap = initMap;
"""

_TEMPLATE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}}</title>
{{MAP_HEAD}}
<style>
  :root {
    --bg: #fbf9f6; --panel: #ffffff; --ink: #23201d; --muted: #6d6660;
    --line: #e6e0d8; --accent: #c2410c; --warn: #92400e; --warn-bg: #fef3c7;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #16140f; --panel: #1f1c17; --ink: #ece7df; --muted: #a49c92;
      --line: #322d26; --accent: #f97316; --warn: #fcd34d; --warn-bg: #3a2c10;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: "Hiragino Sans", "Noto Sans JP", "Yu Gothic", system-ui, sans-serif;
    line-height: 1.75; -webkit-font-smoothing: antialiased;
  }
  .wrap { max-width: 1240px; margin: 0 auto; padding: 32px 20px 64px; }
  header.page h1 { font-size: clamp(1.6rem, 3.4vw, 2.4rem); margin: 0 0 6px; letter-spacing: .01em; }
  .date { color: var(--accent); font-weight: 700; letter-spacing: .08em; font-size: .85rem; }
  .lede { color: var(--muted); max-width: 62ch; margin: 12px 0 0; }
  .stats { display: flex; flex-wrap: wrap; gap: 10px; margin: 22px 0 26px; }
  .stat {
    background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
    padding: 8px 14px; display: flex; flex-direction: column; min-width: 118px;
  }
  .stat-label { font-size: .72rem; color: var(--muted); letter-spacing: .04em; }
  .stat-value { font-size: 1.08rem; font-weight: 700; }

  .layout { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 26px; align-items: start; }
  @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }

  .map-col { position: sticky; top: 20px; }
  @media (max-width: 900px) { .map-col { position: static; } }
  #map {
    height: 460px; border-radius: 14px; border: 1px solid var(--line);
    background: var(--panel); overflow: hidden;
  }
  #map .fallback { display: grid; place-items: center; height: 100%; color: var(--muted); padding: 24px; text-align: center; }
  .pin {
    width: 26px; height: 26px; border-radius: 50%; background: var(--accent); color: #fff;
    display: grid; place-items: center; font-weight: 700; font-size: 12px;
    box-shadow: 0 2px 6px rgba(0,0,0,.35); border: 2px solid #fff;
  }
  .pop { font-family: inherit; }
  .pop img { width: 100%; border-radius: 6px; display: block; margin-bottom: 6px; }
  .pop b { display: block; margin-bottom: 2px; }
  .pop span { color: #666; font-size: .8rem; }

  .stops { list-style: none; margin: 18px 0 0; padding: 0; }
  .stop {
    display: flex; gap: 12px; padding: 12px; border: 1px solid var(--line);
    border-radius: 12px; background: var(--panel); margin-bottom: 10px; cursor: pointer;
  }
  .stop:hover, .stop.active { border-color: var(--accent); }
  .stop-no {
    flex: 0 0 26px; height: 26px; border-radius: 50%; background: var(--accent);
    color: #fff; display: grid; place-items: center; font-weight: 700; font-size: .8rem;
  }
  .stop-name { font-weight: 700; }
  .stop-meta { font-size: .78rem; color: var(--muted); }
  .stop-summary { margin: 6px 0 0; font-size: .86rem; color: var(--muted); }

  h2.section { font-size: 1.1rem; margin: 34px 0 14px; padding-bottom: 8px; border-bottom: 2px solid var(--line); }
  .card {
    display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 18px;
    background: var(--panel); border: 1px solid var(--line); border-radius: 14px;
    padding: 14px; margin-bottom: 14px; scroll-margin-top: 24px;
  }
  @media (max-width: 620px) { .card { grid-template-columns: 1fr; } }
  .card.active { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(194,65,12,.12); }
  .card-media img { width: 100%; border-radius: 9px; display: block; background: var(--line); }
  .noimg { height: 150px; display: grid; place-items: center; color: var(--muted); background: var(--bg); border-radius: 9px; font-size: .85rem; }
  .card-body header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  .time { font-weight: 700; color: var(--accent); font-variant-numeric: tabular-nums; }
  .fname { font-size: .78rem; color: var(--muted); word-break: break-all; }
  .badges { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
  .badge { font-size: .74rem; padding: 2px 9px; border-radius: 999px; background: var(--bg); border: 1px solid var(--line); color: var(--muted); }
  .badge-warn { background: var(--warn-bg); color: var(--warn); border-color: transparent; }
  .badge-tag { border-style: dashed; }
  .caption { margin: 6px 0 10px; }
  .card-body footer { display: flex; gap: 14px; flex-wrap: wrap; font-size: .76rem; color: var(--muted); }
  .coords { color: var(--accent); text-decoration: none; font-variant-numeric: tabular-nums; }
  .coords:hover { text-decoration: underline; }
  .note { background: var(--warn-bg); color: var(--warn); border-radius: 10px; padding: 10px 14px; font-size: .85rem; }
  footer.page { margin-top: 42px; padding-top: 16px; border-top: 1px solid var(--line); color: var(--muted); font-size: .78rem; }

  @media print {
    .map-col { position: static; }
    .layout { display: block; }
    #map { height: 320px; page-break-inside: avoid; }
    .card { page-break-inside: avoid; box-shadow: none; }
    body { background: #fff; color: #000; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header class="page">
    <div class="date">{{DATE_LABEL}}</div>
    <h1>{{TITLE}}</h1>
    <p class="lede">{{SUMMARY}}</p>
  </header>

  <div class="stats">{{STATS}}</div>

  <div class="layout">
    <div class="map-col">
      <div id="map"><div class="fallback">地図を読み込んでいます…</div></div>
      {{NO_GEO_NOTE}}
    </div>
    <aside>
      <h2 class="section" style="margin-top:0">その日の行程</h2>
      <ol class="stops">{{STOPS}}</ol>
    </aside>
  </div>

  <h2 class="section">写真と解説</h2>
  {{CARDS}}

  <footer class="page">
    photomap で生成 ・ {{GENERATED}} ・ 位置情報は各写真の EXIF / Google Takeout のメタデータに基づきます。
  </footer>
</div>

<script type="application/json" id="photomap-data">{{PAYLOAD}}</script>
<script>
const DATA = JSON.parse(document.getElementById('photomap-data').textContent);
const markers = {};
let api = null;

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function popupHtml(stop) {
  const first = DATA.photos[stop.photos[0]];
  const img = first && first.asset ? '<img src="' + esc(first.asset) + '" alt="">' : '';
  return '<div class="pop">' + img +
    '<b>' + stop.index + '. ' + esc(stop.label) + '</b>' +
    '<span>' + esc(stop.start) + '–' + esc(stop.end) + ' ・ ' + stop.photos.length + ' 枚</span>' +
    '</div>';
}

function mapUnavailable() {
  const el = document.getElementById('map');
  const msg = DATA.stops.length
    ? '地図ライブラリを読み込めませんでした(オフライン、または API キーの問題)。座標のリンクからは地図を開けます。'
    : 'ジオタグを持つ写真が無かったため、地図は表示していません。';
  el.innerHTML = '<div class="fallback">' + msg + '</div>';
}

function focusStop(index, moveMap = true) {
  const stop = DATA.stops.find(s => s.index === index);
  if (!stop) return;
  document.querySelectorAll('.stop').forEach(el =>
    el.classList.toggle('active', Number(el.dataset.stop) === index));
  document.querySelectorAll('.card').forEach(el => el.classList.remove('active'));
  stop.photos.forEach(i => {
    const card = document.getElementById('photo-' + i);
    if (card) card.classList.add('active');
  });
  if (moveMap && api) api.focus(stop);
}

document.querySelectorAll('.stop').forEach(el => {
  el.addEventListener('click', () => {
    const index = Number(el.dataset.stop);
    focusStop(index);
    const stop = DATA.stops.find(s => s.index === index);
    const card = stop && document.getElementById('photo-' + stop.photos[0]);
    if (card) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
});

document.querySelectorAll('.card').forEach(el => {
  el.addEventListener('click', () => {
    const i = Number(el.dataset.index);
    const stop = DATA.stops.find(s => s.photos.includes(i));
    if (stop) focusStop(stop.index);
  });
});

{{MAP_SCRIPT}}

if (!DATA.stops.length) {
  mapUnavailable();
} else {
  {{MAP_BOOT}}
}
</script>
</body>
</html>
"""
