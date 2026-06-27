#!/usr/bin/env python3
"""
ブログ記事生成システム - CLIエントリーポイント

使い方:
  python main.py index              # 記事インデックスを構築
  python main.py suggest            # 新テーマを提案
  python main.py generate "テーマ"  # 記事を生成
  python main.py search "キーワード" # 類似記事を検索
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent))
from src.indexer import build_index, load_index, search as index_search
from src.generator import generate_article
from src.theme_suggester import suggest_themes

console = Console()


def load_config(config_path: str = "config.yaml") -> dict:
    p = Path(config_path)
    if not p.exists():
        console.print(f"[red]設定ファイルが見つかりません: {p}[/red]")
        sys.exit(1)
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


@click.group()
def cli():
    """ブログ記事生成システム"""
    pass


@cli.command()
@click.option("--config", default="config.yaml", help="設定ファイルのパス")
def index(config):
    """既存のブログ記事からインデックスを構築する"""
    cfg = load_config(config)
    console.print(Panel("[bold cyan]インデックス構築開始[/bold cyan]"))
    result = build_index(
        articles_dir=cfg["articles_dir"],
        index_path=cfg["index_path"],
        min_length=cfg.get("min_article_length", 100),
    )
    if result:
        console.print(f"[green]完了: {result['total']} 件の記事をインデックスしました[/green]")


@cli.command()
@click.argument("query")
@click.option("--top", default=5, help="表示件数")
@click.option("--config", default="config.yaml", help="設定ファイルのパス")
def search(query, top, config):
    """キーワードで類似記事を検索する"""
    cfg = load_config(config)
    idx = load_index(cfg["index_path"])
    results = index_search(query, idx, top_k=top)

    if not results:
        console.print("[yellow]該当する記事が見つかりませんでした。[/yellow]")
        return

    table = Table(title=f'"{query}" の検索結果', show_lines=True)
    table.add_column("スコア", style="cyan", width=8)
    table.add_column("タイトル", style="bold")
    table.add_column("日付", width=12)
    table.add_column("プレビュー")

    for r in results:
        table.add_row(
            str(r["score"]),
            r["title"],
            r.get("date", "-"),
            r.get("preview", "")[:80] + "...",
        )

    console.print(table)


@cli.command()
@click.option("--n", default=10, help="提案するテーマ数")
@click.option("--focus", default="", help="重視したいキーワードやジャンル")
@click.option("--config", default="config.yaml", help="設定ファイルのパス")
def suggest(n, focus, config):
    """既存記事を分析して新しいテーマを提案する"""
    cfg = load_config(config)
    console.print(Panel("[bold cyan]テーマ提案を生成中...[/bold cyan]"))

    raw = suggest_themes(cfg, n_themes=n, focus=focus)

    # JSONブロックを抽出
    try:
        start = raw.find("[")
        end = raw.rfind("]") + 1
        themes = json.loads(raw[start:end])

        table = Table(title="新テーマ候補", show_lines=True)
        table.add_column("#", width=4)
        table.add_column("タイトル", style="bold")
        table.add_column("説明")
        table.add_column("キーワード", style="cyan")

        for i, t in enumerate(themes, 1):
            table.add_row(
                str(i),
                t.get("title", ""),
                t.get("description", ""),
                ", ".join(t.get("keywords", [])),
            )

        console.print(table)
    except (json.JSONDecodeError, ValueError):
        console.print(raw)


@cli.command()
@click.argument("theme")
@click.option("--output", default="", help="出力ファイル名（省略時は自動生成）")
@click.option("--refs", default=None, type=int, help="参照する記事数（省略時はconfig値を使用）")
@click.option("--config", default="config.yaml", help="設定ファイルのパス")
@click.option("--preview", is_flag=True, help="ターミナルでプレビュー表示する")
def generate(theme, output, refs, config, preview):
    """指定したテーマでブログ記事を生成する"""
    cfg = load_config(config)
    console.print(Panel(f"[bold cyan]記事生成中: {theme}[/bold cyan]"))

    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[red]ANTHROPIC_API_KEY 環境変数が設定されていません。[/red]")
        sys.exit(1)

    article, used_refs = generate_article(theme=theme, config=cfg, top_k=refs)

    # 出力ファイルパスを決定
    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    if not output:
        slug = theme[:30].replace(" ", "-").replace("/", "-")
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = str(out_dir / f"{date_str}_{slug}.md")

    Path(output).write_text(article, encoding="utf-8")
    console.print(f"[green]保存しました: {output}[/green]")

    # 参照記事を表示
    if used_refs:
        console.print("\n[bold]参照した記事:[/bold]")
        for i, ref in enumerate(used_refs, 1):
            console.print(f"  {i}. [{ref.get('score', '')}] {ref['title']}")

    if preview:
        console.print("\n" + "=" * 60)
        console.print(Markdown(article))


if __name__ == "__main__":
    cli()
