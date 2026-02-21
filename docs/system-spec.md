# システム仕様書

## 目的
Raspberry Pi 5（ホスト）および Raspberry Pi Pico 2 W を中心に、WAVESHARE-19804（WaveShare Pico-ResTouch-LCD-2.8）を用いた表示コントローラアプリケーションの構成と通信フローを定義します。表示処理は Pico 側で実行し、Pi 5 から送信される指示で表示内容を更新します。

## ハードウェア構成
- **Raspberry Pi 5（ホスト）**
  - 電源とネットワーク（有線/Wi-Fi）をもとに、Pico との命令送信・監視・ログ記録を行う中心装置。
  - USB ポートを使って Pico へ 5V 給電を行い、追加のコンセント接続は不要とする。

- **Raspberry Pi Pico 2 W（コントローラ）**
  - Pico-ResTouch-LCD-2.8 を直接 SPI 接続し、MicroPython で描画・タッチ・MicroSD を制御。
  - USB は給電のみで使用し、通信は Wi-Fi を介して Raspberry Pi 5 とソケット接続する構成。

- **WAVESHARE-19804（Pico-ResTouch-LCD-2.8）**
  - 2.8" IPS、320×240、ST7789 ドライバ＋XPT2046 タッチ。
  - 接続には SPI/MicroSD/バックライト制御ピンを使用し、詳細は `docs/pico-restouch-lcd-2.8.md` に記載。

## ネットワーク/通信構成
1. **Wi-Fi アクセス**
   - Pico 2 W は MicroPython の `network` モジュールで指定アクセスポイントに接続し、IP を取得する。
   - Raspberry Pi 5 は同一ネットワーク上にサーバ（TCP 推奨）を立て、Pico からのソケット接続を待機する。

2. **ソケット通信プロトコル（例）**
   - 送信フォーマット：JSON 文字列（UTF-8）で、`cmd`、`payload` を含む。
     ```json
     { "cmd": "display", "payload": { "type": "text", "value": "Hello" } }
     ```
   - Pico からのレスポンス（任意）：`{ "status": "ok", "touch": { ... } }` のように ACK やタッチ情報を返す。
   - 通信は TCP ソケット（デフォルトポート 5000 など）とし、再接続処理を Pico で実装する。

3. **通信の役割分担**
   - Pi 5：表示指示を生成し、ソケットを通じて Pico へ送信。ログ保存・監視・必要時のコマンド再送を担当。
   - Pico：受信データを解析して `display_manager` を呼び出し、画面再描画を実行。タッチイベントやステータスは Pico が独自に Pi へ通知可能。

## ソフトウェア構成（Pico 側）
- **`main.py`（MicroPython）**
  - Wi-Fi 接続、ソケットクライアント、データ受信ループを実装。
  - `display_manager.py` 等で ST7789 + タッチの抽象化を提供し、`draw_text`／`draw_image` などを呼び出す。
  - 受信コマンドは `cmd` で振り分け (`display/text`、`display/image`、`system/reset`など)。

- **描画 API / データ構成**
  - 画面は複数レイヤ（背景・テキスト・バッジ）で構成し、JSON で位置/色/フォントを指定できる。
  - 画像再描画時には MicroSD 内のビットマップを参照する機構を用意。

- **状態管理**
  - タッチ入力やバックライト調整などイベントは Pico 内部で処理し、必要に応じて Pi へ戻る。

## ソフトウェア構成（Raspberry Pi 5 側）
- **通信クライアント/サーバ（Python）**
  - TCP サーバを立て、Pico からの接続を待機。JSON コマンドを `json.loads` で解釈。
  - 表示内容の変更要求は CLI や REST/API から呼び出せるよう簡易 CLI、または cron/スケジューラ連携を想定。

- **表示指示の生成**
  - スクリプトで `display/text`／`display/status` などの JSON コマンドを組み立て。
  - ローカルリソース（画像・テーマ）を Pico へ転送するときは、MicroSD に先に配置→Pico にパスを送る形を検討。

## ワークフロー
1. Pico を Raspberry Pi 5 の USB で給電し、Pico が MicroPython `main.py` を起動。
2. Wi-Fi 接続が確立後、Pi 5 側の TCP サーバとセッションを確立。
3. Pi 5 から表示コマンドを送信／Pico が描画。
4. Pico はタッチや状態変化を Pi へ返送し、Pi 側でログ・フロー制御を行う。
5. 必要なコード変更やリソース更新後は、Pi 側で再ビルドした MicroPython ファイルを Pico に書き込む（CLI ベース）。

## MicroPython ビルド + 書き込み（CLI）
1. **環境整備**
   - `mpremote`、`picotool`、`mpy-cross` などを Raspberry Pi 5 上にインストール（`sudo apt install mpremote picotool python3-pip` + `pip3 install mpy-cross` など）。
2. **ビルド／構成**
   - `main.py` や依存モジュールを `src/` に置いたら `mpy-cross` で `.mpy` を生成し、`build/` へコピーすることで起動時間を短縮。
   - 背景画像・アイコンなどのアセットは `assets/` 配下で整理し、`mpremote fs cp` で Pico 側に転送。
3. **書き込み**
   - BOOTSEL モードで Pico を接続したら、CLI で UF2 をロード：
     ```bash
     picotool load build/main.uf2
     ```
   - MicroPython が既に稼働しているときは、以下のように直接ファイルをコピー：
     ```bash
     mpremote connect usb0 fs cp src/main.py :/main.py
     mpremote connect usb0 fs mkdir -p assets
     mpremote connect usb0 fs cp assets/* :/assets/
     mpremote connect usb0 run main.py
     ```
   - 接続先の USB デバイス名（`usb0` や `/dev/ttyACM0`）は `mpremote list` で確認し、必要に応じて指定し直す。
4. **デプロイスクリプト例**
   - `scripts/deploy.sh` などを作って `git pull` → `./scripts/deploy.sh` で書き込み・再起動まで自動化するとミスが減る。

## その他
- **電源**：USB 給電のみで十分。Pico 自身が 5V レギュレータ（RT9193-33）を搭載しているので、Pi 側の USB 1 ポートから供給可能。追加の AC アダプタ不要。
- **拡張**：将来的にタッチイベントやセンサ値を Pi へ送る際は、ソケットメッセージに `event` フィールドを追加し、Pi 側でハンドリングします。

このドキュメントは `docs/` 以下で管理し、各機能追加時に更新してください。必要であればブロック図、シーケンス図などを追加します。
