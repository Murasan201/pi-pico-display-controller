# Communication Specification

Raspberry Pi 5（ホスト）と Raspberry Pi Pico 2 W 間の Wi-Fi TCP ソケット通信仕様。

## アーキテクチャ概要

```
┌─────────────────────────────────────────────────┐
│  Raspberry Pi 5 (Host)                          │
│                                                 │
│  pico-ctl.sh ──FIFO──▶ command_server.py        │
│  Claude Code ─FIFO──▶    ┃  TCP :5000           │
│                          ┃  accept_timeout=1.0s │
│                          ┃  recv_timeout=2.0s   │
└──────────────────────────╂──────────────────────┘
                           ┃ Wi-Fi (TCP)
                           ┃ 改行区切り JSON
┌──────────────────────────╂──────────────────────┐
│  Pico 2 W (Client)       ┃                      │
│                          ┃                      │
│  main.py ◀───────────────┛                      │
│    SOCKET_TIMEOUT=0.75s                         │
│    RECONNECT_DELAY=5s                           │
│    タイムアウト時にタッチポーリング実行          │
└─────────────────────────────────────────────────┘
```

## 接続フロー

1. ホストが `command_server.py` で TCP サーバを起動（`0.0.0.0:5000`）
2. Pico が Wi-Fi に接続後、`config.py` の `TCP_SERVER_HOST:TCP_SERVER_PORT` に TCP 接続
3. ホストが接続を受け付け、クライアントごとにハンドラスレッドを起動
4. 双方向の改行区切り JSON でコマンド・レスポンスを交換
5. 接続断の場合、Pico は `RECONNECT_DELAY`（5秒）後に自動再接続

## 接続パラメータ

| パラメータ | ホスト側 | Pico側 | 定義場所 |
|---|---|---|---|
| バインドアドレス | `0.0.0.0` | N/A（クライアント） | `command_server.py` |
| 接続先 | N/A（サーバ） | `192.168.11.16` | `src/config.py` |
| ポート | `5000` | `5000` | 両方の config |
| accept タイムアウト | `1.0s` | N/A | `command_server.py` |
| recv タイムアウト | `2.0s` | N/A | `command_server.py` |
| ソケットタイムアウト | N/A | `0.75s` | `src/config.py` |
| 受信バッファ | `1024` bytes | `1024` bytes | 両方 |
| 再接続待機 | N/A | `5s` | `src/config.py` |
| Wi-Fi 接続タイムアウト | N/A | `15s` | `src/main.py` |
| 最大同時クライアント | `2`（listen backlog） | N/A | `command_server.py` |

## タイムアウトとフリーズ防止

ソケット通信でプロセスがブロックして停止する問題を防ぐため、全ての I/O 操作にタイムアウトを設定している。

### ホスト側（command_server.py）

| 操作 | タイムアウト | タイムアウト時の動作 |
|---|---|---|
| `server.accept()` | 1.0s | `socket.timeout` → `continue`（`running` フラグを再チェック） |
| `conn.recv()` | 2.0s | `socket.timeout` → `continue`（シャットダウン監視のため定期起床） |
| `conn.recv()` | — | `ConnectionResetError` / `BrokenPipeError` / `OSError` → `break`（切断処理） |

### Pico側（main.py）

| 操作 | タイムアウト | タイムアウト時の動作 |
|---|---|---|
| `sock.recv()` | 0.75s | `OSError(110)` (ETIMEDOUT) → タッチパネルをポーリングし `continue` |
| `sock.recv()` | — | その他の `OSError` → `raise`（再接続処理へ） |
| 空チャンク受信 | — | `OSError("socket closed")` を発行 → 再接続処理へ |

> **注**: MicroPython には `socket.timeout` 例外が存在しない。タイムアウトは `OSError` の errno `110`（ETIMEDOUT）として発生する。

### FIFO 書き込み（Claude Code / pico-ctl.sh → command_server.py）

FIFO はブロッキング操作のため、書き込み側は必ず `timeout` コマンドでラップする。

```bash
# 正しい書き込み方法（3秒タイムアウト）
timeout 3 bash -c "printf '%s\n' '<json>' > /tmp/pico-cmd-fifo"

# 直接書き込みは禁止（読み取り側が不在の場合、永遠にブロックする）
# echo '<json>' > /tmp/pico-cmd-fifo  ← NG
```

## プロトコル

- **エンコーディング**: UTF-8
- **フレーミング**: 改行（`\n`）区切り。1コマンド = 1行の JSON
- **方向**: 双方向（ホスト→Pico: コマンド、Pico→ホスト: レスポンス/イベント）
- **部分送信禁止**: ホストは完全な JSON 行を送ること。Pico は `\n` まで内部バッファに蓄積

## コマンド（ホスト → Pico）

### set_mode

表示モードを切り替える。

```json
{
  "cmd": "set_mode",
  "mode": "<モード名>",
  "payload": { ... }
}
```

**対応モード:**

| モード | 必須ペイロード | 説明 |
|---|---|---|
| `status_datetime` | `date`, `time`, `weather`, `temp` | 日時・天気表示 |
| `tasks_short` | `tasks` (配列) | 短期タスク一覧（最大4件） |
| `free_text` | `text` | 自由テキスト表示 |

**例: 日時・天気モード**
```json
{
  "cmd": "set_mode",
  "mode": "status_datetime",
  "payload": {
    "date": "2026/02/22",
    "time": "14:30",
    "weather": "Sunny",
    "temp": "15°C",
    "humidity": "45%",
    "background": {"path": "/assets/bg.jpg"}
  }
}
```

**例: タスクモード**
```json
{
  "cmd": "set_mode",
  "mode": "tasks_short",
  "payload": {
    "tasks": [
      {"title": "資料作成", "status": "in_progress"},
      {"title": "会議", "status": "pending"},
      {"title": "レビュー", "status": "done"}
    ]
  }
}
```

タスクの `status` による色分け:
- `done` → 緑 (80, 200, 80)
- `in_progress` → 黄 (255, 220, 80)
- `pending` → グレー (220, 220, 220)

**例: フリーテキストモード**
```json
{
  "cmd": "set_mode",
  "mode": "free_text",
  "payload": {
    "text": "Pi says hello!\nLine 2"
  }
}
```

### refresh

現在のモードをキャッシュ済みペイロードで再描画する。

```json
{"cmd": "refresh"}
```

## レスポンス / イベント（Pico → ホスト）

### コマンド応答

```json
{"status": "ok", "mode": "status_datetime"}
```

```json
{"status": "error", "reason": "unknown_command"}
```

### タッチイベント

Pico はソケットタイムアウト（0.75秒）ごとにタッチパネルをポーリングし、ボタン押下を検知するとホストにイベントを送信する。

**モード切替リクエスト（MODE ボタン）:**
```json
{"cmd": "event", "event": {"type": "mode_request", "source": "touch_button"}}
```

**スクロール（UP / DOWN ボタン）:**
```json
{"cmd": "event", "event": {"type": "scroll", "dir": "up", "source": "touch_button"}}
```
```json
{"cmd": "event", "event": {"type": "scroll", "dir": "down", "source": "touch_button"}}
```

> 同一ボタンの連続タップはデバウンスされる（ボタンが離されるまで同じイベントは再送しない）。

## ボタン優先度

- タッチボタンはローカルイベントを発行し、Pico がスクロールやモード切替リクエストを処理できる
- **ホストからの `set_mode` コマンドは常に優先**。ボタン操作がホストコマンドと競合した場合、ホストのコマンドが勝つ
- スクロール操作はヒントとして扱われ、表示ウィンドウを変更した上でイベントとしてホストに報告する

## ペイロード共通仕様

### background（オプション）

全モードの `payload` に含めることができる背景画像指定。

**ファイルパス指定:**
```json
{"background": {"path": "/assets/bg.jpg"}}
```

**Base64 インライン指定:**
```json
{"background": {"data": "<base64エンコードされたJPEG>"}}
```

Base64 指定の場合、Pico は一時ファイル `/background.jpg` に書き出してから描画し、描画後に削除する。

## コマンド入力経路

ホスト側の `command_server.py` は3つの入力経路をサポートする。

### 1. インタラクティブモード（デフォルト）

```bash
python3 host/command_server.py
```

`command>` プロンプトから直接コマンドを入力:
- `mode <モード名> <JSONペイロード>` — モード切替
- `refresh` — 再描画
- 生 JSON — そのままブロードキャスト
- `exit` / `quit` — 終了

### 2. ヘッドレス + FIFO モード

```bash
python3 -u host/command_server.py --headless --fifo /tmp/pico-cmd-fifo
```

- `--headless`: `input()` を使わず、`running` フラグによるループで待機
- `--fifo`: 指定パスの名前付きパイプからコマンドを読み取るデーモンスレッドを起動
- FIFO が存在しない場合は自動作成
- FIFO 読み取りエラー時は 0.5 秒のバックオフ後にリトライ

### 3. プリロード

```bash
python3 host/command_server.py --preload commands.txt
```

最初のクライアント接続後（最大30秒待機）、ファイル内の JSON を1行ずつ送信。`#` で始まる行はコメントとしてスキップ。

### pico-ctl.sh ラッパースクリプト

Claude Code やシェルスクリプトからの操作には `pico-ctl.sh` を使用する。全操作がノンブロッキングで安全に実行される。

```bash
pico-ctl.sh start          # サーバ起動（冪等）
pico-ctl.sh stop           # サーバ停止
pico-ctl.sh restart        # サーバ再起動
pico-ctl.sh status         # 状態確認（サーバ/FIFO/Pico接続/USB）
pico-ctl.sh send '<json>'  # FIFO 経由でコマンド送信（3秒タイムアウト）
pico-ctl.sh send-file <f>  # ファイルから複数コマンド送信
pico-ctl.sh wait-pico [s]  # Pico 接続待ち（デフォルト30秒）
pico-ctl.sh logs [n]       # ログ末尾表示（デフォルト30行）
```

## エラーハンドリング

| 状況 | 動作 |
|---|---|
| 不正な JSON 受信（Pico側） | フレームを破棄し次の行を処理 |
| 不正な JSON 受信（ホスト側） | `"Unrecognized command"` を出力しスキップ |
| Pico からの接続断 | ホストがクライアントリストから除外、ログ出力 |
| ホストからの接続断 | Pico が 5 秒後に自動再接続 |
| Wi-Fi 切断 | Pico がソケットエラーをキャッチし、Wi-Fi 再接続 → TCP 再接続 |
| `sendall()` 失敗 | ホストが対象クライアントをリストから除外 |
