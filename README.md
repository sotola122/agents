# agents catalog

agent、AGENTS.md、skillsを一か所で管理し、Cursor や OpenCode などへ配布するためのリポジトリです。

外部リポジトリから取り込むファイルはコミット ID で固定します。
そのため、どこからどの版を取り込んだのかを `sources.toml` と `sources.lock.toml` で確認できます。

## ディレクトリ構成

配布元となるファイルは、種類ごとに三つのディレクトリへ置きます。

- `skills/`：このリポジトリで直接管理するエージェントスキル（local asset）
- `agents/`：このリポジトリで直接管理するエージェント向けプロンプト
- `context/`：このリポジトリで直接管理する、各ツールで共有する指示

Anago はレビュー／ワークフロー skill を自リポジトリで管理する。このリポジトリから Anago が同期するのは harness skill（`skills/delegate-pi`、`skills/delegate-codex`）のみ。

`catalog/` には、外部リポジトリからファイルを取り込み、各ツールの設定ディレクトリへ配布するコマンドが入っています。

配布先は次のとおりです。

- Cursor：`~/.cursor/`
- OpenCode：`~/.config/opencode/`
- OMP：`~/.omp/`
- Pi：`~/.pi/agent/`
- Shared：`~/.agents/skills/`

## 動作環境

Python 3.11 以降と Git が必要です。

以下のコマンドはリポジトリのルートで実行します。

## 初回の同期と配布

```console
python -m catalog validate
```

外部リポジトリから指定のバージョンを取得し、`.cache` とロックファイルを更新します。

```console
python -m catalog sync
```

配布先との差分を確認します。

```console
python -m catalog diff
```

差分に問題がなければ、ファイルを配布します。

```console
python -m catalog apply
```

最後に、取り込んだファイルの状態を確認します。

```console
python -m catalog status
```

初期設定では Cursor が配布先です。
別のツールへ配布する方法は「配布先を選ぶ」で説明します。

## 必要なファイルだけを同期する

`sources.toml` の `[[assets]]` には、外部リポジトリから取り込むファイル一式が登録されています。

`--asset` にその ID を渡すと、指定したものだけを同期できます。

```console
python -m catalog sync --asset example/tdd
```

複数の ID は、`--asset` を繰り返すか、カンマで区切って指定します。

`sync` は実行のたびに `.cache/sources` を作り直し、参照されなくなったキャッシュを削除します。

## 配布先を選ぶ

`diff` と `apply` では、配布するファイルの種類と配布先を指定できます。

```console
# Cursor へスキルだけを配布する
python -m catalog diff --harness cursor --kind skill
python -m catalog apply --harness cursor --kind skill

# Cursor へスキルと共通指示を配布する
python -m catalog diff --harness cursor --kind skill,context
python -m catalog apply --harness cursor --kind skill,context

# Cursor とSharedへ同時に配布する
python -m catalog apply --harness cursor,shared --kind skill
```

`--kind` には `skill`、`agent`、`context` を指定します。

`--harness` には `cursor`、`opencode`、`omp`、`pi`、`shared` を指定します。
ここでいう `harness` は、配布先となるツールや共通ディレクトリを指します。

指定を省略すると、`sources.toml` の `[apply]` にある `default_kinds` と `default_harnesses` が使われます。

端末ごとに既定の配布先を変えたい場合は、`apply.local.toml` を作成します。
このファイルは Git の管理対象外です。

```toml
default_harnesses = ["cursor"]
```

`diff` / `apply` に含める asset は、`assets.local.toml` で制御します（Git 管理外。雛形は `assets.local.toml.example`）。

```toml
[external]
"mattpocock/tdd" = true
"mattpocock/ask-matt" = false

[skills]
delegate-pi = true
delegate-codex = true
```

- `[external]` … `sources.toml` の `asset.id`。セクション省略時は外部をすべて適用。あるときは `true` だけ適用
- `[skills]` / `[agents]` / `[context]` … リポジトリ直下の local 資産（`true` のものだけ適用）
- `sync` は `sources.toml` の外部 pin をすべて同期する（enable の影響なし）

`sources.toml` への local asset 登録は不要です（登録するとエラーになります）。

## コマンド一覧

- `validate`：設定ファイルとロックファイルの整合性を検証します。
- `sync`：外部リポジトリからファイルを取得し、キャッシュとロックファイルを更新します。
- `diff`：管理元（local はリポジトリ内、外部は `.cache`）と配布先を比較し、変更内容を表示します。
- `apply`：選択したファイルを配布先へコピーします。
- `status`：既定の選択内容と、各ファイルの同期状態を表示します。
- `check-updates`：取得元の HEAD と固定中のコミット ID を比較します。

`diff` の各行は次の記号です。

- `+`：追加（add）
- `~`：更新（update）
- `-`：削除（remove）

先頭の `summary: +N  ~N  -N` はファイル単位の件数です。
以前 apply 済みで今回の対象外になった asset は `[… → harness remove]` と表示され、`-` 行が削除予定です。
ターミナル表示時は `+` 緑 / `~` 黄 / `-` 赤で色分けします（`NO_COLOR` 設定時やパイプ／`--output` では無色）。

`validate`、`diff`、`apply`、`status` はネットワークに接続しません。

`sync` と `check-updates` は外部リポジトリへ接続します。

`diff` は差分がある場合に終了コード `1`、差分がない場合に `0` を返します。
終了コード `1` は失敗ではなく、配布先に変更が必要であることを表します。

`check-updates` は更新候補がある場合に終了コード `1`、候補がない場合に `0` を返します。

設定や引数に誤りがある場合、各コマンドは終了コード `2` を返します。

## 外部リポジトリのファイルを登録する

外部リポジトリからファイルを取り込むには、`sources.toml` に取得元と管理対象を追加します。

`[[sources]]` には取得元の Git リポジトリを記述します。
`rev` にはブランチ名やタグ名ではなく、40桁または64桁の完全なコミット ID を指定します。

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

登録後に `sync` を実行すると、指定したコミットから Git の管理対象ファイルだけを取得し、`.cache/sources/` へ配置して `sources.lock.toml` を更新します。
外部資産はリポジトリ内の `skills/` / `agents/` / `context/` にはコピーしません。
`diff` / `apply` はロック経由で `.cache` から読みます。

```console
python -m catalog sync --asset example/tdd
```

## このリポジトリで直接管理するファイル

外部リポジトリから取得しないスキルは、`skills/<name>/` に置き、`assets.local.toml` で有効化します。
`sync` の対象外で、`diff` / `apply` はリポジトリ内のディレクトリをそのまま配布します。

```toml
# assets.local.toml（gitignored）
[skills]
delegate-pi = true
delegate-codex = true
```

`agents/` や `context/` の local ファイルも同様に `[agents]` / `[context]` で有効化できます。
ドットを含むファイル名は TOML キーを引用符で囲みます（例: `"AGENTS.md" = true`）。

## テスト

```console
python -m unittest discover -s catalog/tests -v
```
