"""Interactive toggle screen for `agents pick`.

Standard library only: termios on POSIX, msvcrt on Windows, ANSI escapes for
drawing. ``Picker`` and ``render`` hold all behavior and stay terminal-free.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tomllib
import unicodedata

from . import core

HARNESS_GROUP = "配布先"
HELP = "j/k 移動  Space 切替  a 群を一括  / 絞り込み  Tab 次の群  Enter 保存  q 中止"


@dataclasses.dataclass
class Item:
    section: str  # "apply" for harnesses, else the assets.local.toml section
    key: str
    label: str
    group: str
    original: bool
    checked: bool
    ident: str  # asset id, or the harness name

    @property
    def changed(self) -> bool:
        return self.checked != self.original


def build_items(config: core.Config, settings: dict) -> list[Item]:
    items = [
        Item("apply", harness, harness, HARNESS_GROUP, on, on, harness)
        for harness in config.allowed_harnesses
        for on in (harness in config.default_harnesses,)
    ]
    assets: list[Item] = []
    for asset in config.assets:
        if asset.is_local:
            continue
        on = core.apply_enabled(config, asset)
        owner, _, name = asset.id.rpartition("/")
        assets.append(Item("external", asset.id, name, f"{asset.kind}: {owner or asset.source}", on, on, asset.id))
    local_enabled = {asset.id for asset in config.assets if asset.is_local}
    for _section, _key, asset_id, kind in core._local_candidates(config):
        # Reuse the key spelling already in the file ("x" vs "x.md").
        section, key, _ = core._resolve_setting(config, settings, asset_id)
        on = asset_id in local_enabled
        assets.append(Item(section, key, PurePosixPath(asset_id).name, f"{kind}: local", on, on, asset_id))
    group_order = {group: index for index, group in enumerate(dict.fromkeys(item.group for item in assets))}
    assets.sort(key=lambda item: (group_order[item.group], item.label))
    return items + assets


class Picker:
    def __init__(self, items: list[Item]) -> None:
        self.items = items
        self.query = ""
        self.filtering = False
        self.cursor = 0  # index into visible()
        self.top = 0  # first body line shown
        self.message = ""

    def visible(self) -> list[int]:
        query = self.query.lower()
        return [
            index
            for index, item in enumerate(self.items)
            if not query or query in f"{item.group} {item.key} {item.label}".lower()
        ]

    def current(self) -> int | None:
        visible = self.visible()
        if not visible:
            return None
        self.cursor = max(0, min(self.cursor, len(visible) - 1))
        return visible[self.cursor]

    def handle(self, key: str) -> str | None:
        """Apply one key; return "save" or "quit" when the screen should close."""
        self.message = ""
        if self.filtering:
            if key == "enter":
                self.filtering = False
            elif key == "esc":
                self.filtering = False
                self.query = ""
            elif key == "backspace":
                self.query = self.query[:-1]
            elif len(key) == 1 and key.isprintable():
                self.query += key
            else:
                self._navigate(key)
            self.current()
            return None
        if self._navigate(key):
            return None
        if key in ("space", "x"):
            index = self.current()
            if index is not None:
                self.items[index].checked = not self.items[index].checked
        elif key == "a":
            self._toggle_group()
        elif key == "/":
            self.filtering = True
        elif key == "enter":
            if not any(item.checked for item in self.items if item.section == "apply"):
                self.message = "配布先を 1 つ以上選んでください"
                return None
            return "save"
        elif key in ("q", "esc"):
            return "quit"
        return None

    def _navigate(self, key: str) -> bool:
        visible = self.visible()
        step = {"up": -1, "k": -1, "down": 1, "j": 1, "pgup": -10, "pgdn": 10}
        if key in step and not (self.filtering and key in ("j", "k")):
            self.cursor += step[key]
        elif key == "home" or (key == "g" and not self.filtering):
            self.cursor = 0
        elif key == "end" or (key == "G" and not self.filtering):
            self.cursor = len(visible) - 1
        elif key == "tab" and visible:
            self.current()
            group = self.items[visible[self.cursor]].group
            following = [
                position for position in range(self.cursor + 1, len(visible))
                if self.items[visible[position]].group != group
            ]
            self.cursor = following[0] if following else 0
        else:
            return False
        self.current()
        return True

    def _toggle_group(self) -> None:
        index = self.current()
        if index is None:
            return
        group = self.items[index].group
        members = [i for i in self.visible() if self.items[i].group == group]
        target = not all(self.items[i].checked for i in members)
        for i in members:
            self.items[i].checked = target

    def changes(self) -> dict[str, dict[str, object]]:
        result: dict[str, dict[str, object]] = {}
        harnesses = [item for item in self.items if item.section == "apply"]
        if any(item.changed for item in harnesses):
            result["apply"] = {"harnesses": [item.key for item in harnesses if item.checked]}
        for item in self.items:
            if item.section != "apply" and item.changed:
                result.setdefault(item.section, {})[item.key] = item.checked
        return result

    def removed_harnesses(self) -> list[str]:
        return [item.key for item in self.items if item.section == "apply" and item.original and not item.checked]

    def describe_changes(self) -> list[str]:
        lines = []
        for item in self.items:
            if not item.changed:
                continue
            label = "on" if item.checked else "off"
            if item.section == "apply":
                lines.append(f"{label} -H {item.key}")
            else:
                lines.append(f"{label}: {item.ident}")
        return lines


def render(picker: Picker, width: int, height: int) -> list[tuple[str, str]]:
    """Screen lines as (text, style); style is "", "title", "group", or "cursor"."""
    harnesses = [item for item in picker.items if item.section == "apply"]
    assets = [item for item in picker.items if item.section != "apply"]
    changed = sum(1 for item in picker.items if item.changed)
    title = (
        f"agents pick  配布先 {sum(i.checked for i in harnesses)}/{len(harnesses)}"
        f"  asset {sum(i.checked for i in assets)}/{len(assets)}"
        + (f"  変更 {changed}" if changed else "")
    )
    if picker.filtering or picker.query:
        status = f"/{picker.query}" + ("_" if picker.filtering else "")
    else:
        status = picker.message or HELP

    body: list[tuple[str, str, int | None]] = []
    previous_group = None
    current = picker.current()
    for index in picker.visible():
        item = picker.items[index]
        if item.group != previous_group:
            body.append((item.group, "group", None))
            previous_group = item.group
        mark = "x" if item.checked else " "
        suffix = "  *" if item.changed else ""
        body.append((f"  [{mark}] {item.label}{suffix}", "cursor" if index == current else "", index))
    if not body:
        body.append(("  （該当なし）", "", None))

    rows = max(1, height - 3)
    cursor_line = next((n for n, (_t, _s, i) in enumerate(body) if i is not None and i == current), 0)
    # Keep the group header visible when the cursor sits on its first item.
    wanted = cursor_line - 1 if cursor_line > 0 and body[cursor_line - 1][2] is None else cursor_line
    if wanted < picker.top:
        picker.top = wanted
    elif cursor_line >= picker.top + rows:
        picker.top = cursor_line - rows + 1
    picker.top = max(0, min(picker.top, max(0, len(body) - rows)))
    visible_body = body[picker.top:picker.top + rows]

    lines = [(title, "title"), (status, "")]
    lines.extend((text, style) for text, style, _index in visible_body)
    return [(_fit(text, width - 1), style) for text, style in lines]


def _fit(text: str, width: int) -> str:
    out: list[str] = []
    used = 0
    for char in text:
        char_width = 2 if unicodedata.east_asian_width(char) in "WF" else 1
        if used + char_width > width:
            break
        out.append(char)
        used += char_width
    return "".join(out)


_STYLES = {"title": "\x1b[1m", "group": "\x1b[1m", "cursor": "\x1b[7m", "": ""}


class _Terminal:
    def __enter__(self) -> "_Terminal":
        self._saved = None
        if os.name == "nt":
            _enable_windows_vt()
        else:
            import termios
            import tty

            self._fd = sys.stdin.fileno()
            self._saved = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
        sys.stdout.write("\x1b[?1049h\x1b[?25l")
        sys.stdout.flush()
        return self

    def __exit__(self, *_exc: object) -> None:
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()
        if self._saved is not None:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)

    def draw(self, lines: list[tuple[str, str]]) -> None:
        out = ["\x1b[H"]
        for text, style in lines:
            prefix = _STYLES[style]
            out.append(f"{prefix}{text}\x1b[0m\x1b[K\r\n" if prefix else f"{text}\x1b[K\r\n")
        out.append("\x1b[J")
        sys.stdout.write("".join(out))
        sys.stdout.flush()

    def read_key(self) -> str:
        return _read_key_windows() if os.name == "nt" else _read_key_posix(self._fd)


_ESCAPES = {
    "[A": "up", "[B": "down", "[5~": "pgup", "[6~": "pgdn",
    "[H": "home", "[1~": "home", "OH": "home", "[F": "end", "[4~": "end", "OF": "end",
    "OA": "up", "OB": "down",
}
_CONTROL = {"\r": "enter", "\n": "enter", "\t": "tab", " ": "space", "\x7f": "backspace", "\x08": "backspace"}


def _read_key_posix(fd: int) -> str:
    import select

    first = os.read(fd, 1)
    if first == b"\x1b":
        sequence = b""
        while select.select([fd], [], [], 0.03)[0]:
            sequence += os.read(fd, 1)
            if sequence[-1:].isalpha() or sequence.endswith(b"~"):
                break
        return _ESCAPES.get(sequence.decode(errors="ignore"), "esc" if not sequence else "")
    # Complete a UTF-8 sequence so typed non-ASCII reaches the filter intact.
    lead = first[0]
    extra = 3 if lead >= 0xF0 else 2 if lead >= 0xE0 else 1 if lead >= 0xC0 else 0
    data = first + (os.read(fd, extra) if extra else b"")
    char = data.decode(errors="ignore")
    return _CONTROL.get(char, char)


def _read_key_windows() -> str:
    import msvcrt

    char = msvcrt.getwch()
    if char in ("\x00", "\xe0"):
        code = msvcrt.getwch()
        return {"H": "up", "P": "down", "I": "pgup", "Q": "pgdn", "G": "home", "O": "end"}.get(code, "")
    if char == "\x03":
        raise KeyboardInterrupt
    if char == "\x1b":
        return "esc"
    return _CONTROL.get(char, char)


def _enable_windows_vt() -> None:
    import ctypes

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
    mode = ctypes.c_uint32()
    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING


def run(root: Path) -> int:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise core.SyncError("agents pick は端末で実行してください（スクリプトからは agents on / off を使います）")
    config = core.load_config(root)
    path = root / core.LOCAL_ASSETS_REL
    settings = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    picker = Picker(build_items(config, settings))
    action = None
    try:
        with _Terminal() as terminal:
            while action is None:
                size = shutil.get_terminal_size()
                terminal.draw(render(picker, size.columns, size.lines))
                action = picker.handle(terminal.read_key())
    except KeyboardInterrupt:
        action = "quit"
    changes = picker.changes()
    if action != "save" or not changes:
        print("変更なし" if action == "save" else "中止しました（保存していません）")
        return 0

    for line in picker.describe_changes():
        print(line)
    with core._exclusive_sync_lock(root):
        core.write_settings(core.load_config(root), changes)
    removed = picker.removed_harnesses()
    summary = core._diff_summary_line(core.distribute(root, purge=removed, dry_run=True))
    if summary is None:
        print("配布先はすでに最新です")
        return 0
    print(f"配布すると {summary}")
    if removed:
        print(f"外した配布先（{', '.join(removed)}）に配布済みのファイルも削除します")
    try:
        answer = input("今すぐ配布しますか [Y/n] ").strip().lower()
    except EOFError:
        answer = "n"
    if answer not in ("", "y", "yes"):
        hint = f"。外した配布先のファイルは agents off -H {','.join(removed)} で削除します" if removed else ""
        print(f"設定だけ保存しました。配布するには agents を実行してください{hint}")
        return 0
    lines = core.distribute(root, purge=removed, dry_run=False)
    print(core._diff_summary_line(lines) or "no changes")
    return 0
