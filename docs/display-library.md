# 表示関数ライブラリ設計

Raspberry Pi Pico 側では `DisplayManager` を中心とした関数ライブラリを持ち、Raspberry Pi 5 から送られてくる JSON コマンドを受けてモードを切り替え／描画を実行します。通信やデータ取得も含めて再利用しやすい構成を以下に示します。

## モジュール構成例
```python
# display_manager.py
class DisplayManager:
    def __init__(self, panel, touch, wifi):
        self.panel = panel
        self.touch = touch
        self.mode = None

    def set_mode(self, mode, payload):
        handler = {
            "status_datetime": self._draw_status,
            "tasks_short": self._draw_tasks
        }.get(mode)
        if handler:
            self.mode = mode
            handler(payload)
            return {"status": "ok", "mode": mode}
        return {"status": "error", "reason": "unknown_mode"}

    def _draw_status(self, payload):
        data = prepare_status_data(payload)
        self.panel.fill(0)
        self.panel.text(data["date"], 10, 4)
        self.panel.text(data["time"], 10, 26)
        draw_weather_block(self.panel, data)
        self.panel.show()

    def _draw_tasks(self, payload):
        tasks = normalize_tasks(payload)
        self.panel.fill(0)
        draw_task_list(self.panel, tasks)
        self.panel.show()
```

## データ取得／整形の関数
- `prepare_status_data(payload)`
  - `payload` に含まれる `date`/`time`/`weather`/`temp` を検証して、フォントサイズ・カラーの規定値を補完。
  - `weather` は Pi が提供する文字列（例：`"Cloudy"`）で、アイコン描画用のマッピング（`icon_map[weather]`）もここで決定。
  - 必要あれば `utime.localtime()` から補助の日時を取得し、`date`/`time` が未提供でも表示できるようにする。

- `normalize_tasks(payload)`
  - `payload["tasks"]`（配列）を受け、`title`/`status`/`due` を検証。
  - ステータス（`pending`/`in_progress`/`done`）に応じてカラーを返す。
  - 最大 4 件にトリムし、無ければ `空白行` を挿入する。

- `draw_weather_block(panel, data)` / `draw_task_list(panel, tasks)`
  - ST7789 用に座標とサイズを固定し、アイコンビットマップ・バー・テキストを描画する共通関数。

## 背景画像 (JPEG) のサポート
- `set_background_image(panel, payload)`
  - `payload["background"]` に `type: "jpeg"` を含む辞書を渡すと、JPEG ファイルやバイナリをデコードして背景に敷く。
  - 通常は MicroSD 上の `images/` などに JPEG を置き、Pi からは `"source": "images/scene.jpg"` のようなパスを送るだけで済む。
  - 直接転送したい場合は Base64 文字列 (`payload["background"]["data"]`) を Pico が受信して一時ファイルに書き出し、`jpgdec` や `picdecoder` など MicroPython 互換の JPEG デコーダで描画する。ただしサイズによってメモリを圧迫するため、事前に Pi 側でリサイズしておく。
  - 背景は `panel.blit()` で描画すると、後から描画するテキスト／タスクの読みやすさを考慮して、オーバーレイ用の半透明レイヤやダークフィルタを配置できる。

## 通信／データ要求のヘルパー
- `listen_for_commands()`
  - Wi-Fi ソケットを扱うメインループ。接続が切れた場合は再接続を試みる。
  - 受信した JSON を `json.loads` し、`cmd` で振り分け。

- `handle_command(cmd)`
  - `cmd` が `set_mode` なら `DisplayManager.set_mode(mode, payload)` を呼ぶ。
  - `cmd` が `refresh` なら現在のモードを再描画。
  - `cmd` が `request_status` なら `payload` を埋めた上で即座に `status_datetime` 用の描画を実行。

- `collect_local_status()`
  - Pico 内部から取得可能なデータ（Wi-Fi 信号強度、内部温度センサなど）をまとめて `self.panel` に補足表示するための関数。

## Pi 5 側（送信するデータ）
- `status_datetime` モードのペイロード例：
  ```json
  {
    "cmd": "set_mode",
    "mode": "status_datetime",
    "payload": {
      "date": "2026-02-21",
      "time": "23:58",
      "weather": "Rain",
      "temp": "12°C",
      "humidity": "73%"
    }
  }
  ```
- `tasks_short` モードのペイロード例：
  ```json
  {
    "cmd": "set_mode",
    "mode": "tasks_short",
    "payload": {
      "tasks": [
        {"title": "ミーティング", "status": "in_progress"},
        {"title": "資料整理", "status": "pending"}
      ]
    }
  }
  ```

## 実装のヒント
- モード切替は `DisplayManager.set_mode` で行い、各 `_draw_*` が `payload` のデータ構造を完全に把握する。
- データ取得関数は Pico 内部で補完しても良いが、主に Pi 5 から提供される想定でサーバ側を中心に設計。
- 画面切替時のエフェクト（フェードやクリア）も `DisplayManager` の責務として扱うと整合性が保ちやすい。

このライブラリ構造をベースに実装し、必要に応じて `display_manager.py`、`mode_status.py`、`mode_tasks.py` などに分割してください。