# ブログ記事生成システム

2018年から蓄積してきた既存ブログ記事を参照しながら、新しいテーマの記事を自動生成するCLIツール。

## 構成

```
.
├── main.py              # CLIエントリーポイント
├── config.yaml          # 設定ファイル
├── requirements.txt
├── src/
│   ├── indexer.py       # 記事インデックス構築・検索（TF-IDF）
│   ├── generator.py     # Claude APIによる記事生成
│   └── theme_suggester.py # 新テーマ提案
├── articles/            # 既存ブログ記事を配置（.md / .txt）
├── output/              # 生成された記事の出力先
└── index/               # 検索インデックス（自動生成）
```

## セットアップ

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="your-api-key"
```

## 使い方

### 1. 記事インデックスの構築

`articles/` ディレクトリに既存の記事ファイル（`.md` / `.txt`）を配置してから実行：

```bash
python main.py index
```

- YAML front matter（`title`, `date`）に対応
- ファイル名に `2024-01-15-` 形式の日付があれば自動抽出
- 約1900件でも数分以内で完了

### 2. 新テーマの提案

```bash
python main.py suggest
python main.py suggest --n 15 --focus "健康・運動"
```

既存記事のキーワード分布と記事タイトルを分析して、まだ書かれていなそうなテーマを提案します。

### 3. 記事の生成

```bash
python main.py generate "瞑想を3ヶ月続けて変わったこと"
python main.py generate "在宅ワークで集中力を保つ5つの習慣" --preview
python main.py generate "テーマ" --refs 8 --output ./output/my_article.md
```

| オプション | 説明 |
|-----------|------|
| `--refs N` | 参照する類似記事数（デフォルト: config値） |
| `--output PATH` | 出力先ファイルパス |
| `--preview` | ターミナルでMarkdownプレビュー表示 |

### 4. 類似記事の検索

```bash
python main.py search "断捨離 ライフスタイル"
python main.py search "勉強法" --top 10
```

## 設定（config.yaml）

| キー | 説明 | デフォルト |
|------|------|-----------|
| `articles_dir` | 既存記事ディレクトリ | `./articles` |
| `output_dir` | 生成記事の出力先 | `./output` |
| `model` | 使用するClaudeモデル | `claude-sonnet-4-6` |
| `max_reference_articles` | 参照記事数 | `5` |
| `blog_language` | 言語 (`ja` / `en`) | `ja` |
| `author_name` | 著者名 | *(空)* |
| `blog_style_hint` | 文体ヒント | *(空)* |

## 記事フォーマット

既存記事はYAML front matter付きのMarkdownを推奨：

```markdown
---
title: 記事タイトル
date: 2024-01-15
tags: [タグ1, タグ2]
---

本文...
```

front matterがない `.txt` や `.md` も処理可能。ファイル名から日付を推測します。

## 処理の仕組み

1. **インデックス構築**: 日本語n-gram + 英単語でTF-IDFベクトルを生成
2. **類似記事検索**: クエリとのコサイン類似度で上位k件を選択
3. **記事生成**: 選択した記事の本文をコンテキストとしてClaudeに渡し、著者スタイルを踏まえた新記事を生成
