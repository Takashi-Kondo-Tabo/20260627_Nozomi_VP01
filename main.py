#!/usr/bin/env python3
"""
ブログ記事生成システム - CLIエントリーポイント

使い方:
  python main.py index                     # 記事インデックスを構築
  python main.py stats                     # インデックス統計を表示
  python main.py search "キーワード"        # 類似記事を検索
  python main.py suggest                   # 新テーマを提案
  python main.py generate "テーマ"          # 記事を生成
  python main.py batch themes.txt          # 複数テーマを一括生成
  python main.py analyze-style             # 文体を分析してキャッシュ
  python main.py interactive               # 対話モード
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent))
from src.generator import batch_generate, generate_article
from src.indexer import build_index, load_index
from src.indexer import search as index_search
from src.stats import compute_stats, format_stats_table
from src.style_analyzer import get_style_guide
from src.theme_suggester import suggest_themes

console = Console()


def load_config(config_path: str = "config.yaml") -> dict:
    p = Path(config_path)
    if not p.exists():
        console.print(f"[red]設定ファイルが見つかりません: {p}[/red]")
        sys.exit(1)
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _check_api_key():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print(
            "[red]ANTHROPIC_API_KEY 環境変数が設定されていません。[/red]\n"
            "  export ANTHROPIC_API_KEY='your-api-key'"
        )
        sys.exit(1)


def _save_article(article: str, theme: str, output_dir: Path, output_path: str = "") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_path:
        p = Path(output_path)
    else:
        slug = re.sub(r'[\s/\\:*?"<>|]', "-", theme)[:40].strip("-")
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        p = output_dir / f"{date_str}_{slug}.md"
    p.write_text(article, encoding="utf-8")
    return p


# ----------------------------------------------------------------
# CLI コマンド群
# ----------------------------------------------------------------

@click.group()
def cli():
    """ブログ記事生成システム"""
    pass


@cli.command()
@click.option("--config", default="config.yaml")
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
@click.option("--config", default="config.yaml")
def stats(config):
    """インデックス済み記事の統計・傾向を表示する"""
    cfg = load_config(config)
    idx = load_index(cfg["index_path"])
    s = compute_stats(idx)
    console.print(Panel("[bold cyan]記事統計[/bold cyan]"))
    console.print(format_stats_table(s))


@cli.command()
@click.argument("query")
@click.option("--top", default=5)
@click.option("--config", default="config.yaml")
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
            (r.get("preview", "")[:80] + "..."),
        )
    console.print(table)


@cli.command()
@click.option("--n", default=10)
@click.option("--focus", default="")
@click.option("--config", default="config.yaml")
def suggest(n, focus, config):
    """既存記事を分析して新しいテーマを提案する"""
    _check_api_key()
    cfg = load_config(config)
    console.print(Panel("[bold cyan]テーマ提案を生成中...[/bold cyan]"))
    raw = suggest_themes(cfg, n_themes=n, focus=focus)

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
@click.option("--output", default="")
@click.option("--refs", default=None, type=int)
@click.option("--config", default="config.yaml")
@click.option("--preview", is_flag=True)
@click.option("--use-style-guide/--no-style-guide", default=True,
              help="文体ガイドを使用する（デフォルト: 使用）")
@click.option("--instruction", default="", help="追加の生成指示")
def generate(theme, output, refs, config, preview, use_style_guide, instruction):
    """指定したテーマでブログ記事を生成する"""
    _check_api_key()
    cfg = load_config(config)
    idx = load_index(cfg["index_path"])

    style_guide = ""
    if use_style_guide:
        try:
            style_guide = get_style_guide(idx, cfg)
        except Exception:
            pass

    console.print(Panel(f"[bold cyan]記事生成中: {theme}[/bold cyan]"))

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Claude APIに接続中...", total=None)
        article, used_refs = generate_article(
            theme=theme, config=cfg, index=idx,
            top_k=refs, style_guide=style_guide, extra_instruction=instruction
        )

    out_path = _save_article(article, theme, Path(cfg["output_dir"]), output)
    console.print(f"[green]保存しました: {out_path}[/green]")

    if used_refs:
        console.print("\n[bold]参照した記事:[/bold]")
        for i, ref in enumerate(used_refs, 1):
            console.print(f"  {i}. [{ref.get('score', '')}] {ref['title']}")

    if preview:
        console.print("\n" + "=" * 60)
        console.print(Markdown(article))


@cli.command()
@click.argument("themes_file", type=click.Path(exists=True))
@click.option("--config", default="config.yaml")
@click.option("--use-style-guide/--no-style-guide", default=True)
def batch(themes_file, config, use_style_guide):
    """
    テキストファイルに記載した複数テーマを一括生成する。

    themes.txt の書式（1行1テーマ）:
      睡眠の質を上げる方法
      在宅ワークで集中力を保つコツ
      読書記録の続け方
    """
    _check_api_key()
    cfg = load_config(config)
    idx = load_index(cfg["index_path"])
    out_dir = Path(cfg["output_dir"])

    themes = [
        l.strip() for l in Path(themes_file).read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.startswith("#")
    ]
    if not themes:
        console.print("[yellow]テーマが見つかりませんでした。[/yellow]")
        return

    style_guide = ""
    if use_style_guide:
        try:
            style_guide = get_style_guide(idx, cfg)
            console.print("[dim]文体ガイドを読み込みました[/dim]")
        except Exception:
            pass

    console.print(Panel(f"[bold cyan]一括生成: {len(themes)} 件[/bold cyan]"))

    def on_progress(i, total, theme, path):
        console.print(f"[green][{i}/{total}][/green] {theme}")
        console.print(f"       → {path}")

    batch_generate(
        themes=themes, config=cfg, index=idx,
        output_dir=out_dir, style_guide=style_guide,
        on_progress=on_progress,
    )
    console.print(f"\n[green]完了! {len(themes)} 件を {out_dir} に保存しました。[/green]")


@cli.command("analyze-style")
@click.option("--config", default="config.yaml")
@click.option("--refresh", is_flag=True, help="キャッシュを無視して再分析する")
def analyze_style(config, refresh):
    """既存記事から著者の文体を分析してキャッシュする"""
    _check_api_key()
    cfg = load_config(config)
    idx = load_index(cfg["index_path"])

    cache = Path("index/style_guide.txt")
    if refresh and cache.exists():
        cache.unlink()
        console.print("[dim]キャッシュを削除しました[/dim]")

    console.print(Panel("[bold cyan]文体分析中...[/bold cyan]"))
    guide = get_style_guide(idx, cfg)
    console.print(Panel(guide, title="文体ガイド", border_style="green"))
    console.print(f"[dim]キャッシュ保存先: {cache}[/dim]")


@cli.command()
@click.option("--config", default="config.yaml")
def interactive(config):
    """
    対話モード: テーマ提案→選択→生成を一連の流れで操作する
    """
    _check_api_key()
    cfg = load_config(config)
    idx = load_index(cfg["index_path"])
    out_dir = Path(cfg["output_dir"])

    console.print(Panel("[bold cyan]ブログ記事生成システム - 対話モード[/bold cyan]"))

    # 文体ガイドの読み込み
    style_guide = ""
    cache = Path("index/style_guide.txt")
    if cache.exists():
        style_guide = cache.read_text(encoding="utf-8")
        console.print("[dim]文体ガイドを読み込みました[/dim]")
    else:
        if Confirm.ask("文体分析を実行しますか？（初回のみ・推奨）"):
            from src.style_analyzer import analyze_style_with_claude
            with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
                p.add_task("文体を分析中...", total=None)
                style_guide = analyze_style_with_claude(idx, cfg)
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(style_guide, encoding="utf-8")
            console.print("[green]文体ガイドを保存しました[/green]")

    while True:
        console.rule()
        action = Prompt.ask(
            "\n何をしますか？",
            choices=["suggest", "generate", "search", "quit"],
            default="suggest",
        )

        if action == "quit":
            console.print("[bold]終了します。[/bold]")
            break

        elif action == "search":
            query = Prompt.ask("検索キーワード")
            results = index_search(query, idx, top_k=5)
            if not results:
                console.print("[yellow]見つかりませんでした。[/yellow]")
            else:
                for i, r in enumerate(results, 1):
                    console.print(f"  {i}. [{r['score']}] {r['title']} ({r.get('date', '')})")

        elif action == "suggest":
            focus = Prompt.ask("重視したいジャンル・キーワード（空欄でOK）", default="")
            n = IntPrompt.ask("提案するテーマ数", default=8)

            with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
                p.add_task("テーマを生成中...", total=None)
                raw = suggest_themes(cfg, index=idx, n_themes=n, focus=focus)

            themes_list = []
            try:
                start = raw.find("[")
                end = raw.rfind("]") + 1
                themes_list = json.loads(raw[start:end])
            except (json.JSONDecodeError, ValueError):
                console.print(raw)
                continue

            console.print()
            for i, t in enumerate(themes_list, 1):
                console.print(
                    f"  [cyan]{i:2d}.[/cyan] [bold]{t.get('title', '')}[/bold]"
                )
                console.print(f"       {t.get('description', '')}")

            console.print()
            choice = Prompt.ask(
                "生成するテーマ番号を入力（スキップはEnter）",
                default="",
            )
            if not choice.strip():
                continue

            try:
                picked_idx = int(choice) - 1
                theme = themes_list[picked_idx]["title"]
            except (ValueError, IndexError):
                console.print("[red]無効な番号です。[/red]")
                continue

            _do_generate(theme, cfg, idx, out_dir, style_guide)

        elif action == "generate":
            theme = Prompt.ask("記事のテーマを入力してください")
            _do_generate(theme, cfg, idx, out_dir, style_guide)


def _do_generate(theme: str, cfg: dict, idx: dict, out_dir: Path, style_guide: str):
    instruction = Prompt.ask("追加指示（任意）", default="")
    refs_count = IntPrompt.ask("参照記事数", default=cfg.get("max_reference_articles", 5))
    want_preview = Confirm.ask("生成後にプレビューを表示しますか？", default=False)

    console.print(f"\n[bold]生成中: {theme}[/bold]")
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as p:
        p.add_task("Claude APIに接続中...", total=None)
        article, used_refs = generate_article(
            theme=theme, config=cfg, index=idx,
            top_k=refs_count, style_guide=style_guide,
            extra_instruction=instruction,
        )

    out_path = _save_article(article, theme, out_dir)
    console.print(f"[green]保存しました: {out_path}[/green]")

    if used_refs:
        console.print("[dim]参照記事:[/dim]")
        for ref in used_refs:
            console.print(f"  [dim]- {ref['title']}[/dim]")

    if want_preview:
        console.print()
        console.print(Markdown(article))


if __name__ == "__main__":
    cli()
