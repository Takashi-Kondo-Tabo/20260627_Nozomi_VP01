# Haiku-Dojo（俳句道場）

AIと詠み、AIが採点し、ちょいたしカードで磨き上げる俳句Webアプリ。
GitHub Pages で公開: https://takashi-kondo-tabo.github.io/20260627_Nozomi_VP01/
（リポジトリ `Takashi-Kondo-Tabo/20260627_Nozomi_VP01` の `claude/haiku-generator-scoring-app-kki5x0` ブランチが公開元）

## ファイル構成

- `index.html` — ひとりで詠むモード（1ファイル完結。CSS/JSはインライン）
- `cards.html` — ちょいたしカード一覧
- `kukai.html` + `kukai.js` + `kukai-db.js` + `firebase-config.js` — 句会モード（複数人）
- `CARD_DECK` は index.html / cards.html / kukai.js の3か所にある。変更時は3つとも揃える

## 句会モードの流れ

偏愛検定（`../Henai-Kentei`）のルームコード方式を移植したもの。

1. ホストがルームを作成（5桁コード）→ 参加者はコードかURL（`kukai.html#コード`）で入室
2. ホストがお題（季語・テーマ）を決める（AIに出してもらうか手入力）→ 開始
3. 全員が一句詠む（composing）→ AIが全員分を採点（scoring1）
4. 各自ちょいたしカードを1枚引き（交換は1回まで）、推敲（brushup）→ AIが再採点（scoring2）
5. 自分以外の全員の句を褒め合う（praising。褒めポイントを1つ以上＋ひとこと）
6. 結果: 初句→カード→推敲句、点数の伸び、もらった褒め言葉。「いちばん伸びた」「いちばん褒められた」

- AI（Claude API）を呼ぶのは**ホストの端末だけ**。参加者はAPIキー不要。ホストがページを閉じると採点が止まる（再読み込みで再開）
- フェーズ遷移は偏愛検定と同じく、条件成立を検知したクライアントが `status` を進める（Cloud Functions不使用）
- 部屋と参加者は別リスナーで届くため、新フェーズの通知が参加者データより先に着くことがある。
  描画・採点はデータが揃ってから行うようにしている（`computeScreenKey` / `runHostScoring` のコメント参照）

## Firebase

偏愛検定と同じ Firebase プロジェクト `henai-kentei` を共用し、コレクション `haikuRooms` で分けている。
セキュリティルールは1プロジェクトに1つなので、原本は `../Henai-Kentei/firestore.rules`（haikuRooms の節を含む）。
ルールのデプロイは Henai-Kentei ディレクトリから `npx firebase-tools deploy --only firestore:rules`。

```
haikuRooms/{roomCode}
  status: 'waiting' | 'composing' | 'scoring1' | 'brushup' | 'scoring2' | 'praising' | 'results'
  hostId, prompt { kigo, theme, sceneHint, techniqueTip }, createdAt

haikuRooms/{roomCode}/participants/{participantId}
  name, emoji, joinedAt
  text1, submitted1, ai1 { score, goodPoint, improvement, kigo, kigoDescription }
  card { icon, title, tip }, cardSwapped
  text2, submitted2, ai2 { ... }

haikuRooms/{roomCode}/praises/{raterId_targetId}
  raterId, targetId, points[], comment
```

## ローカル確認

ESモジュールのため `file://` では動かない。`npx serve .` などで静的配信して開く。
