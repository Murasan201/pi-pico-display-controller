# Pico-ResTouch-LCD-2.8 (Waveshare)

Raspberry Pi Pico 専用に設計された WaveShare の `Pico-ResTouch-LCD-2.8` は、Pico 直結で高精細なタッチ表示を提供する 2.8 インチ IPS ディスプレイモジュールです。Raspberry Pi Pico 2 W と組み合わせて、本プロジェクトで採用している `WAVESHARE-19804`（Pico-ResTouch-LCD-2.8 の製品番号）として利用します。

## 公式情報（参照）
- 公式ページ: https://www.waveshare.com/pico-restouch-lcd-2.8.htm
- 公式 Wiki: https://www.waveshare.com/wiki/Pico-ResTouch-LCD-2.8

両ページとも、製品仕様・機能・接続例・デモコードなどを提供しており、開発やトラブルシュートの一次情報源として活用してください。

## 主なスペック
| 項目 | 内容 |
| --- | --- |
| 表示パネル | 2.8 インチ IPS、320×240 ピクセル、262K 色 |
| ドライバ | ST7789 |
| タッチコントローラ | XPT2046（抵抗膜式） |
| 通信インタフェース | SPI |
| 動作電圧 | 5V |
| 表示サイズ | 57.60 × 43.20 mm |
| 外形寸法 | 70.20 × 50.20 mm |
| バックライト | プログラム制御可能 |
| 拡張 | MicroSD スロット（画像表示） |

## 接続とピン配置
公式 Wiki に記載されている接続テーブルを使うと、Raspberry Pi Pico の各 GPIO とディスプレイの対応ピンがわかりやすくなっています（USB 端子の方向を揃えて接続するのが推奨）。重要な接続を抜き出すと：

- `VCC` → Pico `VSYS`（5V 電源）
- `GND` → Pico `GND`
- `LCD_CS` → `GP9`
- `LCD_DC` → `GP8`
- `LCD_CLK` → `GP10`
- `MOSI` → `GP11`
- `MISO` → `GP12`
- `LCD_BL` → `GP13`（バックライト PWM 制御）
- `LCD_RST` → `GP15`（リセット）
- `TP_CS` / `TP_IRQ` などタッチ制御と MicroSD（GP16〜GP22）も含まれる

SPI は 4 線（CLK/MOSI/MISO/CS）で、最大 60MHz 程度まで利用されており、RGB565（16bit）あるいは RGB666（18bit）入力に対応しています。RST・CS・DC のロジックレベルも Wiki に詳細が載っています。

## 特長
- 専用の抵抗膜式タッチコントローラ（XPT2046）により、従来の AD 測定より滑らかなタッチ動作が可能。
- MicroSD カードスロットを利用して画像を保存・直接表示できる。
- バックライトは PWM で調整でき、省電力用途でも柔軟。
- Pico 向けの C/C++ / MicroPython デモコードと開発資料を提供（公式ページに付属）

## 備考
- 内部的には ST7789VW を採用しており、LCD 側のインタフェースは 240×320 ピクセル（縦×横）で制御される。データは SPI0、MSB 先行、CPHA=0／CPOL=0 のモードで送信する。
- リセット（RESX）、チップ選択（CSX）、データ/コマンド（D/CX）の信号レベルについても Wiki に記載あり。詳細なタイミングやシリアル仕様は ST7789 データシート（Datasheet Page 55 など）も参照すること。

このドキュメントは `docs/` 以下で管理し、本プロジェクトのハードウェア選定や制御ロジックの指針として共有してください。
