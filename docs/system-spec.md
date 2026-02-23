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

## ディスプレイ/タッチ UI
- 画面は縦表示（ポートレート）とし、320×240 の長辺を上下とします。UI は上部にボタンエリアを設け、左から「モード切替」「上スクロール」「下スクロール」のボタン（実体ボタンではなくタッチで描画した疑似ボタン）を置きます。これらにより Pico 単体でもモード切替やリストスクロールが可能です。
- モード切替は Raspberry Pi 5 からの `set_mode` 要求を最優先とし、ホストからの指示がある場合はタッチからの切替を抑止してホスト指定モードに従います。
- スクロールボタンは短期タスクリストモード等で上下移動を通知するため、タッチイベントとして Pico がローカルで処理し、必要に応じて Pi へ `event: {"type":"scroll","dir":"up"}` などで状況通知も行えるように設計します。

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
   - Pi 5：表示指示を生成し、ソケットを通じて Pico へ送信。ログ保存・監視・必要時のコマンド再送を担当。`host/command_server.py` によりコマンドサーバ＋ CLI を実装し、連携したドキュメントを `docs/pi-host.md` にまとめている。
   - Pico：受信データを解析して `display_manager` を呼び出し、画面再描画を実行。タッチイベントやステータスは Pico が独自に Pi へ通知可能。
   - 通信フォーマットやレスポンス期待値、再送タイミングについては新設した `docs/communication-spec.md` を参照してください。

## 設定値の管理
- `src/config.py` に Pico が接続する Raspberry Pi 5 のホスト名/IP を設定します（例：`raspberrypi.local` や `192.168.1.42`）。本番環境で使う実際のアドレスはこのファイルか起動スクリプト内で上書きしてください。
- Wi-Fi SSID/PASSWORD は `src/secrets.py` に記述しますが、このファイルは `.gitignore` に追加し、GitHub へのアップロード対象から外すことで IP/認証情報の漏洩を防ぎます。
- 複数環境で運用する場合は `config.py`/`secrets.py` をテンプレート化し、各端末でコピーしてから実際の値を記入する運用が安全です。
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

## 時刻同期と自律更新

### NTP 同期
- Pico 2 W は Wi-Fi 接続済みのため、MicroPython 標準ライブラリ `ntptime` で NTP 時刻同期を行う。
- 同期タイミング: Wi-Fi 接続確立直後（起動時）+ 24 時間ごとに再同期。
- 起動時の NTP 同期は最大 3 回リトライする（各試行間 2 秒待機）。Wi-Fi 接続直後は DNS が未準備の場合があり、1 回目で失敗しても 2〜3 回目で成功することが確認されている。
- 起動時に全リトライ失敗した場合、`last_ntp_sync = 0` とし、メインループの次の反復（`NTP_SYNC_INTERVAL` 経過判定が即座に真になる）で再試行する。
- JST (UTC+9) オフセットを適用し、`utime.localtime(utime.time() + JST_OFFSET)` でローカル時刻を取得する。
- NTP 同期失敗時はログ出力のみで動作を継続する（時刻は不正確になるが描画は止めない）。

### status_datetime モードの自律更新
- `status_datetime` モード時、Pico 側で 60 秒間隔の自動リフレッシュを行い、画面の日時表示を更新する。
- 日時（date / time）は常に Pico のローカル時刻（`utime.localtime()`）から生成する。ホストからのペイロードに含まれる date / time は無視する。
- 天気・温度・湿度はホストからの `set_mode` コマンドで更新し、Pico 側で `current_payload` にキャッシュする。
- `set_mode` で `status_datetime` モードが再送された場合、新しいペイロードは既存の `current_payload` にマージされる。これにより天気だけ更新しても他のデータが保持される。
- 他のモード（`tasks_short`, `free_text`）では自動リフレッシュは行わない。

## microSD カードと背景画像

### microSD マウント
- Pico-ResTouch-LCD-2.8 基板上の microSD カードスロットは、回路基板上の SDIO ラベル（GP5, GP18-22）とは異なり、実際には **SPI1 バス（GP10/GP11/GP12）を LCD・タッチと共有** している。
- CS ピンのみ SD 固有: **GP22**。LCD CS (GP9)、TP CS (GP16) と CS ピンで切り替えてバスを共有する。
- MicroPython の `sdcard` モジュール（SPI プロトコル）で接続する。
- SD 初期化手順:
  1. LCD CS (GP9) と TP CS (GP16) を HIGH に設定してバス競合を防止
  2. SPI1 を 400kHz, Mode 0 で初期化し `sdcard.SDCard` を作成
  3. 1MHz でウォームアップ読み取り（カードのデータ転送エンジンを起動、失敗しても続行）
  4. SPI1 を 20MHz に切り替えてマウント
- DisplayManager の SPI1 baudrate は SD カードとの共有のため 20MHz に設定（SD SPI モード上限 25MHz 以内）。
- FAT32 フォーマットの microSD を `/sd/` にマウントする。
- マウント失敗（SD カード未挿入・破損等）時はログ出力のみで動作を継続する（背景なし＝黒背景）。

### 背景画像ランダム選択
- 画像ファイル規約:
  - 格納先: microSD ルート直下
  - ファイル名: `background_001.jpg`, `background_002.jpg`, ... （`background_` + 3桁連番 + `.jpg`）
  - 解像度: 240×320（ディスプレイ解像度と同一）推奨
  - フォーマット: JPEG（st7789 の `panel.jpg()` が直接デコード可能）
- 起動時に `/sd/` 内の `background_*.jpg` ファイルをスキャンしてリスト化する。
- モード切替時（`set_mode` でモードが変わるとき）にリストからランダムに 1 枚選択し、背景として適用する。
- 同一モードの再送（`status_datetime` のペイロードマージ等）では背景を変更しない。
- `refresh()`（自動リフレッシュ）では背景を変更しない（現在の背景を維持）。
- SD カード未挿入・背景リストが空の場合は、従来通りペイロードの `background` フィールドで指定された画像を使用する。

### microSD カードの使用方法

#### 初回セットアップ（フォーマット）
新品の microSD カードは Pico 上で FAT フォーマットする必要がある:
```python
import sdcard, os
from machine import Pin, SPI
Pin(9, Pin.OUT, value=1); Pin(16, Pin.OUT, value=1)
spi = SPI(1, baudrate=400_000, polarity=0, phase=0, sck=Pin(10), mosi=Pin(11), miso=Pin(12))
sd = sdcard.SDCard(spi, Pin(22, Pin.OUT, value=1))
os.VfsFat.mkfs(sd)
```
または PC 上で FAT32 フォーマットしても可。

#### 背景画像の転送手順
1. Pi 5 上で 240×320 の JPEG 画像を用意する（リサイズが必要な場合は PIL 等で実施）
2. `mpremote fs cp` で Pico 内蔵フラッシュに一時転送:
   ```bash
   mpremote connect /dev/ttyACM0 fs cp background_001.jpg :/background_001.jpg
   ```
3. `mpremote exec` で SD カードをマウントし、フラッシュから SD にコピー:
   ```python
   # SD マウント → コピー → フラッシュから削除
   with open('/background_001.jpg', 'rb') as src:
       data = src.read()
   with open('/sd/background_001.jpg', 'wb') as dst:
       dst.write(data)
   os.remove('/background_001.jpg')
   ```
4. Pico をリセットすると起動時に自動スキャンされる

#### 注意事項
- **SPI バス共有**: SD カードは LCD・タッチと SPI1 を共有しているため、`mpremote fs cp` で直接 `/sd/` に書き込むことはできない。必ずフラッシュ経由で転送する。
- **カード容量**: 8GB / 16GB の FAT32 カードを推奨。
- **ホットスワップ非対応**: SD カードの挿抜は電源オフ状態で行う。

### 描画更新の最適化

画面更新は 3 段階のレベルで行い、不要な再描画を最小化する:

| 更新レベル | トリガー | 処理内容 |
|-----------|---------|---------|
| 全体再描画 | モード切替（`set_mode` で異なるモードへ） | 背景 JPEG + ボタン + 全テキスト |
| コンテンツ再描画 | 同一モード再送（天気更新等） | テキスト領域のみクリア + 全テキスト（背景・ボタン維持） |
| 時刻のみ更新 | 自動リフレッシュ（60 秒間隔） | 日時テキスト領域のみクリア + 日時テキスト |

- 全体再描画時も `fill(0)` による黒画面フラッシュを回避: 背景 JPEG がある場合は JPEG を先に描画し、その上にテキストを重ねる。
- 自動リフレッシュでは SD カードからの JPEG 読み取りが発生しないため、高速に更新される。

## その他
- **電源**：USB 給電のみで十分。Pico 自身が 5V レギュレータ（RT9193-33）を搭載しているので、Pi 側の USB 1 ポートから供給可能。追加の AC アダプタ不要。
- **拡張**：将来的にタッチイベントやセンサ値を Pi へ送る際は、ソケットメッセージに `event` フィールドを追加し、Pi 側でハンドリングします。
- **実行手順やキャリブレーション**：`docs/setup-guide.md` に CLI ベースの展開手順、タッチボタンのチェックフロー、調整方法（XPT2046 のスケーリング/オフセット）をまとめています。

このドキュメントは `docs/` 以下で管理し、各機能追加時に更新してください。必要であればブロック図、シーケンス図などを追加します。
