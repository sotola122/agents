"""Commit-pinned external asset synchronization.

The module intentionally depends only on Python's standard library and Git.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import difflib
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from typing import Iterable, Iterator, Mapping, Sequence

# path -> (content, mode); mode is 0o644 or 0o755
FileTree = dict[str, tuple[bytes, int]]
DEFAULT_FILE_MODE = 0o644
EXECUTABLE_FILE_MODE = 0o755


KINDS = ("skill", "agent", "context")
HARNESSES = ("cursor", "opencode", "omp", "pi", "shared", "hermes")
SUPPORTED: Mapping[str, frozenset[str]] = {
    "skill": frozenset(HARNESSES),
    "agent": frozenset(("cursor", "opencode", "omp")),
    "context": frozenset(("cursor", "opencode", "omp", "pi")),
}
PI_APPEND_REL = "APPEND_SYSTEM.md"
EXPORT_META_REL = ".export-meta.toml"
APPLIED_MANIFEST_REL = ".catalog-applied.toml"
SYNC_LOCK_REL = ".cache/sources/.sync.lock"
LOCAL_ASSETS_REL = "assets.local.toml"
# Section name in assets.local.toml -> catalog kind
LOCAL_ASSET_SECTIONS: Mapping[str, str] = {
    "skills": "skill",
    "agents": "agent",
    "context": "context",
}
OID_RE = re.compile(r"^[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
PI_BEGIN = "<!-- external-skill-sync:{asset}:begin -->"
PI_END = "<!-- external-skill-sync:{asset}:end -->"


@dataclasses.dataclass(frozen=True)
class AppliedOutput:
    asset_id: str
    root: str
    kind: str


class SyncError(RuntimeError):
    """A user-facing validation or synchronization error."""


@dataclasses.dataclass(frozen=True)
class Source:
    id: str
    url: str
    rev: str
    license: str


@dataclasses.dataclass(frozen=True)
class Asset:
    id: str
    source: str | None
    kind: str
    path: str
    target: str
    harnesses: tuple[str, ...]

    @property
    def is_local(self) -> bool:
        return self.source is None


@dataclasses.dataclass(frozen=True)
class Config:
    root: Path
    sources: Mapping[str, Source]
    assets: tuple[Asset, ...]
    default_kinds: tuple[str, ...]
    default_harnesses: tuple[str, ...]
    allowed_harnesses: tuple[str, ...]
    # None => every external asset is included in diff/apply.
    # frozenset => only these external asset ids (true in [external]) are included.
    # Local assets are already filtered at load (only enabled ones appear in assets).
    external_apply_enabled: frozenset[str] | None = None


@dataclasses.dataclass(frozen=True)
class LockAsset:
    id: str
    source: str
    rev: str
    export_hash: str
    target: str
    cache: str
    source_is_file: bool


def _read_toml(path: Path, *, optional: bool = False) -> dict:
    if optional and not path.exists():
        return {}
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream)
    except FileNotFoundError as exc:
        raise SyncError(f"設定ファイルがありません: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise SyncError(f"TOML が不正です: {path}: {exc}") from exc


def _safe_rel(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise SyncError(f"{label} は空でない POSIX 相対パスで指定してください")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise SyncError(f"{label} が安全な相対パスではありません: {value}")
    return path.as_posix()


def _safe_id(value: object, label: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise SyncError(f"{label} が不正です: {value!r}")
    if any(part in ("", ".", "..") for part in PurePosixPath(value).parts):
        raise SyncError(f"{label} に安全でない path segment があります: {value}")
    return value


def _string_list(value: object, label: str, allowed: Iterable[str]) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
        raise SyncError(f"{label} は空でない文字列配列で指定してください")
    result = tuple(dict.fromkeys(value))
    unknown = sorted(set(result) - set(allowed))
    if unknown:
        raise SyncError(f"{label} に未知の値があります: {', '.join(unknown)}")
    return result


def _default_target(kind: str, source_path: str) -> str:
    name = PurePosixPath(source_path).name
    if kind == "skill":
        return f"skills/{name}"
    if kind == "agent":
        return f"agents/{name if name.endswith('.md') else name + '.md'}"
    return f"context/{name}"


def _default_asset_harnesses(
    kind: str, allowed_harnesses: Sequence[str]
) -> tuple[str, ...]:
    return tuple(
        harness for harness in allowed_harnesses if harness in SUPPORTED[kind]
    )


def _read_assets_local(root: Path) -> dict:
    data = _read_toml(root / LOCAL_ASSETS_REL, optional=True)
    if not data:
        return {}
    allowed = set(LOCAL_ASSET_SECTIONS) | {"external"}
    unknown = set(data) - allowed
    if unknown:
        raise SyncError(
            f"{LOCAL_ASSETS_REL} に未知のキーがあります: {', '.join(sorted(unknown))}"
        )
    return data


def _parse_local_skill_excludes(
    value: object,
    *,
    root: Path,
    allowed_harnesses: Sequence[str],
) -> dict[str, frozenset[str]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SyncError("apply.local_skill_excludes は harness ごとのテーブルです")

    result: dict[str, frozenset[str]] = {}
    for harness, raw_names in value.items():
        if harness not in allowed_harnesses:
            raise SyncError(
                f"apply.local_skill_excludes に未知の harness があります: {harness}"
            )
        if not isinstance(raw_names, list) or not all(
            isinstance(name, str) for name in raw_names
        ):
            raise SyncError(
                f"apply.local_skill_excludes.{harness} は skill 名の配列です"
            )
        names: set[str] = set()
        for raw_name in raw_names:
            name = _safe_id(raw_name, f"apply.local_skill_excludes.{harness}")
            if len(PurePosixPath(name).parts) != 1:
                raise SyncError(
                    f"apply.local_skill_excludes.{harness} は skill 名だけを指定してください: {name}"
                )
            if not (root / "skills" / name).is_dir():
                raise SyncError(
                    f"apply.local_skill_excludes.{harness} に対応する local skill がありません: {name}"
                )
            names.add(name)
        result[harness] = frozenset(names)
    return result


def _parse_enable_table(
    table: object, *, section: str, known_ids: Iterable[str] | None = None
) -> dict[str, bool]:
    if not isinstance(table, dict) or not table:
        raise SyncError(f"{LOCAL_ASSETS_REL} の [{section}] は空でないテーブルです")
    known = set(known_ids) if known_ids is not None else None
    result: dict[str, bool] = {}
    for name, enabled in table.items():
        if not isinstance(name, str) or not name:
            raise SyncError(f"{LOCAL_ASSETS_REL} の [{section}] キーが不正です")
        if isinstance(enabled, dict):
            raise SyncError(
                f"{LOCAL_ASSETS_REL} の [{section}] でドット付きキーは引用符で囲んでください "
                f'(例: "{name}.…")'
            )
        if not isinstance(enabled, bool):
            raise SyncError(
                f"{LOCAL_ASSETS_REL} の [{section}].{name} は true/false で指定してください"
            )
        if known is not None and name not in known:
            raise SyncError(
                f"{LOCAL_ASSETS_REL} の [{section}] に未知の asset.id があります: {name}"
            )
        result[name] = enabled
    return result


def _load_local_assets(
    root: Path,
    data: Mapping[str, object],
    allowed_harnesses: Sequence[str],
    local_skill_excludes: Mapping[str, frozenset[str]],
    *,
    asset_ids: set[str],
    targets: set[str],
) -> list[Asset]:
    """Load enabled local assets from assets.local.toml (machine-local, gitignored)."""
    assets: list[Asset] = []
    for section, kind in LOCAL_ASSET_SECTIONS.items():
        table = data.get(section)
        if table is None:
            continue
        enables = _parse_enable_table(table, section=section)
        for name, enabled in enables.items():
            if not enabled:
                continue
            if kind == "skill":
                relative = f"skills/{name}"
            elif kind == "agent":
                filename = name if name.endswith(".md") else f"{name}.md"
                relative = f"agents/{filename}"
            else:
                filename = name if name.endswith(".md") else f"{name}.md"
                relative = f"context/{filename}"
            relative = _safe_rel(relative, f"local.{section}.{name}")
            basename = PurePosixPath(relative).name
            # Skills keep local/<dir>; agents/context nest under kind to avoid clashes.
            asset_id = _safe_id(
                f"local/{basename}" if kind == "skill" else f"local/{kind}/{basename}",
                f"local.{section}.id",
            )
            if asset_id in asset_ids:
                raise SyncError(f"asset.id が重複しています: {asset_id}")
            if any(_paths_overlap(relative, existing) for existing in targets):
                raise SyncError(f"catalog target が重複または重なっています: {relative}")
            location = root.joinpath(*PurePosixPath(relative).parts)
            if not location.exists():
                raise SyncError(
                    f"{LOCAL_ASSETS_REL} の [{section}].{name} に対応する path がありません: "
                    f"{relative}"
                )
            harnesses = _default_asset_harnesses(kind, allowed_harnesses)
            if kind == "skill":
                harnesses = tuple(
                    harness
                    for harness in harnesses
                    if name not in local_skill_excludes.get(harness, frozenset())
                )
            if not harnesses:
                raise SyncError(f"{asset_id} に適用可能な harness がありません")
            assets.append(
                Asset(asset_id, None, kind, relative, relative, harnesses)
            )
            asset_ids.add(asset_id)
            targets.add(relative)
    return assets


def _external_apply_enabled(
    data: Mapping[str, object], external_ids: Iterable[str]
) -> frozenset[str] | None:
    """Parse [external] enable table. None means section absent (all external apply)."""
    table = data.get("external")
    if table is None:
        return None
    enables = _parse_enable_table(table, section="external", known_ids=external_ids)
    return frozenset(asset_id for asset_id, enabled in enables.items() if enabled)


def apply_enabled(config: Config, asset: Asset) -> bool:
    """Whether asset participates in diff/apply (sync always uses all external assets)."""
    if asset.is_local:
        return True
    if config.external_apply_enabled is None:
        return True
    return asset.id in config.external_apply_enabled


def load_config(root: Path) -> Config:
    root = root.resolve()
    data = _read_toml(root / "sources.toml")
    if data.get("schema_version") != 1:
        raise SyncError("sources.toml の schema_version は 1 である必要があります")
    unknown_top = set(data) - {"schema_version", "apply", "sources", "assets"}
    if unknown_top:
        raise SyncError(f"sources.toml に未知のキーがあります: {', '.join(sorted(unknown_top))}")

    apply = data.get("apply", {})
    if not isinstance(apply, dict):
        raise SyncError("[apply] はテーブルである必要があります")
    unknown_apply = set(apply) - {
        "default_kinds",
        "default_harnesses",
        "allowed_harnesses",
        "local_skill_excludes",
    }
    if unknown_apply:
        raise SyncError(f"[apply] に未知のキーがあります: {', '.join(sorted(unknown_apply))}")
    allowed_harnesses = _string_list(
        apply.get("allowed_harnesses", list(HARNESSES)),
        "apply.allowed_harnesses",
        HARNESSES,
    )
    default_kinds = _string_list(
        apply.get("default_kinds", list(KINDS)), "apply.default_kinds", KINDS
    )
    default_harnesses = _string_list(
        apply.get("default_harnesses", ["cursor"]),
        "apply.default_harnesses",
        allowed_harnesses,
    )
    local_skill_excludes = _parse_local_skill_excludes(
        apply.get("local_skill_excludes"),
        root=root,
        allowed_harnesses=allowed_harnesses,
    )

    local = _read_toml(root / "apply.local.toml", optional=True)
    if local:
        if set(local) != {"default_harnesses"}:
            raise SyncError("apply.local.toml では default_harnesses だけを指定できます")
        default_harnesses = _string_list(
            local["default_harnesses"], "apply.local.default_harnesses", allowed_harnesses
        )

    sources: dict[str, Source] = {}
    raw_sources = data.get("sources", [])
    if not isinstance(raw_sources, list):
        raise SyncError("[[sources]] は配列テーブルである必要があります")
    for raw in raw_sources:
        if not isinstance(raw, dict):
            raise SyncError("[[sources]] の要素が不正です")
        required = {"id", "url", "rev", "license"}
        if set(raw) != required:
            raise SyncError(f"source は {', '.join(sorted(required))} だけを指定してください")
        source_id = _safe_id(raw["id"], "source.id")
        if source_id in sources:
            raise SyncError(f"source.id が重複しています: {source_id}")
        if not isinstance(raw["url"], str) or not raw["url"]:
            raise SyncError(f"source.url が不正です: {source_id}")
        if not isinstance(raw["rev"], str) or not OID_RE.fullmatch(raw["rev"]):
            raise SyncError(f"source.rev は完全な commit OID で指定してください: {source_id}")
        if not isinstance(raw["license"], str) or not raw["license"]:
            raise SyncError(f"source.license が不正です: {source_id}")
        sources[source_id] = Source(
            source_id, raw["url"], raw["rev"].lower(), raw["license"]
        )

    assets: list[Asset] = []
    asset_ids: set[str] = set()
    targets: set[str] = set()
    raw_assets = data.get("assets", [])
    if not isinstance(raw_assets, list):
        raise SyncError("[[assets]] は配列テーブルである必要があります")
    for raw in raw_assets:
        if not isinstance(raw, dict):
            raise SyncError("[[assets]] の要素が不正です")
        allowed_keys = {"id", "source", "kind", "path", "target", "harnesses"}
        required = {"id", "kind", "path"}
        if not required <= set(raw) or set(raw) - allowed_keys:
            raise SyncError(f"asset の必須/許可キーが不正です: {raw.get('id', '<unknown>')}")
        asset_id = _safe_id(raw["id"], "asset.id")
        if asset_id in asset_ids:
            raise SyncError(f"asset.id が重複しています: {asset_id}")
        source_id = raw.get("source")
        if source_id is None:
            raise SyncError(
                f"local asset は sources.toml ではなく {LOCAL_ASSETS_REL} で有効化してください: {asset_id}"
            )
        if not isinstance(source_id, str):
            raise SyncError(f"asset.source が不正です: {asset_id}")
        if source_id not in sources:
            raise SyncError(f"asset.source が未定義です: {asset_id}: {source_id}")
        kind = raw["kind"]
        if kind not in KINDS:
            raise SyncError(f"asset.kind が不正です: {asset_id}: {kind}")
        source_path = _safe_rel(raw["path"], f"{asset_id}.path")
        target = _safe_rel(
            raw.get("target", _default_target(kind, source_path)), f"{asset_id}.target"
        )
        expected_root = {"skill": "skills", "agent": "agents", "context": "context"}[kind]
        if PurePosixPath(target).parts[0] != expected_root:
            raise SyncError(f"{asset_id}.target は {expected_root}/ 配下である必要があります")
        if any(_paths_overlap(target, existing) for existing in targets):
            raise SyncError(f"catalog target が重複または重なっています: {target}")
        harnesses = _string_list(
            raw.get("harnesses", list(_default_asset_harnesses(kind, allowed_harnesses))),
            f"{asset_id}.harnesses",
            allowed_harnesses,
        )
        unsupported = set(harnesses) - SUPPORTED[kind]
        if unsupported:
            raise SyncError(
                f"{asset_id} では未対応の kind×harness です: "
                f"{kind}×{','.join(sorted(unsupported))}"
            )
        assets.append(Asset(asset_id, source_id, kind, source_path, target, harnesses))
        asset_ids.add(asset_id)
        targets.add(target)

    local_data = _read_assets_local(root)
    external_ids = tuple(asset.id for asset in assets)
    external_apply_enabled = _external_apply_enabled(local_data, external_ids)
    assets.extend(
        _load_local_assets(
            root,
            local_data,
            allowed_harnesses,
            local_skill_excludes,
            asset_ids=asset_ids,
            targets=targets,
        )
    )

    cache_names: dict[tuple[str, str], str] = {}
    for asset in assets:
        if asset.is_local:
            continue
        cache_name = PurePosixPath(asset.target).name
        key = (asset.source, _path_key(cache_name))
        previous = cache_names.get(key)
        if previous is not None:
            raise SyncError(
                f"cache 名が重複しています: {asset.source}/{cache_name} "
                f"({previous}, {asset.id})"
            )
        cache_names[key] = asset.id

    harness_targets: dict[tuple[str, str], str] = {}
    harness_paths: dict[str, set[str]] = {}
    for asset in assets:
        for harness in asset.harnesses:
            # Pi context shares a single APPEND_SYSTEM.md marker file.
            if harness == "pi" and asset.kind == "context":
                continue
            target = _target_for(asset, harness)
            key = (harness, _path_key(target))
            previous = harness_targets.get(key)
            if previous is not None:
                raise SyncError(
                    f"harness target が重複しています: {harness}:{target} "
                    f"({previous}, {asset.id})"
                )
            paths = harness_paths.setdefault(harness, set())
            if any(_paths_overlap(target, existing) for existing in paths):
                raise SyncError(
                    f"harness target が重複または重なっています: {harness}:{target}"
                )
            if any(
                _path_key(target) != _path_key(catalog) and _paths_overlap(target, catalog)
                for catalog in targets
            ):
                raise SyncError(
                    f"catalog target と harness target が重なっています: {target}"
                )
            harness_targets[key] = asset.id
            paths.add(target)

    return Config(
        root,
        sources,
        tuple(assets),
        default_kinds,
        default_harnesses,
        allowed_harnesses,
        external_apply_enabled,
    )


def load_lock(config: Config, *, required: bool = False) -> dict[str, LockAsset]:
    path = config.root / "sources.lock.toml"
    if not path.exists():
        if required:
            raise SyncError("sources.lock.toml がありません。先に sync を実行してください")
        return {}
    data = _read_toml(path)
    if data.get("schema_version") != 1:
        raise SyncError("sources.lock.toml の schema_version は 1 である必要があります")
    if set(data) - {"schema_version", "assets"}:
        raise SyncError("sources.lock.toml に未知のキーがあります")
    result: dict[str, LockAsset] = {}
    raw_assets = data.get("assets", [])
    if not isinstance(raw_assets, list):
        raise SyncError("sources.lock.toml の [[assets]] が不正です")
    expected = {"id", "source", "rev", "export_hash", "target", "cache", "source_is_file"}
    for raw in raw_assets:
        if not isinstance(raw, dict) or set(raw) != expected:
            raise SyncError("sources.lock.toml の asset entry が不正です")
        if raw["id"] in result:
            raise SyncError(f"lock asset が重複しています: {raw['id']}")
        if not isinstance(raw["source_is_file"], bool):
            raise SyncError(f"lock source_is_file が不正です: {raw['id']}")
        cache = _safe_rel(raw["cache"], f"lock.{raw['id']}.cache")
        target = _safe_rel(raw["target"], f"lock.{raw['id']}.target")
        if not OID_RE.fullmatch(raw["rev"]):
            raise SyncError(f"lock rev が不正です: {raw['id']}")
        if not re.fullmatch(r"[0-9a-f]{64}", raw["export_hash"]):
            raise SyncError(f"lock export_hash が不正です: {raw['id']}")
        result[raw["id"]] = LockAsset(
            raw["id"],
            raw["source"],
            raw["rev"],
            raw["export_hash"],
            target,
            cache,
            raw["source_is_file"],
        )
    return result


def validate(config: Config, lock: Mapping[str, LockAsset]) -> None:
    assets = {asset.id: asset for asset in config.assets}
    for asset in config.assets:
        if not asset.is_local:
            continue
        if asset.id in lock:
            raise SyncError(f"local asset を lock に入れないでください: {asset.id}")
        location = config.root.joinpath(*PurePosixPath(asset.target).parts)
        if not location.exists():
            raise SyncError(f"local asset がありません: {asset.id}: {asset.target}")
    for asset_id, entry in lock.items():
        asset = assets.get(asset_id)
        if asset is None:
            raise SyncError(f"lock に manifest 未定義 asset があります: {asset_id}")
        if asset.is_local or asset.source is None:
            raise SyncError(f"local asset を lock に入れないでください: {asset_id}")
        source = config.sources[asset.source]
        expected_cache = _cache_rel(source, asset)
        if (
            entry.source != asset.source
            or entry.rev != source.rev
            or entry.target != asset.target
            or entry.cache != expected_cache
        ):
            raise SyncError(f"lock が sources.toml と一致しません: {asset_id}")


def _git(args: Sequence[str], cwd: Path | None = None, *, text: bool = True):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=env,
            check=True,
            capture_output=True,
            text=text,
        ).stdout
    except FileNotFoundError as exc:
        raise SyncError("Git が見つかりません") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if isinstance(exc.stderr, str) else exc.stderr.decode(errors="replace")
        raise SyncError(f"git {' '.join(args)} に失敗しました: {stderr}") from exc


def _cache_rel(source: Source, asset: Asset) -> str:
    name = PurePosixPath(asset.target).name
    return f".cache/sources/{source.id}/{source.rev}/{name}"


def _normalize_mode(mode: int) -> int:
    return EXECUTABLE_FILE_MODE if mode & 0o111 else DEFAULT_FILE_MODE


def _mode_from_git(git_mode: str) -> int:
    return EXECUTABLE_FILE_MODE if git_mode == "100755" else DEFAULT_FILE_MODE


def _set_file_mode(path: Path, mode: int) -> None:
    if os.name == "nt":
        return
    path.chmod(_normalize_mode(mode))


def _write_export_meta(destination: Path, modes: Mapping[str, int]) -> None:
    lines = [
        "# Generated by catalog export. Do not edit by hand.",
        "schema_version = 1",
        "",
        "[modes]",
    ]
    for relative, mode in sorted(modes.items()):
        lines.append(f"{_toml_quote(relative)} = {int(mode)}")
    lines.append("")
    (destination / EXPORT_META_REL).write_text(
        "\n".join(lines), encoding="utf-8", newline="\n"
    )


def _read_export_meta(cache: Path) -> dict[str, int] | None:
    meta = cache / EXPORT_META_REL
    if not meta.is_file():
        return None
    data = _read_toml(meta)
    if data.get("schema_version") != 1:
        raise SyncError(f"export metadata の schema_version が不正です: {cache}")
    modes = data.get("modes")
    if not isinstance(modes, dict) or not modes:
        raise SyncError(f"export metadata の modes が不正です: {cache}")
    result: dict[str, int] = {}
    for relative, mode in modes.items():
        if not isinstance(relative, str) or not isinstance(mode, int):
            raise SyncError(f"export metadata の mode が不正です: {cache}")
        result[_safe_rel(relative, "export-meta")] = _normalize_mode(mode)
    return result


def _modes_for_cache(cache: Path) -> dict[str, int]:
    """Prefer Git-derived export metadata; fall back for legacy caches."""
    modes = _read_export_meta(cache)
    if modes is not None:
        return modes
    result: dict[str, int] = {}
    for file in _iter_export_files(cache):
        result[file.relative_to(cache).as_posix()] = _normalize_mode(file.stat().st_mode)
    if not result:
        raise SyncError(f"cache が空です: {cache}")
    return result


def _iter_export_files(path: Path) -> list[Path]:
    files: list[Path] = []
    for item in path.rglob("*"):
        if item.is_symlink():
            raise SyncError(f"cache に symlink があります: {item}")
        if not item.is_file():
            continue
        relative = item.relative_to(path).as_posix()
        if relative == EXPORT_META_REL:
            continue
        files.append(item)
    return files


def _tree_hash(path: Path) -> str:
    modes = _modes_for_cache(path)
    digest = hashlib.sha256()
    files = sorted(_iter_export_files(path), key=lambda p: p.relative_to(path).as_posix())
    seen: set[str] = set()
    for file in files:
        rel = file.relative_to(path).as_posix()
        if rel not in modes:
            raise SyncError(f"export metadata に mode がありません: {rel}")
        seen.add(rel)
        content = file.read_bytes()
        mode = modes[rel]
        encoded = rel.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
        digest.update(mode.to_bytes(4, "big"))
    missing = sorted(set(modes) - seen)
    if missing:
        raise SyncError(f"export metadata に対応する file がありません: {', '.join(missing)}")
    return digest.hexdigest()


def _unique_dir(parent: Path, prefix: str) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=parent))


def _unique_file(parent: Path, prefix: str, suffix: str = "") -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=parent)
    os.close(handle)
    return Path(name)


@contextlib.contextmanager
def _exclusive_sync_lock(root: Path) -> Iterator[None]:
    lock_path = _assert_safe_destination(root, SYNC_LOCK_REL)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\0")
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise SyncError(
                    "別の sync が実行中です。完了を待ってから再実行してください"
                ) from exc
        else:
            import fcntl

            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise SyncError(
                    "別の sync が実行中です。完了を待ってから再実行してください"
                ) from exc
        locked = True
        yield
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                try:
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _export_asset(repo: Path, source: Source, asset: Asset, destination: Path) -> bool:
    # "." (repo root tree) は git の rev:path 構文で "rev:." と解決できないため
    # 空文字に置き換えて root tree を参照する。
    normalized_path = "" if PurePosixPath(asset.path).as_posix() == "." else asset.path
    object_type = _git(["cat-file", "-t", f"{source.rev}:{normalized_path}"], repo).strip()
    if object_type not in ("tree", "blob"):
        raise SyncError(f"asset path は file または directory ではありません: {asset.id}")
    # "." (repo root tree) は path が空文字として index に現れるため特別扱いする。
    root_export = normalized_path == ""
    source_is_file = object_type == "blob" and not root_export
    raw = _git(
        ["ls-files", "-z", "--stage", "--", asset.path], repo, text=False
    )
    entries = raw.split(b"\0")
    files: list[tuple[str, str, int]] = []
    prefix = asset.path.rstrip("/") + "/"
    for entry in entries:
        if not entry:
            continue
        try:
            metadata, encoded_path = entry.split(b"\t", 1)
            mode = metadata.split(b" ", 1)[0].decode()
            tracked_path = encoded_path.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise SyncError(f"git ls-files の出力を解釈できません: {asset.id}") from exc
        if mode == "120000":
            raise SyncError(f"symlink は取り込めません: {tracked_path}")
        if mode not in ("100644", "100755"):
            raise SyncError(f"未対応の Git file mode です: {mode}: {tracked_path}")
        if source_is_file:
            if tracked_path != asset.path:
                continue
            relative = PurePosixPath(tracked_path).name
        elif root_export:
            relative = tracked_path
        else:
            if not tracked_path.startswith(prefix):
                continue
            relative = tracked_path[len(prefix) :]
        relative = _safe_rel(relative, f"{asset.id}.export")
        if relative == EXPORT_META_REL:
            raise SyncError(
                f"upstream に予約名 {EXPORT_META_REL} があります: {asset.id}: {tracked_path}"
            )
        files.append((tracked_path, relative, _mode_from_git(mode)))
    if not files:
        raise SyncError(f"tracked file がありません: {asset.id}: {asset.path}")

    staging = _unique_dir(destination.parent, f".{destination.name}.tmp-")
    modes: dict[str, int] = {}
    try:
        for tracked_path, relative, file_mode in files:
            output = staging.joinpath(*PurePosixPath(relative).parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            content = _git(["show", f"{source.rev}:{tracked_path}"], repo, text=False)
            output.write_bytes(content)
            _set_file_mode(output, file_mode)
            modes[relative] = file_mode
        _write_export_meta(staging, modes)
        if destination.exists():
            _remove_tree(destination)
        staging.replace(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return source_is_file


def _toml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def write_lock(config: Config, entries: Mapping[str, LockAsset]) -> None:
    lines = [
        "# Generated by python -m catalog sync. Do not edit by hand.",
        "schema_version = 1",
        "",
    ]
    order = {asset.id: index for index, asset in enumerate(config.assets)}
    for entry in sorted(entries.values(), key=lambda item: order[item.id]):
        lines.extend(
            [
                "[[assets]]",
                f"id = {_toml_quote(entry.id)}",
                f"source = {_toml_quote(entry.source)}",
                f"rev = {_toml_quote(entry.rev)}",
                f"export_hash = {_toml_quote(entry.export_hash)}",
                f"target = {_toml_quote(entry.target)}",
                f"cache = {_toml_quote(entry.cache)}",
                f"source_is_file = {'true' if entry.source_is_file else 'false'}",
                "",
            ]
        )
    temporary = _unique_file(config.root, "sources.lock.toml.", suffix=".tmp")
    try:
        temporary.write_text("\n".join(lines), encoding="utf-8", newline="\n")
        temporary.replace(config.root / "sources.lock.toml")
    finally:
        if temporary.exists():
            temporary.unlink()


def _cache_sources_root(config: Config) -> Path:
    return _assert_safe_destination(config.root, ".cache/sources")


def _remove_tree(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
        return
    if not path.exists():
        return
    for child in sorted(path.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if child.is_symlink():
            child.unlink()
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _lexical_under(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _clean_cache(config: Config, entries: Mapping[str, LockAsset]) -> None:
    """Remove .cache/sources contents that are not referenced by lock entries."""
    sources_root = _cache_sources_root(config)
    if not sources_root.exists():
        return
    retained: set[str] = set()
    ancestors: set[str] = set()
    for entry in entries.values():
        cache = _assert_safe_destination(config.root, entry.cache)
        try:
            rel = _lexical_under(sources_root, cache)
        except ValueError as exc:
            raise SyncError(f"cache が sources root 外です: {entry.cache}") from exc
        retained.add(rel)
        parts = PurePosixPath(rel).parts
        for index in range(len(parts)):
            ancestors.add(PurePosixPath(*parts[:index]).as_posix() if index else ".")

    # Unlink symlink aliases before any keep/delete decision so resolve() cannot
    # make an alias look like a retained path.
    for path in sorted(sources_root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_symlink():
            print(f"removed cache symlink: {_lexical_under(sources_root, path)}")
            path.unlink()

    def _keep(rel: str) -> bool:
        if rel in retained or rel in ancestors:
            return True
        return any(
            rel == retained_path or rel.startswith(retained_path + "/")
            for retained_path in retained
        )

    for path in sorted(sources_root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.name == ".sync.lock" and path.parent == sources_root:
            continue
        rel = _lexical_under(sources_root, path)
        if _keep(rel):
            continue
        _remove_tree(path)
    if sources_root.exists() and not any(
        item for item in sources_root.iterdir() if item.name != ".sync.lock"
    ):
        # Keep the lock file; leave the directory in place.
        pass


def _path_key(rel: str) -> str:
    """Case-folded posix path key for collision detection on any OS."""
    return "/".join(part.casefold() for part in PurePosixPath(rel).parts)


def _paths_overlap(left: str, right: str) -> bool:
    left_key = _path_key(left)
    right_key = _path_key(right)
    if left_key == right_key:
        return True
    return left_key.startswith(right_key + "/") or right_key.startswith(left_key + "/")


def _local_catalog_targets(config: Config) -> set[str]:
    return {asset.target for asset in config.assets if asset.is_local}


@dataclasses.dataclass(frozen=True)
class _QuarantineMove:
    original: Path
    quarantined: Path


def _catalog_copy_candidates(
    config: Config, entries: Mapping[str, LockAsset]
) -> list[str]:
    local_targets = _local_catalog_targets(config)
    candidates: list[str] = []
    for entry in entries.values():
        if entry.target in local_targets or any(
            _paths_overlap(entry.target, local) for local in local_targets
        ):
            continue
        destination = _assert_safe_destination(config.root, entry.target)
        if destination.exists() or destination.is_symlink():
            candidates.append(entry.target)
    return candidates


def _stale_catalog_targets(
    config: Config,
    old_lock: Mapping[str, LockAsset],
    new_lock: Mapping[str, LockAsset],
) -> list[str]:
    current_targets = {entry.target for entry in new_lock.values()} | {
        asset.target for asset in config.assets
    }
    stale_targets: set[str] = set()
    for asset_id in set(old_lock) - set(new_lock):
        stale_targets.add(old_lock[asset_id].target)
    for asset_id in set(old_lock) & set(new_lock):
        old_target = old_lock[asset_id].target
        new_target = new_lock[asset_id].target
        if old_target != new_target:
            stale_targets.add(old_target)
    return sorted(
        target
        for target in stale_targets
        if not any(_paths_overlap(target, current) for current in current_targets)
        and target not in _local_catalog_targets(config)
        and not any(
            _paths_overlap(target, local) for local in _local_catalog_targets(config)
        )
    )


def _unlink_cache_symlinks(config: Config) -> None:
    sources_root = _cache_sources_root(config)
    if not sources_root.exists():
        return
    for path in sorted(sources_root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_symlink():
            print(f"removed cache symlink: {_lexical_under(sources_root, path)}")
            path.unlink()


def _obsolete_cache_paths(
    config: Config,
    entries: Mapping[str, LockAsset],
    retain_paths: Sequence[Path] = (),
) -> list[Path]:
    sources_root = _cache_sources_root(config)
    if not sources_root.exists():
        return []
    retained: set[str] = set()
    ancestors: set[str] = set()

    def _retain(rel: str) -> None:
        retained.add(rel)
        parts = PurePosixPath(rel).parts
        for index in range(len(parts)):
            ancestors.add(PurePosixPath(*parts[:index]).as_posix() if index else ".")

    for entry in entries.values():
        cache = _assert_safe_destination(config.root, entry.cache)
        try:
            rel = _lexical_under(sources_root, cache)
        except ValueError as exc:
            raise SyncError(f"cache が sources root 外です: {entry.cache}") from exc
        _retain(rel)
    for path in retain_paths:
        try:
            _retain(_lexical_under(sources_root, path))
        except ValueError:
            continue

    def _keep(rel: str) -> bool:
        if rel in retained or rel in ancestors:
            return True
        return any(
            rel == retained_path or rel.startswith(retained_path + "/")
            for retained_path in retained
        )

    obsolete: list[Path] = []
    for path in sorted(sources_root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.name == ".sync.lock" and path.parent == sources_root:
            continue
        rel = _lexical_under(sources_root, path)
        if _keep(rel):
            continue
        obsolete.append(path)
    return obsolete


def _quarantine_path(
    config: Config, quarantine_root: Path, relative: str
) -> _QuarantineMove | None:
    destination = _assert_safe_destination(config.root, relative)
    if not destination.exists() and not destination.is_symlink():
        return None
    quarantined = quarantine_root.joinpath(*PurePosixPath(relative).parts)
    quarantined.parent.mkdir(parents=True, exist_ok=True)
    destination.replace(quarantined)
    return _QuarantineMove(destination, quarantined)


def _quarantine_tree(path: Path, quarantine_root: Path, label: str) -> _QuarantineMove | None:
    if not path.exists() and not path.is_symlink():
        return None
    quarantined = quarantine_root / label
    if quarantined.exists() or quarantined.is_symlink():
        _remove_tree(quarantined)
    quarantined.parent.mkdir(parents=True, exist_ok=True)
    path.replace(quarantined)
    return _QuarantineMove(path, quarantined)


def _restore_quarantine_moves(moves: Sequence[_QuarantineMove]) -> None:
    for move in reversed(moves):
        if move.quarantined.exists() or move.quarantined.is_symlink():
            if move.original.exists() or move.original.is_symlink():
                _remove_tree(move.original)
            move.original.parent.mkdir(parents=True, exist_ok=True)
            move.quarantined.replace(move.original)


def _quarantine_sync_cleanup(
    config: Config,
    old_lock: Mapping[str, LockAsset],
    final_entries: Mapping[str, LockAsset],
    retain_paths: Sequence[Path] = (),
) -> tuple[Path, list[_QuarantineMove]]:
    quarantine_root = _unique_dir(_assert_safe_destination(config.root, ".cache"), "quarantine-")
    moves: list[_QuarantineMove] = []
    for target in _catalog_copy_candidates(config, final_entries):
        move = _quarantine_path(config, quarantine_root, target)
        if move is not None:
            moves.append(move)
            print(f"quarantined external catalog copy: {target}")
    for target in _stale_catalog_targets(config, old_lock, final_entries):
        move = _quarantine_path(config, quarantine_root, target)
        if move is not None:
            moves.append(move)
            print(f"quarantined stale catalog target: {target}")
    _unlink_cache_symlinks(config)
    for index, path in enumerate(
        _obsolete_cache_paths(config, final_entries, retain_paths)
    ):
        move = _quarantine_tree(path, quarantine_root, f"cache-{index}")
        if move is not None:
            moves.append(move)
            try:
                rel = _lexical_under(_cache_sources_root(config), path)
            except ValueError:
                rel = path.name
            print(f"quarantined obsolete cache: {rel}")
    return quarantine_root, moves


def _finalize_sync_quarantine(quarantine_root: Path | None) -> None:
    if quarantine_root is not None and quarantine_root.exists():
        _remove_tree(quarantine_root)


def _remove_catalog_target_if_present(config: Config, target: str, *, reason: str) -> None:
    local_targets = _local_catalog_targets(config)
    if target in local_targets or any(
        _paths_overlap(target, local) for local in local_targets
    ):
        return
    destination = _assert_safe_destination(config.root, target)
    if destination.exists() or destination.is_symlink():
        _remove_tree(destination)
        print(f"{reason}: {target}")


def _prune_external_catalog_copies(
    config: Config, entries: Mapping[str, LockAsset]
) -> None:
    """Remove any git-tree copies of external assets (source of truth is cache only)."""
    for entry in entries.values():
        _remove_catalog_target_if_present(
            config, entry.target, reason="removed external catalog copy"
        )


def _prune_removed_catalog_targets(
    config: Config,
    old_lock: Mapping[str, LockAsset],
    new_lock: Mapping[str, LockAsset],
) -> None:
    current_targets = {entry.target for entry in new_lock.values()} | {
        asset.target for asset in config.assets
    }
    stale_targets: set[str] = set()
    for asset_id in set(old_lock) - set(new_lock):
        stale_targets.add(old_lock[asset_id].target)
    for asset_id in set(old_lock) & set(new_lock):
        old_target = old_lock[asset_id].target
        new_target = new_lock[asset_id].target
        if old_target != new_target:
            stale_targets.add(old_target)
    for target in sorted(stale_targets):
        if any(_paths_overlap(target, current) for current in current_targets):
            continue
        _remove_catalog_target_if_present(
            config, target, reason="removed stale catalog target"
        )


def _lock_entry_matches_manifest(config: Config, entry: LockAsset) -> bool:
    assets = {asset.id: asset for asset in config.assets}
    asset = assets.get(entry.id)
    if asset is None or asset.is_local or asset.source is None:
        return False
    source = config.sources[asset.source]
    return (
        entry.source == asset.source
        and entry.rev == source.rev
        and entry.target == asset.target
        and entry.cache == _cache_rel(source, asset)
    )


def _select_sync_assets(
    config: Config,
    requested: frozenset[str] | None,
    old_lock: Mapping[str, LockAsset],
) -> list[Asset]:
    selected = [
        asset
        for asset in config.assets
        if not asset.is_local and (requested is None or asset.id in requested)
    ]
    if requested is None:
        return selected

    known = {asset.id for asset in config.assets}
    unknown = sorted(requested - known)
    if unknown:
        raise SyncError(f"未知の asset です: {', '.join(unknown)}")
    for asset in config.assets:
        if asset.is_local and asset.id in requested:
            print(f"skip local asset (no sync): {asset.id}")
    if not selected:
        incompatible = sorted(
            asset_id
            for asset_id, entry in old_lock.items()
            if not _lock_entry_matches_manifest(config, entry)
        )
        if incompatible:
            touched_sources: set[str] = set()
            for asset_id in incompatible:
                asset = next((item for item in config.assets if item.id == asset_id), None)
                if asset is not None and asset.source is not None:
                    touched_sources.add(asset.source)
            if touched_sources:
                expanded = [
                    asset
                    for asset in config.assets
                    if not asset.is_local and asset.source in touched_sources
                ]
                pulled_in = sorted(asset.id for asset in expanded)
                print(
                    "also syncing assets sharing source or changed pin: "
                    + ", ".join(pulled_in)
                )
                return expanded
            raise SyncError(
                "partial sync では未更新の lock が manifest と不一致です: "
                + ", ".join(incompatible)
            )
        return []

    touched_sources = {asset.source for asset in selected if asset.source is not None}
    # Expand to every source whose pin/target no longer matches the lock so a
    # partial sync cannot leave incompatible untouched entries behind.
    for asset in config.assets:
        if asset.is_local or asset.source is None:
            continue
        entry = old_lock.get(asset.id)
        if entry is None:
            continue
        if not _lock_entry_matches_manifest(config, entry):
            touched_sources.add(asset.source)

    expanded = [
        asset
        for asset in config.assets
        if not asset.is_local and asset.source in touched_sources
    ]
    requested_ids = {asset.id for asset in selected}
    pulled_in = [asset.id for asset in expanded if asset.id not in requested_ids]
    if pulled_in:
        print("also syncing assets sharing source or changed pin: " + ", ".join(pulled_in))
    return expanded


def _promote_path(source: Path, destination: Path) -> Path | None:
    """Replace destination with source. Return a backup path if destination existed."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if destination.exists() or destination.is_symlink():
        backup = _unique_dir(destination.parent, f".{destination.name}.bak-")
        # Move existing destination aside into the backup directory.
        moved = backup / destination.name
        destination.replace(moved)
    try:
        source.replace(destination)
    except Exception:
        _restore_backup(backup, destination)
        raise
    return backup


def _restore_backup(backup: Path | None, destination: Path) -> None:
    if backup is None:
        if destination.exists() or destination.is_symlink():
            _remove_tree(destination)
        return
    moved = backup / destination.name
    if destination.exists() or destination.is_symlink():
        _remove_tree(destination)
    if moved.exists() or moved.is_symlink():
        moved.replace(destination)
    _remove_tree(backup)


def sync_assets(config: Config, requested: frozenset[str] | None) -> int:
    with _exclusive_sync_lock(config.root):
        return _sync_assets_locked(config, requested)


def _sync_assets_locked(config: Config, requested: frozenset[str] | None) -> int:
    old_lock = load_lock(config)
    selected = _select_sync_assets(config, requested, old_lock)
    if requested is not None and not selected:
        return 0

    # Full sync rebuilds the lock from scratch; partial sync updates in place.
    entries: dict[str, LockAsset] = {} if requested is None else dict(old_lock)

    staged: list[tuple[Path, Path]] = []  # (staging, final)
    promoted: list[tuple[Path, Path | None]] = []  # (final, backup)
    quarantine_root: Path | None = None
    quarantine_moves: list[_QuarantineMove] = []
    lock_backup: Path | None = None
    lock_created = False
    committed = False
    try:
        with tempfile.TemporaryDirectory(prefix="external-skill-sync-") as temp:
            temp_root = Path(temp)
            repos: dict[str, Path] = {}
            for asset in selected:
                source = config.sources[asset.source]
                repo = repos.get(source.id)
                if repo is None:
                    repo = temp_root / hashlib.sha256(source.id.encode()).hexdigest()[:16]
                    _git(["clone", "--no-checkout", "--quiet", source.url, str(repo)])
                    resolved = (
                        _git(["rev-parse", f"{source.rev}^{{commit}}"], repo).strip().lower()
                    )
                    if resolved != source.rev:
                        raise SyncError(f"pin が指定 commit と一致しません: {source.id}")
                    # Populate only the index so git ls-files can define the export
                    # allowlist without checking untracked or worktree content out.
                    _git(["read-tree", source.rev], repo)
                    repos[source.id] = repo
                cache_rel = _cache_rel(source, asset)
                final_cache = _assert_safe_destination(config.root, cache_rel)
                staging_parent = final_cache.parent
                staging_cache = _unique_dir(
                    staging_parent if staging_parent.exists() else _cache_sources_root(config),
                    f".{final_cache.name}.staging-",
                )
                # _export_asset replaces destination; export directly into the unique staging dir
                # by exporting into a child then swapping — keep API: export into staging_cache.
                # Clear the empty mkdtemp dir and let export recreate via unique child, or export
                # into staging_cache by passing it as destination after removing it.
                shutil.rmtree(staging_cache)
                source_is_file = _export_asset(repo, source, asset, staging_cache)
                staged.append((staging_cache, final_cache))
                entries[asset.id] = LockAsset(
                    asset.id,
                    source.id,
                    source.rev,
                    _tree_hash(staging_cache),
                    asset.target,
                    cache_rel,
                    source_is_file,
                )
                print(f"synced {asset.id} @ {source.rev[:12]}")

        active_ids = {asset.id for asset in config.assets}
        final_entries = {key: value for key, value in entries.items() if key in active_ids}

        if requested is not None:
            incompatible = sorted(
                asset_id
                for asset_id, entry in final_entries.items()
                if asset_id not in {asset.id for asset in selected}
                and not _lock_entry_matches_manifest(config, entry)
            )
            if incompatible:
                raise SyncError(
                    "partial sync では未更新の lock が manifest と不一致です: "
                    + ", ".join(incompatible)
                )

        # Promote caches, quarantine stale paths, then write lock. External assets
        # stay in .cache only — never materialize into the git-tracked tree.
        for staging_cache, final_cache in staged:
            backup = _promote_path(staging_cache, final_cache)
            promoted.append((final_cache, backup))
        staged.clear()

        quarantine_root, quarantine_moves = _quarantine_sync_cleanup(
            config,
            old_lock,
            final_entries,
            retain_paths=tuple(
                backup for _final, backup in promoted if backup is not None
            ),
        )

        lock_path = config.root / "sources.lock.toml"
        lock_created = not lock_path.exists()
        if not lock_created:
            lock_backup = _unique_file(config.root, "sources.lock.toml.bak.")
            shutil.copy2(lock_path, lock_backup)
        write_lock(config, final_entries)
        committed = True

        try:
            _finalize_sync_quarantine(quarantine_root)
            quarantine_root = None
            for _final, backup in promoted:
                if backup is not None and backup.exists():
                    _remove_tree(backup)
            if lock_backup is not None and lock_backup.exists():
                lock_backup.unlink()
                lock_backup = None
        except Exception:
            pass
        return 0
    except Exception:
        if not committed:
            # Restore quarantine first so promote backups are back under .cache/sources.
            _restore_quarantine_moves(quarantine_moves)
            if quarantine_root is not None and quarantine_root.exists():
                _remove_tree(quarantine_root)
            for final_cache, backup in reversed(promoted):
                _restore_backup(backup, final_cache)
            lock_path = config.root / "sources.lock.toml"
            if lock_created:
                if lock_path.exists():
                    lock_path.unlink()
            elif lock_backup is not None and lock_backup.exists():
                if lock_path.exists():
                    lock_path.unlink()
                lock_backup.replace(lock_path)
        raise
    finally:
        for staging_cache, _final in staged:
            if staging_cache.exists():
                _remove_tree(staging_cache)


def _parse_selection(raw: str | None, default: tuple[str, ...], allowed: Iterable[str], label: str) -> tuple[str, ...]:
    if raw is None:
        return default
    values = tuple(dict.fromkeys(part.strip() for part in raw.split(",") if part.strip()))
    if not values:
        raise SyncError(f"--{label} に値がありません")
    unknown = set(values) - set(allowed)
    if unknown:
        raise SyncError(f"未知の {label} です: {', '.join(sorted(unknown))}")
    return values


def _selected_assets(config: Config, kinds: tuple[str, ...]) -> tuple[Asset, ...]:
    return tuple(
        asset
        for asset in config.assets
        if asset.kind in kinds and apply_enabled(config, asset)
    )


def _user_home() -> Path:
    override = os.environ.get("CATALOG_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home().resolve()


def _harness_root(harness: str) -> Path:
    home = _user_home()
    if harness == "cursor":
        return home / ".cursor"
    if harness == "opencode":
        return home / ".config" / "opencode"
    if harness == "omp":
        return home / ".omp"
    if harness == "pi":
        return home / ".pi" / "agent"
    if harness == "shared":
        return home / ".agents"
    if harness == "hermes":
        return home / ".hermes"
    raise SyncError(f"未知の harness です: {harness}")


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    home = _user_home()
    try:
        relative = resolved.relative_to(home)
        return f"~/{relative.as_posix()}"
    except ValueError:
        return resolved.as_posix()


def _target_for(asset: Asset, harness: str) -> str:
    catalog_name = PurePosixPath(asset.target).name
    stem = PurePosixPath(catalog_name).stem
    if asset.kind == "skill":
        if harness == "hermes":
            return f"skills/anago/{catalog_name}"
        return f"skills/{catalog_name}"
    if asset.kind == "agent":
        return f"agents/{catalog_name}"
    if harness == "cursor":
        return f"rules/{stem}.mdc"
    if harness in ("opencode", "omp"):
        return f"rules/{catalog_name}"
    if harness == "pi":
        return PI_APPEND_REL
    raise SyncError(f"未対応の kind×harness です: {asset.kind}×{harness}")


def _cache_files(config: Config, entry: LockAsset) -> FileTree:
    cache = _assert_safe_destination(config.root, entry.cache)
    if not cache.is_dir():
        raise SyncError(f"cache がありません。sync を実行してください: {entry.id}")
    if _tree_hash(cache) != entry.export_hash:
        raise SyncError(f"cache hash が lock と一致しません: {entry.id}")
    modes = _modes_for_cache(cache)
    result: FileTree = {}
    for file in _iter_export_files(cache):
        relative = file.relative_to(cache).as_posix()
        result[relative] = (file.read_bytes(), modes[relative])
    return result


def _local_files(config: Config, asset: Asset) -> tuple[bool, FileTree]:
    location = config.root.joinpath(*PurePosixPath(asset.target).parts)
    if not location.exists():
        raise SyncError(f"local asset がありません: {asset.id}: {asset.target}")
    if location.is_symlink():
        raise SyncError(f"local asset の symlink は拒否しました: {asset.id}")
    if location.is_file():
        return True, {
            location.name: (
                location.read_bytes(),
                _normalize_mode(location.stat().st_mode),
            )
        }
    if not location.is_dir():
        raise SyncError(f"local asset が不正です: {asset.id}: {asset.target}")
    result: FileTree = {}
    for file in location.rglob("*"):
        if file.is_symlink():
            raise SyncError(f"local asset に symlink があります: {file}")
        if file.is_file():
            result[file.relative_to(location).as_posix()] = (
                file.read_bytes(),
                _normalize_mode(file.stat().st_mode),
            )
    if not result:
        raise SyncError(f"local asset が空です: {asset.id}")
    return False, result


def _asset_files(
    config: Config, asset: Asset, lock: Mapping[str, LockAsset]
) -> tuple[bool, FileTree]:
    if asset.is_local:
        return _local_files(config, asset)
    entry = lock.get(asset.id)
    if entry is None:
        raise SyncError(f"asset が未同期です: {asset.id}")
    return entry.source_is_file, _cache_files(config, entry)


def _cursor_context(asset: Asset, content: bytes) -> bytes:
    try:
        body = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SyncError(f"Cursor context は UTF-8 である必要があります: {asset.id}") from exc
    frontmatter = (
        "---\n"
        f"description: Synced external context ({asset.id})\n"
        "alwaysApply: true\n"
        "---\n\n"
    )
    return (frontmatter + body).encode("utf-8")


def _expected_tree(
    config: Config,
    asset: Asset,
    source_is_file: bool,
    files: FileTree,
    harness: str,
) -> tuple[str, FileTree]:
    target = _target_for(asset, harness)
    if source_is_file:
        if len(files) != 1:
            raise SyncError(f"file asset の内容が不正です: {asset.id}")
        relative, (content, mode) = next(iter(files.items()))
        if asset.kind == "skill":
            return target, {f"{target}/{relative}": (content, mode)}
        if harness == "cursor" and asset.kind == "context":
            content = _cursor_context(asset, content)
        return target, {target: (content, mode)}
    if asset.kind != "skill":
        raise SyncError(f"agent/context asset は単一 file である必要があります: {asset.id}")
    return target, {
        f"{target}/{relative}": (content, mode) for relative, (content, mode) in files.items()
    }


def _assert_safe_destination(root: Path, relative: str) -> Path:
    relative = _safe_rel(relative, "destination")
    destination = root.joinpath(*PurePosixPath(relative).parts)
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise SyncError(f"出力先の symlink は拒否しました: {current}")
    try:
        destination.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise SyncError(f"出力先が root 外です: {relative}") from exc
    return destination


def _apply_tree(
    base_root: Path,
    managed_root: str,
    expected: FileTree,
    *,
    label: str,
) -> None:
    destination = _assert_safe_destination(base_root, managed_root)
    if destination.exists():
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    for relative, (content, mode) in expected.items():
        output = _assert_safe_destination(base_root, relative)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
        _set_file_mode(output, mode)
    print(f"applied {label} -> {_display_path(destination)}")


def _actual_tree(root: Path, managed_root: str) -> FileTree:
    target = _assert_safe_destination(root, managed_root)
    if not target.exists():
        return {}
    if target.is_file():
        return {
            managed_root: (
                target.read_bytes(),
                _normalize_mode(target.stat().st_mode),
            )
        }
    result: FileTree = {}
    for file in target.rglob("*"):
        if file.is_symlink():
            raise SyncError(f"出力先の symlink は拒否しました: {file}")
        if file.is_file():
            result[file.relative_to(root).as_posix()] = (
                file.read_bytes(),
                _normalize_mode(file.stat().st_mode),
            )
    return result


def _diff_tree(actual: FileTree, expected: FileTree) -> list[str]:
    lines: list[str] = []
    for path in sorted(set(actual) | set(expected)):
        if path not in actual:
            lines.append(f"+ {path}")
        elif path not in expected:
            lines.append(f"- {path}")
        elif actual[path] != expected[path]:
            lines.append(f"~ {path}")
            try:
                before = actual[path][0].decode("utf-8").splitlines()
                after = expected[path][0].decode("utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            lines.extend(
                "  " + line
                for line in difflib.unified_diff(before, after, fromfile=path, tofile=path, lineterm="")
            )
    return lines


_DIFF_OP_RE = re.compile(r"\] ([+\-~]) ")
_ANSI_RESET = "\033[0m"
_ANSI_BOLD = "\033[1m"
_ANSI_GREEN = "\033[32m"
_ANSI_YELLOW = "\033[33m"
_ANSI_RED = "\033[31m"
_DIFF_OP_COLOR = {"+": _ANSI_GREEN, "~": _ANSI_YELLOW, "-": _ANSI_RED}


def _diff_line_op(line: str) -> str | None:
    """Return '+', '~', or '-' for a plan_changes file op line; else None."""
    match = _DIFF_OP_RE.search(line)
    return match.group(1) if match else None


def _diff_summary_line(lines: Sequence[str]) -> str | None:
    counts = {"+": 0, "~": 0, "-": 0}
    for line in lines:
        op = _diff_line_op(line)
        if op is not None:
            counts[op] += 1
    if not any(counts.values()):
        return None
    return f"summary: +{counts['+']}  ~{counts['~']}  -{counts['-']}"


def _color_enabled_for_stdout() -> bool:
    if os.environ.get("NO_COLOR", ""):
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    return sys.stdout.isatty()


def _colorize_diff_line(line: str) -> str:
    if line.startswith("summary:"):
        colored = line
        for op, color in _DIFF_OP_COLOR.items():
            colored = colored.replace(f" {op}", f" {color}{op}{_ANSI_RESET}", 1)
        # First token "summary:" stays bold for scanability.
        if colored.startswith("summary:"):
            colored = f"{_ANSI_BOLD}summary:{_ANSI_RESET}" + colored[len("summary:") :]
        return colored
    op = _diff_line_op(line)
    if op is None:
        return line
    return f"{_DIFF_OP_COLOR[op]}{line}{_ANSI_RESET}"


def render_diff_output(lines: Sequence[str], *, color: bool) -> str:
    """Format plan_changes lines for display: optional summary + optional ANSI color."""
    if not lines:
        return "no changes\n"
    body = list(lines)
    summary = _diff_summary_line(body)
    rendered = ([summary] if summary else []) + body
    if color:
        rendered = [_colorize_diff_line(line) for line in rendered]
    return "\n".join(rendered) + "\n"


_PI_MARKER_RE = re.compile(
    r"<!-- external-skill-sync:([^:\s]+):begin -->.*?<!-- external-skill-sync:\1:end -->",
    re.DOTALL,
)


def _pi_content(
    root: Path,
    updates: Sequence[tuple[Asset, bytes]],
    *,
    known_ids: frozenset[str] | None = None,
) -> tuple[bytes, bytes, bool]:
    path = _assert_safe_destination(root, PI_APPEND_REL)
    exists = path.exists()
    original = path.read_bytes() if exists else b""
    try:
        text = original.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SyncError(f"{PI_APPEND_REL} は UTF-8 である必要があります") from exc
    for asset, content in updates:
        begin = PI_BEGIN.format(asset=asset.id)
        end = PI_END.format(asset=asset.id)
        if text.count(begin) != text.count(end) or text.count(begin) > 1:
            raise SyncError(f"Pi marker が衝突または破損しています: {asset.id}")
        try:
            body = content.decode("utf-8").rstrip()
        except UnicodeDecodeError as exc:
            raise SyncError(f"Pi context は UTF-8 である必要があります: {asset.id}") from exc
        block = f"{begin}\n{body}\n{end}"
        pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
        if pattern.search(text):
            text = pattern.sub(lambda _match: block, text)
        else:
            text = text.rstrip() + ("\n\n" if text.strip() else "") + block + "\n"
    if known_ids is not None:
        def _keep_or_strip(match: re.Match[str]) -> str:
            return match.group(0) if match.group(1) in known_ids else ""

        stripped = _PI_MARKER_RE.sub(_keep_or_strip, text)
        if stripped != text:
            text = re.sub(r"\n{3,}", "\n\n", stripped).rstrip()
            if text:
                text += "\n"
    return original, text.encode("utf-8"), exists


def plan_changes(
    config: Config,
    lock: Mapping[str, LockAsset],
    kinds: tuple[str, ...],
    harnesses: tuple[str, ...],
) -> tuple[
    list[str],
    list[tuple[str, Path, str, FileTree]],
    tuple[Path, bytes, bytes] | None,
    dict[str, tuple[AppliedOutput, ...]],
]:
    unsupported = [
        f"{kind}×{harness}"
        for kind in kinds
        for harness in harnesses
        if harness not in SUPPORTED[kind]
    ]
    if unsupported:
        raise SyncError(f"未対応の kind×harness です: {', '.join(unsupported)}")
    operations: list[tuple[str, Path, str, FileTree]] = []
    lines: list[str] = []
    pi_updates: list[tuple[Asset, bytes]] = []
    expected_applied: dict[str, list[AppliedOutput]] = {harness: [] for harness in harnesses}
    for asset in _selected_assets(config, kinds):
        source_is_file, files = _asset_files(config, asset, lock)
        for harness in harnesses:
            if harness not in asset.harnesses:
                continue
            if harness == "pi" and asset.kind == "context":
                if not source_is_file or len(files) != 1:
                    raise SyncError(f"Pi context は単一 file である必要があります: {asset.id}")
                pi_updates.append((asset, next(iter(files.values()))[0]))
                continue
            base_root = _harness_root(harness)
            managed_root, expected = _expected_tree(
                config, asset, source_is_file, files, harness
            )
            expected_applied[harness].append(
                AppliedOutput(asset.id, managed_root, asset.kind)
            )
            actual = _actual_tree(base_root, managed_root)
            asset_lines = _diff_tree(actual, expected)
            lines.extend(f"[{asset.id} → {harness}] {line}" for line in asset_lines)
            if asset_lines:
                operations.append((asset.id, base_root, managed_root, expected))
    for harness in harnesses:
        base_root = _harness_root(harness)
        previous = _load_applied_manifest(base_root)
        expected_roots = {item.root for item in expected_applied[harness]}
        # Only consider previously managed outputs that are in the selected kind scope.
        scoped_previous = [item for item in previous if item.kind in kinds]
        for item in scoped_previous:
            if item.root in expected_roots:
                continue
            # Skip Pi context markers — handled via known_ids stripping.
            if harness == "pi" and item.kind == "context":
                continue
            actual = _actual_tree(base_root, item.root)
            destination = _assert_safe_destination(base_root, item.root)
            if not actual and not destination.exists() and not destination.is_symlink():
                continue
            asset_lines = _diff_tree(actual, {})
            lines.extend(
                f"[{item.asset_id} → {harness} remove] {line}" for line in asset_lines
            )
            operations.append((item.asset_id, base_root, item.root, {}))
    pi_change = None
    if "pi" in harnesses and "context" in kinds:
        known_context_ids = frozenset(
            asset.id
            for asset in config.assets
            if asset.kind == "context"
            and "pi" in asset.harnesses
            and apply_enabled(config, asset)
        )
        pi_root = _harness_root("pi")
        original, expected, exists = _pi_content(
            pi_root, pi_updates, known_ids=known_context_ids
        )
        actual_pi = (
            {PI_APPEND_REL: (original, DEFAULT_FILE_MODE)} if exists else {}
        )
        expected_pi = (
            {PI_APPEND_REL: (expected, DEFAULT_FILE_MODE)}
            if expected or exists
            else {}
        )
        pi_lines = _diff_tree(actual_pi, expected_pi)
        lines.extend(f"[pi] {line}" for line in pi_lines)
        if pi_lines:
            pi_change = (pi_root, original, expected)
    applied_update = {
        harness: tuple(expected_applied[harness]) for harness in harnesses
    }
    return lines, operations, pi_change, applied_update


def apply_changes(
    config: Config,
    operations: Sequence[tuple[str, Path, str, FileTree]],
    pi_change: tuple[Path, bytes, bytes] | None,
    applied_update: Mapping[str, tuple[AppliedOutput, ...]] | None = None,
    kinds: tuple[str, ...] | None = None,
) -> int:
    for asset_id, base_root, managed_root, expected in operations:
        _apply_tree(base_root, managed_root, expected, label=asset_id)
    if pi_change is not None:
        base_root, original, expected = pi_change
        if original != expected:
            path = _assert_safe_destination(base_root, PI_APPEND_REL)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
            print(f"applied context -> {_display_path(path)}")
    if applied_update is not None:
        kind_scope = frozenset(kinds or KINDS)
        for harness, outputs in applied_update.items():
            base_root = _harness_root(harness)
            previous = _load_applied_manifest(base_root)
            retained = tuple(
                item for item in previous if item.kind not in kind_scope
            )
            _write_applied_manifest(base_root, retained + tuple(outputs))
    return 0


def _load_applied_manifest(harness_root: Path) -> tuple[AppliedOutput, ...]:
    path = harness_root / APPLIED_MANIFEST_REL
    if not path.exists():
        return ()
    data = _read_toml(path)
    if data.get("schema_version") != 1:
        raise SyncError(f"applied manifest の schema_version が不正です: {path}")
    raw_outputs = data.get("outputs", [])
    if not isinstance(raw_outputs, list):
        raise SyncError(f"applied manifest の outputs が不正です: {path}")
    result: list[AppliedOutput] = []
    for raw in raw_outputs:
        if not isinstance(raw, dict):
            raise SyncError(f"applied manifest の entry が不正です: {path}")
        required = {"asset_id", "root", "kind"}
        if set(raw) != required:
            raise SyncError(f"applied manifest の entry キーが不正です: {path}")
        kind = raw["kind"]
        if kind not in KINDS:
            raise SyncError(f"applied manifest の kind が不正です: {kind}")
        result.append(
            AppliedOutput(
                _safe_id(raw["asset_id"], "applied.asset_id"),
                _safe_rel(raw["root"], "applied.root"),
                kind,
            )
        )
    return tuple(result)


def _write_applied_manifest(
    harness_root: Path, outputs: Sequence[AppliedOutput]
) -> None:
    harness_root.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Generated by python -m catalog apply. Do not edit by hand.",
        "schema_version = 1",
        "",
    ]
    for item in sorted(outputs, key=lambda entry: (entry.kind, entry.asset_id, entry.root)):
        lines.extend(
            [
                "[[outputs]]",
                f"asset_id = {_toml_quote(item.asset_id)}",
                f"root = {_toml_quote(item.root)}",
                f"kind = {_toml_quote(item.kind)}",
                "",
            ]
        )
    temporary = _unique_file(harness_root, ".catalog-applied.", suffix=".tmp")
    try:
        temporary.write_text("\n".join(lines), encoding="utf-8", newline="\n")
        temporary.replace(harness_root / APPLIED_MANIFEST_REL)
    finally:
        if temporary.exists():
            temporary.unlink()


def _remote_head(source: Source) -> str:
    output = _git(["ls-remote", source.url, "HEAD"]).strip()
    if not output:
        raise SyncError(f"remote HEAD を取得できません: {source.id}")
    tip = output.split()[0].lower()
    if not OID_RE.fullmatch(tip):
        raise SyncError(f"remote HEAD が不正です: {source.id}: {tip}")
    return tip


def _parse_simple_toml_string_line(line: str, key: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    match = re.fullmatch(
        rf'{re.escape(key)}\s*=\s*(?:"([^"]*)"|\'([^\']*)\')\s*(?:#.*)?',
        stripped,
    )
    if not match:
        return None
    return match.group(1) if match.group(1) is not None else match.group(2)


def _replace_simple_toml_string_line(line: str, key: str, new_value: str) -> str:
    match = re.fullmatch(
        rf'(\s*{re.escape(key)}\s*=\s*)(?:"([^"]*)"|\'([^\']*)\')(\s*(?:#.*)?)?',
        line.rstrip("\r\n"),
    )
    if not match:
        raise SyncError(f"sources.toml の {key} 行を更新できません")
    quote = '"' if match.group(2) is not None else "'"
    suffix = match.group(4) or ""
    return f"{match.group(1)}{quote}{new_value}{quote}{suffix}"


def _rewrite_source_revs(
    text: str,
    expected_old: Mapping[str, str],
    new_revs: Mapping[str, str],
) -> str:
    if set(expected_old) != set(new_revs):
        raise SyncError("internal: expected_old と new_revs のキーが一致しません")
    normalized_new = {source_id: rev.lower() for source_id, rev in new_revs.items()}
    for source_id, rev in normalized_new.items():
        if not OID_RE.fullmatch(rev):
            raise SyncError(
                f"source.rev は完全な commit OID で指定してください: {source_id}"
            )
        if expected_old[source_id].lower() == rev:
            raise SyncError(f"source.rev が更新前後で同じです: {source_id}")

    lines = text.split("\n")
    pending = set(normalized_new)
    seen: set[str] = set()
    index = 0
    while index < len(lines):
        if lines[index].strip() != "[[sources]]":
            index += 1
            continue
        index += 1
        rev_idx: int | None = None
        source_id: str | None = None
        current_rev: str | None = None
        while index < len(lines):
            stripped = lines[index].strip()
            if stripped.startswith("["):
                break
            parsed_id = _parse_simple_toml_string_line(lines[index], "id")
            if parsed_id is not None:
                if source_id is not None:
                    raise SyncError("[[sources]] に id が重複しています")
                source_id = parsed_id
            parsed_rev = _parse_simple_toml_string_line(lines[index], "rev")
            if parsed_rev is not None:
                if rev_idx is not None:
                    raise SyncError(
                        f"[[sources]] に rev が重複しています"
                        + (f": {source_id}" if source_id else "")
                    )
                rev_idx = index
                current_rev = parsed_rev
            index += 1
        if source_id is None or rev_idx is None or current_rev is None:
            raise SyncError(
                "[[sources]] に id と rev が必要です"
                + (f": {source_id}" if source_id else "")
            )
        if source_id in seen:
            raise SyncError(f"source.id が重複しています: {source_id}")
        seen.add(source_id)
        if source_id not in pending:
            continue
        expected = expected_old[source_id].lower()
        if current_rev.lower() != expected:
            raise SyncError(
                f"sources.toml の pin が想定と一致しません: {source_id} "
                f"(file={current_rev[:12]}, expected={expected[:12]})"
            )
        lines[rev_idx] = _replace_simple_toml_string_line(
            lines[rev_idx], "rev", normalized_new[source_id]
        )
        pending.remove(source_id)

    if pending:
        missing = ", ".join(sorted(pending))
        raise SyncError(f"sources.toml に source がありません: {missing}")
    return "\n".join(lines)


def _write_text_atomic(root: Path, name: str, text: str) -> None:
    temporary = _unique_file(root, f"{name}.", suffix=".tmp")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        temporary.replace(root / name)
    finally:
        if temporary.exists():
            temporary.unlink()


def update_sources(config: Config, requested: frozenset[str] | None) -> int:
    with _exclusive_sync_lock(config.root):
        return _update_sources_locked(config, requested)


def _update_sources_locked(config: Config, requested: frozenset[str] | None) -> int:
    if requested is None:
        selected = list(config.sources.values())
    else:
        unknown = sorted(requested - set(config.sources))
        if unknown:
            raise SyncError(f"未知の source です: {', '.join(unknown)}")
        selected = [config.sources[source_id] for source_id in sorted(requested)]

    updates: dict[str, str] = {}
    for source in selected:
        tip = _remote_head(source)
        if tip == source.rev:
            print(f"{source.id}: up-to-date pin={source.rev[:12]}")
            continue
        print(f"updating {source.id}: {source.rev[:12]} -> {tip[:12]}")
        updates[source.id] = tip

    if not updates:
        return 0

    manifest_path = config.root / "sources.toml"
    original = manifest_path.read_text(encoding="utf-8")
    expected_old = {source_id: config.sources[source_id].rev for source_id in updates}
    rewritten = _rewrite_source_revs(original, expected_old, updates)
    _write_text_atomic(config.root, "sources.toml", rewritten)
    try:
        new_config = load_config(config.root)
        asset_ids = frozenset(
            asset.id
            for asset in new_config.assets
            if asset.source is not None and asset.source in updates
        )
        _sync_assets_locked(new_config, asset_ids)
    except Exception:
        _write_text_atomic(config.root, "sources.toml", original)
        raise
    return 0


def check_updates(config: Config) -> int:
    changed = False
    for source in config.sources.values():
        tip = _remote_head(source)
        state = "up-to-date" if tip == source.rev else "update-available"
        changed |= tip != source.rev
        print(f"{source.id}: {state} pin={source.rev[:12]} remote={tip[:12]}")
    return 1 if changed else 0


def status(config: Config, lock: Mapping[str, LockAsset]) -> int:
    print(f"default kinds: {','.join(config.default_kinds)}")
    print(f"default harnesses: {','.join(config.default_harnesses)}")
    for asset in config.assets:
        apply_flag = "apply" if apply_enabled(config, asset) else "apply-off"
        if asset.is_local:
            location = config.root.joinpath(*PurePosixPath(asset.target).parts)
            state = "local" if location.exists() else "local-missing"
            print(f"{asset.id}: {state} {apply_flag} kind={asset.kind}")
            continue
        source = config.sources[asset.source]
        entry = lock.get(asset.id)
        if entry is None:
            state = "not-synced"
        else:
            cache = _assert_safe_destination(config.root, entry.cache)
            state = "cached" if cache.is_dir() and _tree_hash(cache) == entry.export_hash else "cache-invalid"
        print(f"{asset.id}: {state} {apply_flag} kind={asset.kind} pin={source.rev[:12]}")
    if not config.assets:
        print("assets: none")
    return 0


def _asset_option(values: list[str] | None) -> frozenset[str] | None:
    if not values:
        return None
    result: set[str] = set()
    for value in values:
        result.update(part.strip() for part in value.split(",") if part.strip())
    return frozenset(result)


def _find_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / "sources.toml").is_file():
            return candidate
    raise SyncError("sources.toml を現在地または親 directory から見つけられません")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="外部 agent asset を commit pin で同期します")
    parser.add_argument("--root", help="repository root（通常は自動検出）")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="manifest と lock を検証")
    sync_parser = subparsers.add_parser(
        "sync", help="外部 Git から .cache と lock へ同期"
    )
    sync_parser.add_argument("--asset", action="append", help="asset ID（複数回/カンマ区切り可）")
    for name in ("diff", "apply"):
        command = subparsers.add_parser(name, help=f"選択した出力を{name}")
        command.add_argument("--kind", help="skill,agent,context（カンマ区切り）")
        command.add_argument("--harness", help="cursor,opencode,omp,pi,shared")
        if name == "diff":
            command.add_argument("--output", help="差分 plan の保存先")
    update_parser = subparsers.add_parser(
        "update", help="remote HEAD へ pin を進め cache/lock を同期"
    )
    update_parser.add_argument(
        "--source", action="append", help="source ID（複数回/カンマ区切り可）"
    )
    subparsers.add_parser("check-updates", help="remote HEAD と pin を比較")
    subparsers.add_parser("status", help="同期状態を表示")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(_find_root(args.root))
        if args.command == "validate":
            with _exclusive_sync_lock(config.root):
                lock = load_lock(config)
                validate(config, lock)
            print("validation passed")
            return 0
        if args.command == "sync":
            return sync_assets(config, _asset_option(args.asset))
        if args.command == "update":
            return update_sources(config, _asset_option(args.source))
        with _exclusive_sync_lock(config.root):
            lock = load_lock(config)
            validate(config, lock)
            if args.command == "check-updates":
                return check_updates(config)
            if args.command == "status":
                return status(config, lock)
            kinds = _parse_selection(args.kind, config.default_kinds, KINDS, "kind")
            harnesses = _parse_selection(
                args.harness, config.default_harnesses, config.allowed_harnesses, "harness"
            )
            lines, operations, pi_change, applied_update = plan_changes(
                config, lock, kinds, harnesses
            )
            if args.command == "diff":
                # Color only interactive stdout; --output and pipes stay plain.
                use_color = (not args.output) and _color_enabled_for_stdout()
                output = render_diff_output(lines, color=use_color)
                plain = (
                    output
                    if not use_color
                    else render_diff_output(lines, color=False)
                )
                if args.output:
                    path = _assert_safe_destination(config.root, args.output)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(plain, encoding="utf-8", newline="\n")
                sys.stdout.write(output)
                return 1 if lines else 0
            return apply_changes(
                config, operations, pi_change, applied_update, kinds=kinds
            )
    except SyncError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
