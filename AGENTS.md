# AGENTS.md - Project Rules for pi-pico-display-controller

## Hardware
- 本プロジェクトのホストは Raspberry Pi 5 です。
- ホストに接続されている Raspberry Pi Pico 2 W が表示制御を担い、WAVESHARE-19804 ディスプレイで出力される構成です。

## ドキュメント
- すべての設計資料、運用手順、API 仕様などのドキュメントは `docs/` 配下に集約してください。
- `docs/` 配下のファイルがプロジェクトの情報源となるため、変更履歴や補足情報も併せて記録してください。

## その他のルール
- ここに記載したハードウェア構成とドキュメントの配置を守り、プロジェクトの整合性を保ってください。

## Picoコマンド送信ルール（フリーズ再発防止）
- Picoへのコマンド送信は、必ずこのリポジトリ内の `scripts/pico-ctl.sh` を使用してください。
- `/tmp/pico-cmd-fifo` への直接書き込み（`echo` / `printf` / リダイレクト）は禁止です。
- 1行JSON送信は `scripts/pico-ctl.sh send '<json>'` を使用してください。
- `!` や引用符を含む複雑なJSONは `scripts/pico-ctl.sh send-stdin` + HEREDOC で送信してください。
- 既存手順やドキュメント内に直接FIFO書き込みがあれば、順次 `scripts/pico-ctl.sh` 利用へ統一してください。
