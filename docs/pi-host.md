# Raspberry Pi 5 ホスト側: コマンド送信

Raspberry Pi 5 は MicroPython を実行する Pico 2 W に表示指示を送る TCP サーバ兼 CLI として動作します。`host/command_server.py` を使うことで、Pico が接続している間、JSON コマンドを送って表示モードを切り替えたり、背景 JPEG を更新したり、手動でリフレッシュを要求できます。

## サーバの起動
```bash
python3 host/command_server.py --bind 0.0.0.0 --port 5000
```
- Pico の `src/main.py` が `TCP_SERVER_HOST`/`PORT` に合わせてこのポートに接続すると、受信したコマンドを処理します。
- `src/config.py` の `TCP_SERVER_HOST` を実際の Raspberry Pi 5 の IP または mDNS 名（例：`raspberrypi.local`）に書き換えてからデバイスにデプロイしてください。IP は環境ごとに異なるため Git には含めず、各自で上書きする運用とします。- 接続中は Pico からのレスポンスが標準出力に出てくるので、正常性確認とログに使えます。

## 代表的なコマンド
- `mode status_datetime {"date":"2026/02/22","time":"00:15","weather":"Cloudy","temp":"12°C"}`
  - 日時/天気表示モードを指定データで更新します。
- `mode tasks_short {"tasks":[{"title":"資料作成","status":"in_progress"},{"title":"会議","status":"pending"}]}`
  - 短期タスク表示を切り替えます。最大 4 件まで描画され、ステータスで色分けされます。
- `refresh`
  - 現在のモードを再描画させ、背景やローカルデータを再読込させたいときに使います。
- 生 JSON を直接貼り付けることもできます。例：
  ```json
  {"cmd":"set_mode","mode":"status_datetime","payload":{"weather":"Rain","temp":"9°C"}}
  ```

## 画像やアセットの準備
1. Pico 側の `assets/` に背景 JPEG やアイコンを配置する例：
   ```bash
   mpremote connect usb0 fs mkdir -p assets
   mpremote connect usb0 fs cp assets/background.jpg :/assets/background.jpg
   ```
2. JSON で背景を指定するには `payload` に `background: {"path": "/assets/background.jpg"}` を含めます。
3. 直接 Pi から JPEG を送る場合、Base64 エンコードして `background` に `data` キーをセットすれば `DisplayManager` が受信して描画します（転送前に `base64` コマンドでファイルを変換）。

## 非対話モード
- `--preload commands.txt` を使うと、起動直後にファイル内の JSON（1 行 1 コマンド）を順番に送信できます。
- `--headless` と組み合わせると、PIO が接続するとすぐファイルを送ったのちにプロセスを終了させられます。

## ディレクトリ構成
```
host/
└── command_server.py  # TCP コマンドサーバ
```

## 起動例
```bash
python3 host/command_server.py --preload initial_commands.txt
```
- `initial_commands.txt` には、起動時に表示しておきたいモード変更コマンドを記述しておくと自動化できます。
- `initial_commands.txt` は JSON 一行ずつ（コメント行は `#` で始める）。

## ログの活用
- Pico から返ってくる ACK やエラー（JSON 形式）も標準出力に表示されるので、追加のログファイルにリダイレクトするとトレーサビリティが確保できます。

このホストスクリプトを `systemd` サービス化したり、`cron`/`tmux` で常時起動させておけば、Pi 5 から Pico への表示操作が安定して行えます。必要であれば `docs/system-spec.md` にサーバ起動方法やポート番号を補完してください。