#!/bin/bash
# ブログ記事生成システム Web GUI 起動スクリプト

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# .env からAPIキーを読み込む
if [ -f ".env" ]; then
    API_KEY=$(grep "^ANTHROPIC_API_KEY=" .env | cut -d'=' -f2- | tr -d '\r\n')
    if [ -n "$API_KEY" ]; then
        export ANTHROPIC_API_KEY="$API_KEY"
    fi
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "警告: ANTHROPIC_API_KEY が設定されていません。"
    echo ".env ファイルにAPIキーを記載してください（生成機能が使えません）。"
fi

# Python の確認
PYTHON=""
for cmd in /Library/Developer/CommandLineTools/usr/bin/python3 python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "エラー: Python が見つかりません。"
    exit 1
fi

# Flaskの確認
if ! $PYTHON -c "import flask" &>/dev/null; then
    echo "Flaskをインストールしています..."
    $PYTHON -m pip install flask
fi

echo "==============================="
echo "  ブログ記事生成システム Web GUI"
echo "==============================="
echo ""

if [ "$1" == "--lan" ]; then
    export HOST="0.0.0.0"
    LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
    echo "同じWi-Fi内の他端末（iPadなど）からアクセスできます。"
    if [ -n "$LAN_IP" ]; then
        echo "iPadのブラウザで http://${LAN_IP}:5050 を開いてください。"
    fi
else
    echo "起動後、ブラウザで http://127.0.0.1:5050 を開いてください。"
    echo "（iPadなど他端末から使う場合は: bash start_web.sh --lan）"
fi
echo "終了するには Ctrl+C を押してください。"
echo ""

$PYTHON webapp/app.py
