"""Google OAuth 2.0(インストール済みアプリ + PKCE)。外部ライブラリ不要。

Google Cloud Console で「デスクトップアプリ」のOAuthクライアントを作成し、
ダウンロードした client_secret JSON のパスを渡す。
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"

SCOPE_PICKER = "https://www.googleapis.com/auth/photospicker.mediaitems.readonly"
# 2025-03-31 以降、このスコープでユーザーのライブラリ全体を読むことは
# 原則できなくなった(アプリが作成したメディアのみ)。互換目的で残している。
SCOPE_LIBRARY = "https://www.googleapis.com/auth/photoslibrary.readonly"

DEFAULT_TOKEN_PATH = os.path.expanduser("~/.config/photomap/token.json")


class AuthError(Exception):
    pass


# --- 低レベル HTTP -------------------------------------------------------


def http_json(
    url: str, *, method: str = "GET", token: str | None = None, body: dict | None = None
) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:800]
        raise AuthError(f"{method} {url} が {exc.code} を返しました: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AuthError(f"{method} {url} に接続できません: {exc.reason}") from exc
    return json.loads(raw) if raw else {}


def download(url: str, dest: str, token: str | None = None) -> None:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = urllib.request.Request(url, headers=headers)
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp, open(dest, "wb") as fh:
            while chunk := resp.read(1 << 16):
                fh.write(chunk)
    except urllib.error.HTTPError as exc:
        raise AuthError(f"ダウンロード失敗 ({exc.code}): {url[:120]}") from exc


# --- 資格情報 -------------------------------------------------------------


class Credentials:
    def __init__(self, data: dict, path: str):
        self.data = data
        self.path = path

    @property
    def scopes(self) -> list[str]:
        return self.data.get("scope", "").split()

    def token(self) -> str:
        if time.time() >= self.data.get("expires_at", 0) - 60:
            self._refresh()
        return self.data["access_token"]

    def _refresh(self) -> None:
        if not self.data.get("refresh_token"):
            raise AuthError("リフレッシュトークンがありません。`photomap auth` をやり直してください。")
        payload = urllib.parse.urlencode(
            {
                "client_id": self.data["client_id"],
                "client_secret": self.data.get("client_secret", ""),
                "refresh_token": self.data["refresh_token"],
                "grant_type": "refresh_token",
            }
        ).encode()
        req = urllib.request.Request(
            TOKEN_URI,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                tok = json.load(resp)
        except urllib.error.HTTPError as exc:
            raise AuthError(
                "アクセストークンの更新に失敗しました。`photomap auth` をやり直してください。"
            ) from exc
        self.data["access_token"] = tok["access_token"]
        self.data["expires_at"] = time.time() + int(tok.get("expires_in", 3600))
        self.save()

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, ensure_ascii=False, indent=2)
        os.chmod(self.path, 0o600)


def load_credentials(path: str = DEFAULT_TOKEN_PATH) -> Credentials:
    if not os.path.exists(path):
        raise AuthError(
            f"認証情報がありません ({path})。まず `photomap auth --client-secrets <file>` を実行してください。"
        )
    with open(path, "r", encoding="utf-8") as fh:
        return Credentials(json.load(fh), path)


# --- 認可フロー -----------------------------------------------------------


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    result: dict = {}

    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler の規約)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _CallbackHandler.result = {k: v[0] for k, v in query.items()}
        ok = "code" in _CallbackHandler.result
        body = (
            "<h2>認証が完了しました。ターミナルに戻ってください。</h2>"
            if ok
            else f"<h2>認証に失敗しました: {_CallbackHandler.result.get('error', '不明')}</h2>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"<!doctype html><meta charset='utf-8'>{body}".encode("utf-8"))

    def log_message(self, *_args):  # サーバのアクセスログを抑止
        pass


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def authorize(
    client_secrets: str,
    scopes: list[str],
    token_path: str = DEFAULT_TOKEN_PATH,
    open_browser: bool = True,
) -> Credentials:
    with open(os.path.expanduser(client_secrets), "r", encoding="utf-8") as fh:
        conf = json.load(fh)
    section = conf.get("installed") or conf.get("web")
    if not section:
        raise AuthError(
            "client_secrets の形式が不正です(『デスクトップアプリ』の JSON を指定してください)。"
        )
    client_id = section["client_id"]
    client_secret = section.get("client_secret", "")

    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    state = secrets.token_urlsafe(16)
    port = _free_port()
    redirect_uri = f"http://127.0.0.1:{port}"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    url = f"{AUTH_URI}?{urllib.parse.urlencode(params)}"

    server = http.server.HTTPServer(("127.0.0.1", port), _CallbackHandler)
    _CallbackHandler.result = {}
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    print("ブラウザで次のURLを開いて Google アカウントを認可してください:\n")
    print(f"  {url}\n")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001 - ヘッドレス環境では単に無視
            pass

    thread.join(timeout=300)
    server.server_close()
    result = _CallbackHandler.result
    if not result.get("code"):
        raise AuthError(f"認可コードを取得できませんでした: {result.get('error', 'タイムアウト')}")
    if result.get("state") != state:
        raise AuthError("state が一致しません(CSRF の可能性)。やり直してください。")

    payload = urllib.parse.urlencode(
        {
            "code": result["code"],
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        }
    ).encode()
    req = urllib.request.Request(
        TOKEN_URI, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            tok = json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise AuthError(f"トークン交換に失敗しました: {detail}") from exc

    creds = Credentials(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "access_token": tok["access_token"],
            "refresh_token": tok.get("refresh_token", ""),
            "scope": tok.get("scope", " ".join(scopes)),
            "expires_at": time.time() + int(tok.get("expires_in", 3600)),
        },
        os.path.expanduser(token_path),
    )
    creds.save()
    return creds
