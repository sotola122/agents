# agents catalog

agent、AGENTS.md、skillsを一か所で管理し、Cursor や OpenCode などへ配布するためのリポジトリです。

外部リポジトリから取り込むファイルはコミット ID で固定します。
そのため、どこからどの版を取り込んだのかを `sources.toml` と `sources.lock.toml` で確認できます。

## ディレクトリ構成

配布元となるファイルは、種類ごとに三つのディレクトリへ置きます。

- `skills/`：このリポジトリで直接管理するエージェントスキル（local asset）
- `agents/`：このリポジトリで直接管理するエージェント向けプロンプト
- `context/`：このリポジトリで直接管理する、各ツールで共有する指示

Anago はレビュー／ワークフロー skill を自リポジトリで管理する。このリポジトリでは CLI 委譲用 harness skill（`skills/pi`、`skills/codex`、`skills/cursor`）を管理する。
各 harness skill は単一の `SKILL.md` で CLI の起動、権限、workspace、入出力、検証だけを扱い、task prompt、出力 schema、review lens は同梱しない。

Herdrの操作skillは公式リポジトリのv0.8.2 tagをcommit `9eb521456ac0d19d3ab3d9d7cea3cca10baa8a4c`で固定して取り込みます。
このskillは`HERDR_ENV=1`のmanaged pane内だけで動作し、実際のcommand構文はinstalled `herdr` binaryのhelpを正とします。

unslopのskillは公式リポジトリ全体をcommit `d81f5196167ded24f46fced04958c0c12d681798`で固定して取り込みます。
SKILL.mdがreferences/・presets/・scripts/等の相対参照を持つため、repoルート(`path = "."`)ごとexportしています。
catalogのroot export対応(`catalog/core.py`の`_export_asset`)により実現しています。

ponytailのskillは公式リポジトリをcommit `2ed6c52c9d7e5e56942508591085fd45dea277d3`で固定して取り込みます。
6本（`ponytail`、`ponytail-review`、`ponytail-audit`、`ponytail-debt`、`ponytail-gain`、`ponytail-help`）を `sources.toml` に記載し、既定の有効化は `ponytail` と `ponytail-review` のみです。

natural-japaneseのskillは公式リポジトリをcommit `0f1cc1c5a4e2aa7590598c88a15c213a60d9545a`で固定して取り込みます。
スキル本体は `skills/natural-japanese/` にあり、SKILL.md の相対参照（references/・scripts/・assets/）をそのまま配布します。

`catalog/` には、外部リポジトリからファイルを取り込み、各ツールの設定ディレクトリへ配布するコマンドが入っています。

配布先は次のとおりです。

- Cursor：`~/.cursor/`
- OpenCode：`~/.config/opencode/`
- OMP：`~/.omp/`
- Pi：`~/.pi/agent/`
- Shared：`~/.agents/skills/`
- Hermes：`${HERMES_HOME}/skills/anago/`（`HERMES_HOME` 未設定時は `~/.hermes/skills/anago/`）

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

`--harness` には `cursor`、`opencode`、`omp`、`pi`、`shared`、`hermes` を指定します。
ここでいう `harness` は、配布先となるツールや共通ディレクトリを指します。

指定を省略すると、`sources.toml` の `[apply]` にある `default_kinds` と `default_harnesses` が使われます。

特定のlocal skillを一部のharnessだけから除外する場合は、`sources.toml`の`[apply.local_skill_excludes]`にharnessごとのskill名を指定します。
現在はHermes標準のCodex CLI skillと重複するため、このリポジトリの`skills/codex`だけをHermesへのapply対象から除外しています。

```toml
[apply.local_skill_excludes]
hermes = ["codex"]
```

この除外はlocal skillだけに適用されます。`codex`はCursor、OpenCode、OMP、Pi、Sharedには従来どおり配布できます。

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
pi = true
codex = true
cursor = true
```

- `[external]` … `sources.toml` の `asset.id`。セクション省略時は外部をすべて適用。あるときは `true` だけ適用
- `[skills]` / `[agents]` / `[context]` … リポジトリ直下の local 資産（`true` のものだけ適用）
- `sync` は `sources.toml` の外部 pin をすべて同期する（enable の影響なし）

`sync`（`update` に伴う同期を含む）が成功すると、`assets.local.toml` に未登録の外部 asset と `skills/<name>/SKILL.md` を持つ local skill の設定を追記します。ファイルがなければ作成し、既存の値とコメントは保持します。
追記する値は、既存の `[external]` がある場合は `false`、省略されていた場合は従来の適用範囲を維持するため `true`、local skill は `false` です。`--asset` 指定時も設定の補完は一覧全体が対象です。
`[external]` に現在の `sources.toml` にない ID が残っている場合、設定を保持したまま `ignored setting` と表示し、適用対象から除外します。

`sources.toml` への local asset 登録は不要です（登録するとエラーになります）。

## コマンド一覧

- `validate`：設定ファイルとロックファイルの整合性を検証します。
- `sync`：外部リポジトリから、`sources.toml` に固定したコミット（pin）のファイルを取得し、キャッシュとロックファイルを更新します。
- `update`：取得元の HEAD へ pin を進め、その source のキャッシュとロックファイルまで同期します。
- `diff`：管理元（local はリポジトリ内、外部は `.cache`）と配布先を比較し、変更内容を表示します。
- `apply`：選択したファイルを配布先へコピーします。
- `status`：既定の選択内容と、各ファイルの同期状態を表示します。
- `check-updates`：取得元の HEAD と固定中のコミット ID を比較します（書き込みなし）。

`diff` の各行は次の記号です。

- `+`：追加（add）
- `~`：更新（update）
- `-`：削除（remove）

先頭の `summary: +N  ~N  -N` はファイル単位の件数です。
以前 apply 済みで今回の対象外になった asset は `[… → harness remove]` と表示され、`-` 行が削除予定です。
ターミナル表示時は `+` 緑 / `~` 黄 / `-` 赤で色分けします（`NO_COLOR` 設定時やパイプ／`--output` では無色）。

`apply` は更新後に残らないファイルを `removed <asset> -> <path>` と記録します。`sync` / `update` で不要なキャッシュなどを削除した場合も、削除完了後に `removed: <path>` を表示します。

`validate`、`diff`、`apply`、`status` はネットワークに接続しません。

`sync`、`update`、`check-updates` は外部リポジトリへ接続します。

`diff` は差分がある場合に終了コード `1`、差分がない場合に `0` を返します。
終了コード `1` は失敗ではなく、配布先に変更が必要であることを表します。

`check-updates` は更新候補がある場合に終了コード `1`、候補がない場合に `0` を返します。
`update` は更新の有無にかかわらず成功時は終了コード `0` を返します。

設定や引数に誤りがある場合、各コマンドは終了コード `2` を返します。

## 外部リポジトリのファイルを登録する

外部リポジトリからファイルを取り込むには、`sources.toml` に取得元と管理対象を追加します。

`[[sources]]` には取得元の Git リポジトリを記述します。
`rev` にはブランチ名やタグ名ではなく、40桁または64桁の完全なコミット ID（pin）を指定します。
`sources.lock.toml` の `export_hash` はキャッシュ内容の整合性用ハッシュで、pin とは別物です。手編集せず、`sync` / `update` が生成します。

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

## 外部リポジトリの更新を取り込む

取得元に新しいコミットがあるかは `check-updates` で確認できます。

```console
python -m catalog check-updates
```

pin を remote HEAD へ進め、キャッシュとロックまで一度に更新するには `update` を使います。
特定の取得元だけ更新する場合は `--source` を指定します。

```console
python -m catalog update
python -m catalog update --source example-skills
```

`update` のあと、配布先へ反映するには従来どおり `diff` / `apply` を実行します。

## このリポジトリで直接管理するファイル

外部リポジトリから取得しないスキルは、`skills/<name>/` に置き、`assets.local.toml` で有効化します。
`sync` の対象外で、`diff` / `apply` はリポジトリ内のディレクトリをそのまま配布します。

```toml
# assets.local.toml（gitignored）
[skills]
pi = true
codex = true
cursor = true
```

`agents/` や `context/` の local ファイルも同様に `[agents]` / `[context]` で有効化できます。
ドットを含むファイル名は TOML キーを引用符で囲みます（例: `"AGENTS.md" = true`）。

## Hermes の旧 skill 配置を削除する

Hermes harness の skill は `HERMES_HOME` が設定されている場合は `${HERMES_HOME}/skills/anago/<name>/`、未設定時は `~/.hermes/skills/anago/<name>/` へ配布します。
旧 `~/.hermes/skills/<name>/` からの migration 機能はありません。

切り替え時は `~/.hermes/.catalog-applied.toml` の `kind = "skill"` entry と実在する directory を照合し、旧 `skills/<name>` に一致する管理対象だけを列挙します。
一覧を確認してから各 directory を個別に削除し、`python -m catalog apply --harness hermes --kind skill` を実行してください。
`~/.hermes/skills/*` のような wildcard は使わず、manifest にない user-owned skill と `~/.hermes/skills/anago/` は残します。

## テスト

```console
python -m unittest discover -s catalog/tests -v
```
