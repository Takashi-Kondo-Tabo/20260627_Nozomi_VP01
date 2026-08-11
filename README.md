# photomap

Google フォトの写真を **特定の日付で抽出** し、そのジオタグを **地図上に配置した
ドキュメント** を生成するツールです。各写真には、撮影時刻・場所・前後の写真との
つながりを踏まえた **解説** が付きます。

出力は HTML(地図つき)/ Markdown / GeoJSON / KML。標準ライブラリだけで動作し、
追加パッケージは任意です。

```
photomap build --source takeout --path ~/Takeout --date 2026-06-27
```

---

## 先に知っておくべきこと(ジオタグの取得経路)

このツールの設計は、Google フォト API の次の2つの制約が出発点になっています。

1. **Google フォト API は位置情報を返しません。**
   `mediaItems` の `mediaMetadata` に含まれるのは撮影日時・画素数・カメラ情報などで、
   緯度経度は含まれません。したがってジオタグは
   **オリジナル画像の EXIF** か **Takeout の JSON サイドカー** から読む必要があります。
   本ツールは API 経由の場合、`baseUrl=d` でオリジナルを取得してから EXIF を解析します。

2. **2025-03-31 以降、Library API でライブラリ全体を読むことはできません。**
   `photoslibrary.readonly` はアプリが自ら作成したメディアに限定され、ユーザーの
   写真にアクセスする正式な経路は **Picker API**(ユーザーがブラウザで写真を選ぶ)
   になりました。

この2点から、取得元は用途に応じて選びます。

| `--source` | 内容 | ジオタグ | 向いている場面 |
|---|---|---|---|
| `takeout` **(推奨)** | Google Takeout のエクスポート | ◎ JSON サイドカー | 過去の特定日をまとめて処理したい |
| `picker` | Google フォト Picker API | ○ EXIF(要ダウンロード) | 対象写真をその場で選びたい |
| `local` | 手元の画像フォルダ | ○ EXIF | すでに書き出し済み |
| `library` | Library API(レガシー) | ○ EXIF | 互換目的。多くの場合ライブラリは読めません |

> Google フォトの共有設定で「位置情報を削除」した写真、位置情報オフで撮影した写真、
> スクリーンショットには、そもそもジオタグがありません。これらは地図には配置せず、
> 時系列にのみ収録し、ドキュメント上に「ジオタグなし」と明示します。

---

## インストール

```bash
git clone <this repo> && cd 20260627_Nozomi_VP01
pip install -e .

# 任意: サムネイル生成と Claude による解説
pip install -e ".[all]"
```

Python 3.11 以上。必須の外部パッケージはありません。

---

## まず動かしてみる(アカウント不要)

```bash
photomap demo --out demo-out
open demo-out/index.html
```

京都を巡る1日ぶんのサンプル写真(ジオタグ入り)を合成し、そのまま
ドキュメントを生成します。外部通信は行いません。

---

## 使い方

### 1. Google Takeout から(推奨)

[Google データエクスポート](https://takeout.google.com/) で「Google フォト」を
選んでダウンロード・展開し、そのルートを指定します。

```bash
photomap build \
  --source takeout \
  --path ~/Downloads/Takeout \
  --date 2026-06-27 \
  --out out/
```

### 2. Google フォト Picker API から

Google Cloud Console で Photos Picker API を有効にし、「デスクトップアプリ」の
OAuth クライアントを作って `client_secret.json` をダウンロードします。

```bash
photomap auth --client-secrets ~/client_secret.json     # 一度だけ
photomap build --source picker --date 2026-06-27 --out out/
```

実行するとピッカーの URL が表示されます。ブラウザで対象日の写真を選ぶと、
オリジナルがダウンロードされ、EXIF からジオタグを読み取ります。

### 3. ローカルフォルダから

```bash
photomap build --source local --path ~/Pictures/2026-06-27 --date 2026-06-27
```

---

## 地図と解説のオプション

### 地図

```bash
# 既定: Leaflet + OpenStreetMap(API キー不要)
photomap build ... --map leaflet

# Google マップ(Maps JavaScript API のキーが必要)
photomap build ... --map google --maps-key "$GOOGLE_MAPS_API_KEY"
```

生成される `photos.kml` は **Google マイマップ**(<https://mymaps.google.com/>)に
インポートできます。Google マップ上で共有したい場合はこちらを使ってください。

### 地名の解決(逆ジオコーディング)

```bash
--geocode osm      # 既定。OpenStreetMap Nominatim。キー不要、1リクエスト/秒
--geocode google   # Google Geocoding API(--maps-key が必要、高精度)
--geocode none     # 地名を引かない(オフライン)
```

結果は `~/.cache/photomap/geocode.json` にキャッシュされます。

### 解説

指定しない場合は、撮影時刻・地名・カメラ・前後の写真との間隔から
日本語のキャプションを機械的に組み立てます(オフラインで完結)。

`--claude` を付けると Anthropic API(既定 `claude-opus-5`)で、その日の流れを
踏まえた解説と全体サマリを生成します。`--vision` を足すと写真そのものも
モデルに渡すため、被写体に踏み込んだ解説になります。

```bash
export ANTHROPIC_API_KEY=...
photomap build ... --claude --vision --effort high
```

API 呼び出しが失敗した場合や `anthropic` が未インストールの場合は、自動的に
ルールベースの解説にフォールバックします(ドキュメント生成自体は必ず完了します)。

---

## 出力

```
out/
├── index.html        # 地図 + 行程 + 写真と解説(印刷/PDF 化にも対応)
├── document.md       # Markdown 版(ブログ・Notion 用)
├── photos.geojson    # 各写真の点と移動ルート
├── photos.kml        # Google マイマップ用
└── assets/           # ドキュメントから参照する画像
```

`index.html` は次の構成です。

- **地図** — 立ち寄り地点に番号つきのピン、地点間を結ぶ移動ルート
- **その日の行程** — 近接する写真をまとめた地点リスト(クリックで地図が追従)
- **写真と解説** — 時系列のカード。写真・時刻・地名・解説・座標リンク

地点のまとめ方は `--cluster-radius`(既定 250m)と `--cluster-gap`(既定 45分)で
調整できます。

---

## 主なオプション

| オプション | 既定 | 説明 |
|---|---|---|
| `--date` | (必須) | 対象日 `YYYY-MM-DD` |
| `--end-date` | — | 範囲指定の終了日(当日を含む) |
| `--tz` | `Asia/Tokyo` | 日付判定と表示に使うタイムゾーン |
| `--format` | `html md geojson` | 出力形式(`kml` も指定可) |
| `--cluster-radius` | `250` | 同一地点とみなす半径(m) |
| `--cluster-gap` | `45` | 地点を区切る時間間隔(分) |
| `--no-images` | — | 画像をコピーせず本文だけ生成 |
| `--include-videos` | — | 動画も対象にする |

---

## 制限事項

- **地図タイルの取得にはネットワークが必要です。** オフラインで開いた場合、地図の
  代わりに説明を表示し、各写真の座標リンクからは地図を開けるようにしています。
- HEIC のサムネイル生成には Pillow に加えて `pillow-heif` が必要です。無い場合は
  元ファイルをコピーします(ブラウザによっては表示できません)。
- 移動ルートは地点間を **直線** で結んだ近似です。実際の経路探索は行いません。
- `photos.kml` の Google マイマップへの取り込みは手動操作です(API 経由での
  マイマップ作成は Google が公開していません)。

---

## 開発

```bash
python -m unittest discover -s tests -v
```

外部通信もアカウントも不要でテストが完結します(EXIF ライタを内蔵しており、
ジオタグ入り画像を合成して読み戻す往復テストを行っています)。

```
photomap/
├── cli.py              # コマンドライン
├── exif.py             # 依存なしの EXIF リーダ(JPEG / PNG / 総当たり)
├── models.py           # Photo / Place
├── cluster.py          # 立ち寄り地点へのまとめ
├── geocode.py          # 逆ジオコーディング + キャッシュ
├── narrate.py          # 解説生成(ルールベース / Claude)
├── assets.py           # サムネイル生成・画像配置
├── google_auth.py      # OAuth 2.0 (PKCE)
├── testkit.py          # サンプルデータ生成 + EXIF ライタ
├── sources/            # takeout / local / google_photos
└── render/             # html / markdown / geo(GeoJSON, KML)
```
