#!/bin/sh
# Install the agents CLI and distribute the enabled assets.
#
#   ./install.sh                 (inside a clone)
#   curl -fsSL https://raw.githubusercontent.com/sotola122/agents/main/install.sh | sh
#   curl -fsSL .../install.sh | sh -s -- --no-apply
#
# Environment:
#   AGENTS_DIR      clone 先（clone の外から実行したとき。既定 ~/agents）
#   AGENTS_REPO     clone 元（既定 https://github.com/sotola122/agents.git）
#   AGENTS_BIN_DIR  agents コマンドの置き場所（既定 ~/.local/bin）
set -eu

die() {
	echo "install.sh: $*" >&2
	exit 1
}

apply=1
for arg in "$@"; do
	case $arg in
	--no-apply) apply=0 ;;
	-h | --help)
		echo "usage: install.sh [--no-apply]（環境変数: AGENTS_DIR, AGENTS_REPO, AGENTS_BIN_DIR）"
		exit 0
		;;
	*) die "未知の引数です: $arg" ;;
	esac
done

command -v git >/dev/null 2>&1 || die "git が見つかりません"
python=
for candidate in python3 python; do
	if command -v "$candidate" >/dev/null 2>&1 &&
		"$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
		python=$candidate
		break
	fi
done
[ -n "$python" ] || die "Python 3.11 以降が見つかりません"

# Run from a clone: use it. Piped from curl ($0 is the shell): clone first.
root=
case $0 in
*install.sh) root=$(cd "$(dirname "$0")" && pwd -P) ;;
esac
if [ -z "$root" ] || [ ! -f "$root/sources.toml" ]; then
	root=${AGENTS_DIR:-$HOME/agents}
	if [ -f "$root/sources.toml" ]; then
		echo "既存の clone を使います: $root"
	elif [ -e "$root" ]; then
		die "$root は agents の clone ではありません。AGENTS_DIR で別の場所を指定してください"
	else
		git clone --quiet "${AGENTS_REPO:-https://github.com/sotola122/agents.git}" "$root"
		echo "clone しました: $root"
	fi
fi

bin_dir=${AGENTS_BIN_DIR:-$HOME/.local/bin}
link=$bin_dir/agents
target=$root/bin/agents
mkdir -p "$bin_dir"
if [ -e "$link" ] || [ -L "$link" ]; then
	[ -L "$link" ] && [ "$(readlink "$link")" = "$target" ] ||
		die "$link は別のファイルです。削除するか AGENTS_BIN_DIR を指定してください"
else
	ln -s "$target" "$link"
fi
echo "agents コマンド: $link -> $target"
case ":$PATH:" in
*":$bin_dir:"*) ;;
*)
	echo "注意: $bin_dir が PATH にありません。シェルの設定に次を追加してください:"
	echo "  export PATH=\"$bin_dir:\$PATH\""
	;;
esac

if [ "$apply" = 1 ]; then
	"$target"
	"$target" ls
else
	echo "配布するには agents を実行してください"
fi
