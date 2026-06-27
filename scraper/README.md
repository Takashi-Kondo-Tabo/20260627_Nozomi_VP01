# ブログ記事スクレイパー

**このスクレイパーはお手元のPC（ローカル環境）で実行してください。**  
クラウド環境からはFC2ブログへのアクセスが制限されているためです。

## 手順

### 1. 依存ライブラリのインストール

```bash
cd scraper
pip install -r requirements.txt
```

### 2. スクレイパーの実行

```bash
python scrape_fc2.py
```

`../articles/` ディレクトリに記事が保存されます。

- 1900件の場合、約1〜2時間かかります（サーバー負荷軽減のため1.5〜3秒/リクエスト）
- 途中で中断しても、再実行すると続きから取得します
- 進捗は標準出力に表示されます

### 3. 記事取得後の作業

```bash
# リポジトリルートに戻る
cd ..

# インデックス構築
python main.py index

# テーマ提案
python main.py suggest

# 記事生成
python main.py generate "書きたいテーマ" --preview
```

## 出力ファイル形式

```
articles/
├── 2024-01-15_0001_記事タイトル.md
├── 2024-02-03_0002_記事タイトル.md
...
```

各ファイルはYAML front matter付きのMarkdown形式です：

```markdown
---
title: "記事タイトル"
date: 2024-01-15
tags: [タグ1, タグ2]
source_url: https://newhabits.blog.fc2.com/blog-entry-XXXX.html
---

本文...
```

## トラブルシューティング

**記事が取れない場合**  
FC2ブログのCSS構造はテーマによって異なります。`scrape_fc2.py` の `extract_article()` 関数内のセレクタを調整してください。  
ブラウザの開発者ツール（F12）で記事本文の実際のクラス名を確認できます。
