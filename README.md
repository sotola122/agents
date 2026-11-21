# agents catalog

agent、AGENTS.md、skillsを一か所で管理し、Cursor や OpenCode などへ配布するためのリポジトリです。

外部リポジトリから取り込むファイルはコミット ID で固定します。
そのため、どこからどの版を取り込んだのかを `sources.toml` と `sources.lock.toml` で確認できます。

skill ごとの取り込み元・pin の経緯・有効化の注意は [docs/assets.md](docs/assets.md) にまとめています。

## 導入

Python 3.11 以降と Git が必要です。

macOS / Linux：

```console
curl -fsSL https://raw.githubusercontent.com/sotola122/agents/main/install.sh | sh
```

Windows（PowerShell）：

```powershell
irm https://raw.githubusercontent.com/sotola122/agents/main/install.ps1 | iex
```

clone 済みなら、リポジトリ内で `./install.sh`、または `powershell -ExecutionPolicy Bypass -File .\install.ps1` を実行します。

導入スクリプトは次の順に処理します。

1. Python 3.11 以降と Git を確認します。
2. clone の外から実行した場合は `~/agents` へ clone します（`AGENTS_DIR` で変更、clone 元は `AGENTS_REPO`）。既にある clone は更新しません。
3. `agents` コマンドを PATH に置きます。
   - macOS / Linux：`~/.local/bin/agents` から `bin/agents` への symlink（`AGENTS_BIN_DIR` で変更）。同名の別ファイルがあれば中断します。
   - Windows：リポジトリの `bin` をユーザーの PATH に追加します（`bin/agents.cmd`）。
4. `agents` で配布し、`agents ls` で配布先と件数を表示します。配布しない場合は `--no-apply`（PowerShell は `-NoApply`）を付けます。

`agents` は同名の skill directory を配布先で置き換えます。既存の環境へ初めて導入するときは、`--no-apply` で導入してから `agents diff` で確認してください。

## 使い方

| コマンド | 動作 |
|---|---|
| `agents` | 必要なときだけ外部リポジトリを同期し、有効な asset を配布する |
| `agents diff` | 配布せずに差分を表示する |
| `agents up` | 取得元の最新 commit へ pin を進め、同期して配布する |
| `agents up -n` | 更新候補を表示するだけ（書き込みなし） |
| `agents on <name>...` / `agents off <name>...` | asset を有効化・無効化する（配布は次の `agents` で行う） |
| `agents ls` | 配布先・有効な件数・設定の問題を表示する（`-v` で asset ごと） |

- `<name>` には asset ID（`mattpocock/tdd`、`local/pi`）か短い名前（`tdd`、`pi`）を指定します。短い名前が複数に当てはまる場合はエラーになり、候補を表示します。
- `agents`・`agents diff`・`agents up` は `-H <harness>` で配布先を、`-k <kind>` で種類を一時的に変えられます。カンマ区切りで複数、`all` で全部を指定できます。
  - harness：`cursor`、`opencode`、`omp`、`pi`、`shared`、`hermes`、`claude`
  - kind：`skill`、`agent`、`context`
  - 対応しない組み合わせ（例：agent と pi、context と claude）は飛ばします。一つも対応しない指定だけエラーにします。
- `agents up -s <source>` で特定の取得元だけを更新します。
- `agents` はどのディレクトリから実行しても、このリポジトリを対象にします。

`agents` と `agents diff` は、`sources.toml` と `sources.lock.toml`・`.cache` が食い違うとき（初回、pin の変更、asset の追加・削除、cache の破損）だけ外部リポジトリへ接続します。`agents up` は常に接続します。`agents on` / `off` / `ls` は接続しません。

### 差分の表示

`agents diff` の各行は次の記号です。

- `+`：追加
- `~`：更新
- `-`：削除

先頭の `summary: +N  ~N  -N` はファイル単位の件数です。`agents` も最後に同じ形式で件数を表示します。
以前配布し、今回の対象外になった asset は `[… → harness remove]` と表示され、`-` 行が削除予定です。
ターミナル表示時は `+` 緑 / `~` 黄 / `-` 赤で色分けします（`NO_COLOR` 設定時やパイプ／`--output` では無色）。

### 終了コード

| コマンド | 0 | 1 | 2 |
|---|---|---|---|
| `agents`、`agents up`、`on`、`off`、`ls` | 成功 | — | 設定・引数の誤り、失敗 |
| `agents diff` | 差分なし | 差分あり | 設定・引数の誤り、失敗 |
| `agents up -n` | 更新候補なし | 更新候補あり | 設定・引数の誤り、失敗 |

## 配布先

- Cursor：`~/.cursor/`
- OpenCode：`~/.config/opencode/`
- OMP：`~/.omp/`
- Pi：`~/.pi/agent/`
- Shared：`~/.agents/skills/`
- Claude Code：`~/.claude/skills/`（skill のみ）
- Hermes：`${HERMES_HOME}/skills/anago/`（`HERMES_HOME` 未設定時は `~/.hermes/skills/anago/`）

各配布先には、配布したファイルの一覧 `.catalog-applied.toml` を置きます。`agents` が削除するのは、この一覧にあり今回の対象外になったものだけです。

## 設定（assets.local.toml）

端末ごとの設定は `assets.local.toml`（Git 管理外。雛形は `assets.local.toml.example`）にまとめます。
`agents` を実行すると、足りない設定を追記します。既存の値とコメントは保持します。

```toml
[apply]
harnesses = ["cursor", "omp", "claude"]

[external]
"mattpocock/tdd" = true
"mattpocock/ask-matt" = false

[skills]
pi = true
omp = true
harness-sessions = true
```

- `[apply] harnesses`：既定の配布先。ないときは、`.catalog-applied.toml` がある配布先（なければ設定 directory がある配布先）を追記します。どちらもなければ `sources.toml` の `[apply] default_harnesses` を使います。
- `[external]`：`sources.toml` の asset ID。セクションがないときは外部 asset をすべて配布し、あるときは `true` だけ配布します。追記する値は、セクションがあれば `false`、なければ `true` です。
- `[skills]` / `[agents]` / `[context]`：このリポジトリ直下の local asset。`true` だけ配布します。新しい `skills/<name>/SKILL.md` は `false` で追記します。ドットを含む名前は引用符で囲みます（例：`"AGENTS.md" = true`）。

値は `agents on` / `agents off` で書き換えられます。手で編集してもかまいません。

`sources.toml` から消えた ID や、リポジトリから消えた local asset の設定は削除せずに残し、配布の対象から外します。`agents ls` が `! ignored setting` として表示します。

以前の `apply.local.toml` は廃止しました。残っているとエラーになるので、`default_harnesses` の値を `[apply] harnesses` へ移してから削除してください。

### 特定の配布先から local skill を外す

`sources.toml` の `[apply.local_skill_excludes]` に、配布先ごとの skill 名を指定します。
現在は Hermes 標準の Codex CLI skill と重なるため、`skills/codex` だけを Hermes の対象から外しています。

```toml
[apply.local_skill_excludes]
hermes = ["codex"]
```

この除外は local skill だけに適用されます。

## ディレクトリ構成

- `skills/`：このリポジトリで直接管理するエージェントスキル（local asset）
- `agents/`：このリポジトリで直接管理するエージェント向けプロンプト
- `context/`：このリポジトリで直接管理する、各ツールで共有する指示
- `catalog/`：`agents` コマンドの実装（Python 標準ライブラリと Git だけを使用）
- `bin/`：`agents` コマンドの入口（`agents`、`agents.cmd`）
- `docs/`：asset ごとの補足

local asset は `skills/<name>/`・`agents/<name>.md`・`context/<name>.md` に置き、`agents on <name>` で有効にします。
`sources.toml` へは登録しません（登録するとエラーになります）。

## 外部リポジトリのファイルを登録する

`sources.toml` に取得元と管理対象を追加します。

`[[sources]]` には取得元の Git リポジトリを記述します。
`rev` にはブランチ名やタグ名ではなく、40桁または64桁の完全なコミット ID（pin）を指定します。
`sources.lock.toml` の `export_hash` はキャッシュ内容の整合性用ハッシュで、pin とは別物です。手編集せず、`agents` / `agents up` が生成します。

`[[assets]]` には取得するパス、論理上の配置名（`target`）、配布できるツールを記述します。

```toml
[[sources]]
id = "example-skills"
url = "https://github.com/example/skills.git"
rev = "0123456789abcdef0123456789abcdef01234567"
license = "MIT"

[[assets]]
id = "example/tdd"
source = "example-skills"
kind = "skill"
path = "skills/tdd"
target = "skills/tdd"
harnesses = ["cursor", "opencode", "shared"]
```

登録後に `agents` を実行すると、指定したコミットから Git の管理対象ファイルだけを取得して `.cache/sources/` へ置き、`sources.lock.toml` を更新してから配布します。
外部 asset はリポジトリ内の `skills/` / `agents/` / `context/` にはコピーしません。

## Hermes の旧 skill 配置を削除する

Hermes harness の skill は `HERMES_HOME` が設定されている場合は `${HERMES_HOME}/skills/anago/<name>/`、未設定時は `~/.hermes/skills/anago/<name>/` へ配布します。
旧 `~/.hermes/skills/<name>/` からの migration 機能はありません。

切り替え時は `~/.hermes/.catalog-applied.toml` の `kind = "skill"` entry と実在する directory を照合し、旧 `skills/<name>` に一致する管理対象だけを列挙します。
一覧を確認してから各 directory を個別に削除し、`agents -H hermes -k skill` を実行してください。
`~/.hermes/skills/*` のような wildcard は使わず、manifest にない user-owned skill と `~/.hermes/skills/anago/` は残します。

## テスト

```console
python3 -m unittest discover -s catalog/tests -v
```
