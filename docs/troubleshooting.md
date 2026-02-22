# トラブルシューティング

Picoデプロイプロセスで発生した問題と解決策の記録。

---

## 1. main.py SyntaxError (line 15)

**症状**

Pico上で main.py をインポートした際に、15行目で `SyntaxError: invalid syntax` が発生。

**原因**

`send_event` 関数内の `"\n"` がリテラル改行文字として保存されていた。これにより、本来1行であるべき文字列リテラルが2行に分割され、構文エラーとなっていた。

**解決策**

`sock.send((json.dumps(event) + "\n").encode())` を1行で正しく記述し、mpremote で Pico に再転送した。

---

## 2. TCP接続タイムアウト (ETIMEDOUT)

**症状**

Pico からホスト（ポート5000）への TCP 接続が `[Errno 110] ETIMEDOUT` で失敗。

**原因**

ホスト側の UFW ファイアウォールがポート5000をブロックしていた。SSH（ポート22）のみ許可する設定になっていた。

**解決策**

UFW でローカルネットワークからのポート5000へのアクセスを許可した。

```bash
sudo ufw allow from xxx.xxx.xxx.0/24 to any port 5000 proto tcp comment "Pico display controller"
```

**補足**: ファイアウォールルールはローカルネットワーク内に限定し、外部からのアクセスは許可しないこと。

---

## 3. コマンドサーバー即時終了 (--headless)

**症状**

`command_server.py --headless` で起動するとサーバーがすぐに終了し、Pico が接続できない状態になった。

**原因**

`--headless` モードでは `--preload` オプションなしの場合、`interactive_loop` をスキップして即座に `server.stop()` が呼ばれる設計になっていた。サーバーが待機状態を維持できなかった。

**解決策**

`--headless` を使わずに起動する。バックグラウンドで実行する必要がある場合は、stdin を維持するために以下のように実行する。

```bash
tail -f /dev/null | python command_server.py
```

---

## 4. st7789モジュール未インストール

**症状**

main.py 実行時に `no module named 'st7789'` エラーが発生。

**原因**

MicroPython v1.27.0 のデフォルトインストールには ST7789 ドライバが含まれていない。WaveShare Pico-ResTouch-LCD-2.8 の ST7789 ディスプレイコントローラー用ライブラリを別途インストールする必要がある。

**解決策**

標準の `mpremote mip install` では対応不可。以下の方法を試行した結果、カスタムファームウェアビルドが必要だった。

| 試行方法 | 結果 |
|----------|------|
| `mpremote mip install st7789` | 失敗（公式パッケージインデックスに存在しない） |
| `mpremote mip install "github:russhughes/st7789_mpy"` | 失敗（package.json未対応） |
| `mpremote mip install "github:devbis/st7789py_mpy"` | 失敗（同上） |
| devbis/st7789py_mpy（純Python版） | APIが異なる（`st7789py`モジュール） |
| Pimoroni firmware | `picographics` APIで`st7789`ではない |
| **カスタムMicroPythonビルド** | **成功** |

最終的な解決手順:

```bash
# 必要なツール
sudo apt-get install cmake gcc-arm-none-eabi libnewlib-arm-none-eabi build-essential

# MicroPython v1.27.0 ソースクローン
git clone --depth 1 --branch v1.27.0 https://github.com/micropython/micropython.git
cd micropython
git submodule update --init --depth 1 lib/pico-sdk lib/tinyusb lib/mbedtls lib/micropython-lib
cd lib/pico-sdk && git submodule update --init --depth 1 && cd ../..

# mpy-cross ビルド
make -C mpy-cross -j4

# st7789_mpy クローン
git clone --depth 1 https://github.com/russhughes/st7789_mpy.git /path/to/st7789_mpy

# ファームウェアビルド（Wi-Fiサブモジュール含む）
cd ports/rp2
make BOARD=RPI_PICO2_W submodules
make BOARD=RPI_PICO2_W USER_C_MODULES=/path/to/st7789_mpy/st7789/micropython.cmake -j4

# フラッシュ（BOOTSELモード）
cp build-RPI_PICO2_W/firmware.uf2 /media/pi/RP2350/
```

**補足**:
- `jpegdec` モジュールは Pimoroni 固有で組み込み困難だが、st7789 モジュールに `panel.jpg()` メソッドが内蔵されており代替可能
- フォントファイル（`vga1_8x16.py` 等）を Pico の `/lib/` にアップロードする必要がある
- russhughes st7789 の API は既存の `display_manager.py` と差異があり、コード修正が必要（SPI バス番号、フォント指定方法、text() メソッドのシグネチャ等）

---

## 5. secrets.pyがgitで追跡されていた

**症状**

Wi-Fi 認証情報（SSID・パスワード）を含む `secrets.py` が `.gitignore` に記載されているにもかかわらず、git の変更追跡対象になっていた。

**原因**

`secrets.py` がプレースホルダー内容で先にコミットされていたため、後から `.gitignore` に追加しても追跡が自動的に解除されなかった。git は一度追跡を開始したファイルを `.gitignore` だけでは除外しない。

**解決策**

`git rm --cached` でインデックスから削除し、追跡を解除した。ファイル自体はローカルに残る。

```bash
git rm --cached src/secrets.py
```

**補足**: `secrets.py` には Wi-Fi の SSID やパスワードなどの機密情報が含まれるため、リポジトリに絶対にコミットしないこと。テンプレートファイル（例: `secrets_example.py`）を用意し、実際の値はユーザーが手動で設定する運用とすること。

---

## 6. ClaudeCode実行中にソケット通信が固まって見える

**症状**

- ClaudeCode 側のターミナルが応答しないように見える（`esc to interrupt` 表示のまま進まない）。
- `command_server.py` は稼働しているが、Pico へのコマンド反映が止まる。
- `ss -tnp` で `FIN-WAIT-1` が残る、または Pico の再接続が来ないことがある。

**原因**

- サーバー側の `accept()` / `recv()` が無期限待機になる条件があり、切断・再接続の遷移中に処理が進んでいないように見える。
- FIFO への書き込みを `timeout` なしで行うと、読み手状態によっては呼び出し側が待ち続ける可能性がある。
- Pico 側が切断後に再接続できていない場合、ホスト側の送信だけ成功して応答が返らない。

**恒久対策（コード修正）**

`host/command_server.py` に以下を追加:

- サーバーソケットに `settimeout(1.0)` を設定し、`accept()` の待機を短周期で抜ける。
- クライアントソケットに `settimeout(2.0)` を設定し、`recv()` の無期限ブロックを防ぐ。
- `socket.timeout` は継続処理、`ConnectionResetError` / `BrokenPipeError` / `OSError` は切断として処理。

これにより、通信断や再接続時にサーバーが停止したように見える状態を軽減できる。

**運用対策**

- FIFO 書き込みは必ず `timeout` 付きで実行する。

```bash
timeout 3 bash -c 'printf "%s\n" "{\"cmd\":\"set_mode\",\"mode\":\"free_text\",\"payload\":{\"text\":\"hello\"}}" > /tmp/pico-cmd-fifo'
```

- 長い `sleep` を避け、2秒程度の短い間隔で接続状態を確認する。
- 送信後は `/tmp/pico-server.log` に `[pico ...] {"status":"ok"}` が出ることを確認する。

**復旧手順**

1. サーバーが `LISTEN :5000` か確認する。
2. Pico を再起動（USB 抜き差しまたは `mpremote connect /dev/ttyACM0 reset`）。
3. `ss -tnp | rg ":5000|ESTAB"` で Pico セッションの再確立を確認する。
4. `timeout 3` 付きで FIFO コマンドを再送する。
