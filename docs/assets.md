# 配布する asset の補足

skill ごとの取り込み元・pin の経緯・有効化の注意をまとめます。導入と操作は [README](../README.md) を参照してください。

Anago はレビュー／ワークフロー skill を自リポジトリで管理する。このリポジトリでは CLI 委譲用 harness skill（`skills/pi`、`skills/codex`、`skills/claude`、`skills/cursor`、`skills/omp`）を管理する。
各 harness skill は単一の `SKILL.md` で CLI の起動、権限、workspace、入出力、検証、native session の再開を扱い、task prompt、review lens は同梱しない。
`big-bang`・`claude`・`cursor`・`codex`・`pi`・`omp` を配布するときは、共通の履歴管理を担う `harness-sessions` も有効にします。
履歴は対象 workspace 内の呼び出し元 harness directory に保存します（例: `.hermes/agent-sessions/cursor/`）。
同じ directory の `.gitignore` で `/agent-sessions/` を除外し、native session ID、決定事項、検証結果、次の作業を残します。
Big Bang の初回・継続待機は10分以上とし、タイムアウト後は状態を確認して待機継続・助言・中断を判断します。
`omp` は Oh My Pi CLI の実行・再開を扱います。既存環境では `agents on omp harness-sessions` を実行してから `agents` で配布します。

`design-docs` は設計判断と代替案の比較を含む日本語の設計文書を作成します。
ページ数は設計内容に応じて決め、ユーザーがページ数を指定した場合のみその指定に従います。シーケンス図やクラス図などの図はMermaidで記述します。
既存環境では `agents on harness-sessions design-docs` を実行してから `agents diff` / `agents` を実行します。

`deepsearch` は [MaryCache/imozuru](https://github.com/MaryCache/imozuru) の commit `30c3b59a076ce228f05aa3036809297422f23dee` を基にしたローカルスキルです。
取り込み済みの修正には、日本語を含む URL と W で始まる題名での停止回避、http(s) 以外と手元・内側の宛先の拒否、つなぐ直前の引き直しと IPv6 から IPv4 への短い待ち、PMC を Europe PMC の全文 XML から取ること、YouTube 自動字幕を動画の元の言語に限ること、和文が3割を超える PDF の下限 1,000 字、保存名と抜き書きパスの境界検査、検索結果の URL・本文・フィードを他人の入力として扱う検査、OCR の言語選択と低い確信度の拒否、止めたあとの詳細レポート（`digest.py`）、原文の改行を LF にそろえること、Markdown の箇条書きにまたがる抜き書きの照合、保存先に同名フォルダがあるときの拒否、`pdftotext` が無いときの pdfminer.six、数の直前の負号を落とした抜き書きの拒否、双方向制御文字をエスケープした保存名の検査、取得記録への時刻、Playwright で外のページを開くときの明示的なサンドボックス（起動できなければ `--no-sandbox` を足さずユーザーのブラウザへ切り替える）が含まれます。履歴を横断するダッシュボード（`dashboard.py`）は、調査1件の手順に使わないため同梱していません。
スキル本文・補足資料・コード内の説明は英語にし、調査結果・調査マップ・HTMLレポートは日本語で出力します。引用原文は保持し、日本語訳を添えます。
調査資料は作業プロジェクト内の `.research/<topic>/` に保存します。`/deepsearch <topic>` で原典をたどる調査、`/deepsearch watch <topic>` で登録したRSS/Atomの新着を確認できます。
資料取得・引用照合・更新確認・引用追跡のスクリプトとMITライセンスを同梱しています。
英語の手順と日本語の成果物へ改変して同梱しているため、`sources.toml` には登録しません。上流の更新は自動では取り込みません。
既存環境では `agents on deepsearch` を実行してから `agents diff` / `agents` を実行します。

`summary` は `/summary` で現在の会話を引き継ぎ用の要約にまとめ、新しいセッション・別 harness・分岐先の agent が作業を継続できるようにします（保存先は OS の一時ディレクトリ）。
長くなった orchestrator セッションのトークン消費を抑えるため、タスクの区切りで要約して新しいセッションに切り替えます。
有効にするには `agents on summary` を実行します。

Herdrの操作skillは公式リポジトリをcommit `e8d7d9705a7a2c89cef4dd42079379f05685af87`で固定して取り込みます。
`skills/herdr` の tree は直前の pin `ee5bfb5041bb3e4a49d591c72308aae3c81ecdde` と同一です。進めた差分は、handoff の再試行、大量 pane の回収、明るい端末の theme、止まった TUI への画面キューです。待機時間の要件は変わりません。
このskillは`HERDR_ENV=1`のmanaged pane内だけで動作し、実際のcommand構文はinstalled `herdr` binaryのhelpを正とします。

unslopのskillは https://github.com/heydamir/unslop をcommit `620163eedb3529d9cd23a3994ed8d287d06f760d`で固定して取り込みます。
vibecodedなUIを、製品に合う画面へ直すskillです。ライセンスは CC-BY-4.0 です。
path は `skills/unslop`、配布先は `skills/unslop` です。SKILL.md の相対参照（agents/・references/・scripts/）をそのまま配布します。

ponytailのskillは公式リポジトリをcommit `ebd8654c2c627f721eb8f9c0d1bd4090a29f9e10`（v5.3.3 の 4 commit 後）で固定して取り込みます。
6本（`ponytail`、`ponytail-review`、`ponytail-audit`、`ponytail-debt`、`ponytail-gain`、`ponytail-help`）を `sources.toml` に記載し、既定の有効化は `ponytail` と `ponytail-review` のみです。
6本の skill tree は直前の pin `96608e078b2d5ea607c5c3b8b5a54d1c1fba6846`（v5.3.3）と同一です。進めた差分は、取り込まない hook の stdin の UTF-8 decode と band import の修正、README の Braids です。

yomiyasuのskillは公式リポジトリをcommit `ddf365b5d5b36a7aa4ffab798dce1b694dbb1afd`（v3.3.0）で固定して取り込みます。
直前の pin `c49d5f1bee91258e33e1febc3569c6c87be7669e`（v3.2.3）から、配布する差分は SKILL.md の version、主語と述語が離れた文の語順、種類を指定しないときの pause_comma、calque の「段」と「門」、入れ子の文で主語の役が入れ替わった推敲の diff です。ファイルの追加と削除はなく、path は `skills/yomiyasu` のままです。
スキル本体は `skills/yomiyasu/` にあり、SKILL.md の相対参照（references/・scripts/・assets/）をそのまま配布します。
lint が Unicode 由来の絵文字表を埋め込んでいるため、skill ディレクトリ内の `LICENSE`（MIT）と `UNICODE-LICENSE.txt`（Unicode License V3。リポジトリルートと同一）も一緒に配布します。vendored の本文は編集しません。
frontmatter の `allowed-tools` は Claude Code 向けで、スクリプト経路に `${CLAUDE_SKILL_DIR}` を使います。Claude Code 以外ではこの変数は展開されないため、SKILL.md の指示どおりスキルディレクトリの絶対パスに置き換えて実行します。

mattpocock/skills は commit `abeeaf95660ba9e8b7c753eb38f441ca707a8823` で固定します。
登録済み skill の tree は直前の pin `5863806dd4e15c63174bee4e7515a4256792ecfa` と同一です。進めた差分は、未登録の in-progress `software-factory` の frontmatter を YAML として引用したことと、その検査を CI に足したことです。登録しません。`chief-of-staff` も未登録のままです。`ask-matt` は `chief-of-staff` へ経路を持たないため、その skill は pin しません。
upstream は `resolving-merge-conflicts` を `daa01d8` で削除しました。archived のドキュメントは「後継 skill はない」と明記しているため、その path は再登録しません。
`d81f3a183412` で engineering に昇格した `implement-spec`、`pr`、`retro` を登録し、`ask-matt` が指す経路と揃えています。既定の有効化はいずれも `true` です。
domain 文書のファイル名は、外部 skill の指示上 `CONTEXT.md` / `CONTEXT-MAP.md` から `GLOSSARY.md` / `GLOSSARY-MAP.md` に変わっています。
