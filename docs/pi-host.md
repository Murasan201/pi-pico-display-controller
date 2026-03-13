# Raspberry Pi 5 ホスト側: コマンドサーバ

Raspberry Pi 5 は Pico 2 W に表示指示を送る TCP サーバとして動作する。`host/command_server.py` を使い、Pico が Wi-Fi 経由で接続している間、JSON コマンドで表示モード切替・背景更新・リフレッシュを行う。

## サーバ起動方法

### ヘッドレスモード（推奨・本番運用）

```bash
python3 -u host/command_server.py --headless --fifo /tmp/pico-cmd-fifo
```

- `--headless`: 対話プロンプトなしで待機。`input()` によるブロッキングが発生しない
- `--fifo`: 名前付きパイプ（FIFO）からコマンドを受け付けるデーモンスレッドを起動
- `-u`: Python の出力バッファリングを無効化（ログのリアルタイム確認用）

### pico-ctl.sh（Claude Code / シェルからの操作）

### systemd 自動復旧（Pi 再起動時）

Pi 再起動後もコマンドサーバを自動復旧させるには、systemd サービスをインストールする。

```bash
cd /home/pi/.openclaw/workspace/project/pi-pico-display-controller
scripts/install-systemd-service.sh
```

確認コマンド:

```bash
systemctl status pico-command-server.service --no-pager
journalctl -u pico-command-server.service -n 50 --no-pager
scripts/pico-ctl.sh status
```

全操作がノンブロッキングで設計されており、Claude Code から安全に呼び出せる。

```bash
scripts/pico-ctl.sh start          # サーバ起動（冪等・既に起動中なら何もしない）
scripts/pico-ctl.sh stop           # サーバ停止
scripts/pico-ctl.sh restart        # サーバ再起動
scripts/pico-ctl.sh status         # 状態確認（サーバ/FIFO/Pico接続/USB）
scripts/pico-ctl.sh send '<json>'  # FIFO 経由でコマンド送信（3秒タイムアウト）
scripts/pico-ctl.sh send-file <f>  # ファイルから複数コマンド送信
scripts/pico-ctl.sh wait-pico [s]  # Pico 接続待ち（デフォルト30秒）
scripts/pico-ctl.sh logs [n]       # ログ末尾表示（デフォルト30行）
```

### インタラクティブモード（開発・デバッグ用）

```bash
python3 host/command_server.py
```

`command>` プロンプトが表示され、直接コマンドを入力できる:
- `mode status_datetime {"date":"2026/02/22","time":"14:30","weather":"Cloudy","temp":"12°C"}`
- `mode tasks_short {"tasks":[{"title":"資料作成","status":"in_progress"}]}`
- `mode free_text {"text":"Hello!"}`
- `refresh`
- 生 JSON: `{"cmd":"set_mode","mode":"status_datetime","payload":{...}}`
- `exit` / `quit`

### プリロードモード

```bash
python3 host/command_server.py --preload initial_commands.txt
```

最初のクライアント接続後（最大30秒待機）、ファイル内の JSON を1行ずつ送信。`#` 行はスキップ。`--headless` や `--fifo` と組み合わせ可能。

## 設定

Pico 側の接続先は `src/config.py` で定義する:

```python
TCP_SERVER_HOST = "192.168.11.22"  # Pi 5 の固定IP（例）
TCP_SERVER_PORT = 5000
```

> Pi 側は DHCP 予約などで **固定 IP** にしておくことを推奨。固定化したら Pico 側 `config.py` も同じ値にそろえる。
> IP アドレスは環境ごとに異なるため、デプロイ先に合わせて必ず書き換えること（`src/secrets.py` は Git 除外済み）。

## ファイル構成

```
host/
└── command_server.py   # TCP コマンドサーバ（ヘッドレス/FIFO/対話モード対応）

scripts/
└── pico-ctl.sh         # ノンブロッキングラッパースクリプト

/tmp/
├── pico-cmd-fifo       # 名前付きパイプ（FIFO）
├── pico-server.log     # サーバログ
└── pico-server.pid     # PIDファイル
```

## FIFO 経由のコマンド送信

FIFO への書き込みは必ず `timeout` でラップすること。読み取り側がいない場合、書き込みは永遠にブロックする。

```bash
# 正しい方法
timeout 3 bash -c "printf '%s\n' '{\"cmd\":\"refresh\"}' > /tmp/pico-cmd-fifo"

# pico-ctl.sh を使う方法（推奨）
scripts/pico-ctl.sh send '{"cmd":"refresh"}'
```

## ログの活用

ヘッドレスモードでは全ログが `/tmp/pico-server.log` に出力される:

```bash
# 最新ログを確認
scripts/pico-ctl.sh logs 30

# Pico 接続・切断の確認
grep -E "connected|disconnected" /tmp/pico-server.log

# FIFO 経由のコマンド確認
grep "\[fifo\]" /tmp/pico-server.log
```

## トラブルシューティング

### Pico が接続されない / 画面表示が止まる

1. サーバ状態確認
   ```bash
   scripts/pico-ctl.sh status
   scripts/pico-ctl.sh logs 50
   ```
2. Pico 側 `config.py` の `TCP_SERVER_HOST` が Pi 固定IPと一致するか確認
   ```bash
   mpremote connect /dev/ttyACM1 fs cat config.py
   ```
3. Pico 画面に `Pico connection error` が表示されている場合
   - `host: <IP>:5000`
   - `reason: ...`
   - `retry: N`
   が出るため、IP不一致・Wi-Fi未接続を切り分け可能。
4. USBで一時接続して設定更新後に再起動

### BOOTSEL / FS mode になっている場合

`dmesg` に `Product: Board in FS mode` が出る場合、通常実行ではない。
BOOTSEL を離してリセットするか、USB 抜き差し後に通常起動へ戻す。

## 画像アセット

1. Pico の `assets/` に背景 JPEG を配置:
   ```bash
   mpremote connect /dev/ttyACM0 fs mkdir assets
   mpremote connect /dev/ttyACM0 fs cp background.jpg :/assets/background.jpg
   ```
2. JSON ペイロードで背景を指定:
   - ファイルパス: `"background": {"path": "/assets/bg.jpg"}`
   - Base64 インライン: `"background": {"data": "<base64>"}`
