from __future__ import annotations

import contextlib
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest
from unittest import mock

from catalog import core


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class SyncCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.home = base / "home"
        self.home.mkdir()
        self.env = os.environ.copy()
        self.env["CATALOG_HOME"] = str(self.home)
        self.upstream = base / "upstream"
        self.root = base / "catalog"
        self.upstream.mkdir()
        self.root.mkdir()
        git(self.upstream, "init", "--quiet")
        (self.upstream / "skills" / "demo").mkdir(parents=True)
        (self.upstream / "skills" / "demo" / "SKILL.md").write_text(
            "---\nname: demo\ndescription: Use when testing.\n---\n# Demo\n",
            encoding="utf-8",
        )
        (self.upstream / "SKILL.md").write_text(
            "---\nname: standalone\ndescription: A single-file skill.\n---\n# Standalone\n",
            encoding="utf-8",
        )
        (self.upstream / "context").mkdir()
        (self.upstream / "context" / "RULE.md").write_text("# Rule\n", encoding="utf-8")
        git(self.upstream, "add", ".")
        git(
            self.upstream,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "fixture",
        )
        self.rev = git(self.upstream, "rev-parse", "HEAD")
        manifest = f"""
            schema_version = 1
            [apply]
            default_kinds = ["skill", "context"]
            default_harnesses = ["cursor"]
            allowed_harnesses = ["cursor", "opencode", "omp", "pi", "shared", "hermes"]

            [[sources]]
            id = "fixture"
            url = {str(self.upstream).replace(os.sep, '/').__repr__()}
            rev = "{self.rev}"
            license = "MIT"

            [[assets]]
            id = "fixture/demo"
            source = "fixture"
            kind = "skill"
            path = "skills/demo"
            target = "skills/demo"

            [[assets]]
            id = "fixture/standalone"
            source = "fixture"
            kind = "skill"
            path = "SKILL.md"
            target = "skills/standalone"

            [[assets]]
            id = "fixture/rule"
            source = "fixture"
            kind = "context"
            path = "context/RULE.md"
            target = "context/RULE.md"
        """
        (self.root / "sources.toml").write_text(
            textwrap.dedent(manifest), encoding="utf-8"
        )
        (self.root / "sources.lock.toml").write_text(
            "schema_version = 1\n", encoding="utf-8"
        )

    def _run(self, fn):
        previous = os.environ.get("CATALOG_HOME")
        os.environ["CATALOG_HOME"] = str(self.home)
        try:
            return fn()
        finally:
            if previous is None:
                os.environ.pop("CATALOG_HOME", None)
            else:
                os.environ["CATALOG_HOME"] = previous

    def test_sync_caches_only_and_apply_targets_global(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            # Leftover from the old materialize-into-repo behavior must be pruned.
            leftover = self.root / "skills" / "demo"
            leftover.mkdir(parents=True)
            (leftover / "SKILL.md").write_text("# Leftover\n", encoding="utf-8")

            core.sync_assets(config, None)
            lock = core.load_lock(config, required=True)
            core.validate(config, lock)
            self.assertEqual(
                lock["fixture/demo"].cache,
                f".cache/sources/fixture/{self.rev}/demo",
            )
            self.assertTrue(
                (self.root / ".cache" / "sources" / "fixture" / self.rev / "demo").is_dir()
            )
            self.assertFalse((self.root / "skills" / "demo").exists())
            self.assertFalse((self.root / "skills" / "standalone").exists())
            self.assertFalse((self.root / "context" / "RULE.md").exists())
            self.assertFalse((self.home / ".cursor" / "skills" / "demo").exists())

            (self.root / "skills" / "native").mkdir(parents=True)
            (self.root / "skills" / "native" / "SKILL.md").write_text(
                "# Native\n", encoding="utf-8"
            )

            lines, operations, pi, applied = core.plan_changes(
                config, lock, ("skill",), ("cursor",)
            )
            self.assertTrue(lines)
            core.apply_changes(config, operations, pi, applied)
            self.assertTrue(
                (self.home / ".cursor" / "skills" / "demo" / "SKILL.md").is_file()
            )
            self.assertTrue(
                (self.home / ".cursor" / "skills" / "standalone" / "SKILL.md").is_file()
            )
            self.assertFalse((self.root / ".cursor").exists())
            self.assertTrue((self.root / "skills" / "native" / "SKILL.md").is_file())

            lines, _, _, _ = core.plan_changes(config, lock, ("skill",), ("cursor",))
            self.assertEqual([], lines)

            lines, operations, pi, applied = core.plan_changes(
                config, lock, ("skill", "context"), ("cursor",)
            )
            self.assertTrue(lines)
            core.apply_changes(config, operations, pi, applied)
            self.assertTrue(
                (self.home / ".cursor" / "rules" / "RULE.mdc").is_file()
            )
            rule = (self.home / ".cursor" / "rules" / "RULE.mdc").read_text(
                encoding="utf-8"
            )
            self.assertIn("alwaysApply: true", rule)
            self.assertIn("# Rule", rule)
            lines, operations, _, applied = core.plan_changes(
                config, lock, ("skill", "context"), ("cursor",)
            )
            self.assertEqual([], lines)
            self.assertEqual([], operations)

        self._run(exercise)

    def test_hermes_skill_target_is_namespaced_under_anago(self) -> None:
        asset = core.Asset(
            id="fixture/demo",
            source="fixture",
            kind="skill",
            path="skills/demo",
            target="skills/demo",
            harnesses=("cursor", "hermes"),
        )

        self.assertEqual(core._target_for(asset, "hermes"), "skills/anago/demo")
        self.assertEqual(core._target_for(asset, "cursor"), "skills/demo")

    def test_hermes_skill_apply_uses_anago_namespace(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock = core.load_lock(config, required=True)

            lines, operations, pi, applied = core.plan_changes(
                config, lock, ("skill",), ("hermes",)
            )
            self.assertTrue(lines)
            core.apply_changes(
                config, operations, pi, applied, kinds=("skill",)
            )

            installed = self.home / ".hermes" / "skills" / "anago" / "demo"
            self.assertTrue((installed / "SKILL.md").is_file())
            self.assertFalse(
                (self.home / ".hermes" / "skills" / "demo").exists()
            )

        self._run(exercise)

    def test_validate_rejects_catalog_harness(self) -> None:
        path = self.root / "sources.toml"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                'allowed_harnesses = ["cursor", "opencode", "omp", "pi", "shared", "hermes"]',
                'allowed_harnesses = ["catalog", "cursor"]',
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(core.SyncError, "catalog"):
            core.load_config(self.root)

    def test_validate_rejects_path_escape(self) -> None:
        path = self.root / "sources.toml"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                'target = "skills/demo"', 'target = "../outside"'
            ),
            encoding="utf-8",
        )
        with self.assertRaises(core.SyncError):
            core.load_config(self.root)

    def test_validate_rejects_unsafe_source_id(self) -> None:
        path = self.root / "sources.toml"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                'id = "fixture"', 'id = "fixture/../outside"', 1
            ),
            encoding="utf-8",
        )
        with self.assertRaises(core.SyncError):
            core.load_config(self.root)

    def test_diff_rejects_unsupported_kind_harness_pair(self) -> None:
        config = core.load_config(self.root)

        def exercise() -> None:
            with self.assertRaisesRegex(core.SyncError, "agent×pi"):
                core.plan_changes(config, {}, ("agent",), ("pi",))

        self._run(exercise)

    def test_sync_rejects_symlink_entries(self) -> None:
        blob = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=self.upstream,
            input="SKILL.md",
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        git(
            self.upstream,
            "update-index",
            "--add",
            "--cacheinfo",
            f"120000,{blob},skills/demo/link",
        )
        git(
            self.upstream,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "symlink",
        )
        new_rev = git(self.upstream, "rev-parse", "HEAD")
        manifest = self.root / "sources.toml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(self.rev, new_rev),
            encoding="utf-8",
        )
        config = core.load_config(self.root)

        def exercise() -> None:
            with self.assertRaisesRegex(core.SyncError, "symlink"):
                core.sync_assets(config, frozenset(("fixture/demo",)))

        self._run(exercise)

    def test_pi_markers_preserve_native_content(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock = core.load_lock(config, required=True)
            pi_file = self.home / ".pi" / "agent" / "APPEND_SYSTEM.md"
            pi_file.parent.mkdir(parents=True)
            pi_file.write_text("# Native\n", encoding="utf-8")

            lines, operations, pi, applied = core.plan_changes(
                config, lock, ("context",), ("pi",)
            )
            self.assertTrue(lines)
            self.assertEqual([], operations)
            core.apply_changes(config, operations, pi, applied)
            content = pi_file.read_text(encoding="utf-8")
            self.assertIn("# Native", content)
            self.assertIn("external-skill-sync:fixture/rule:begin", content)
            self.assertIn("# Rule", content)
            lines, _, _, _ = core.plan_changes(config, lock, ("context",), ("pi",))
            self.assertEqual([], lines)

        self._run(exercise)

    def test_local_asset_apply_from_catalog_tree(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock = core.load_lock(config, required=True)

            local_dir = self.root / "skills" / "native"
            local_dir.mkdir(parents=True)
            (local_dir / "SKILL.md").write_text("# Native\n", encoding="utf-8")
            (local_dir / "notes.txt").write_text("keep\n", encoding="utf-8")

            (self.root / "assets.local.toml").write_text(
                textwrap.dedent(
                    """
                    [skills]
                    native = true
                    """
                ),
                encoding="utf-8",
            )
            config = core.load_config(self.root)
            core.validate(config, lock)
            self.assertTrue(any(asset.id == "local/native" and asset.is_local for asset in config.assets))

            lines, operations, _, applied = core.plan_changes(
                config, lock, ("skill",), ("cursor",)
            )
            self.assertTrue(any("local/native" in line for line in lines))
            core.apply_changes(config, operations, None, applied)
            applied = self.home / ".cursor" / "skills" / "native"
            self.assertTrue((applied / "SKILL.md").is_file())
            self.assertEqual(
                (applied / "SKILL.md").read_text(encoding="utf-8"), "# Native\n"
            )
            self.assertEqual(
                (applied / "notes.txt").read_text(encoding="utf-8"), "keep\n"
            )

            lines, operations, _, applied = core.plan_changes(
                config, lock, ("skill",), ("cursor",)
            )
            self.assertFalse(any("local/native" in line for line in lines))

        self._run(exercise)

    def test_sources_toml_rejects_local_assets(self) -> None:
        manifest = self.root / "sources.toml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8")
            + textwrap.dedent(
                """
                [[assets]]
                id = "local/native"
                kind = "skill"
                path = "skills/native"
                target = "skills/native"
                """
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(core.SyncError, "assets.local.toml"):
            core.load_config(self.root)

    def test_disabled_local_skill_excluded_from_plan(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock = core.load_lock(config, required=True)
            local_dir = self.root / "skills" / "native"
            local_dir.mkdir(parents=True)
            (local_dir / "SKILL.md").write_text("# Native\n", encoding="utf-8")
            (self.root / "assets.local.toml").write_text(
                textwrap.dedent(
                    """
                    [skills]
                    native = false
                    """
                ),
                encoding="utf-8",
            )
            config = core.load_config(self.root)
            self.assertFalse(any(asset.id == "local/native" for asset in config.assets))
            lines, _, _, _ = core.plan_changes(config, lock, ("skill",), ("cursor",))
            self.assertFalse(any("local/native" in line for line in lines))

        self._run(exercise)

    def test_external_apply_enable_filters_diff(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock = core.load_lock(config, required=True)
            (self.root / "assets.local.toml").write_text(
                textwrap.dedent(
                    """
                    [external]
                    "fixture/demo" = true
                    "fixture/standalone" = false
                    "fixture/rule" = false
                    """
                ),
                encoding="utf-8",
            )
            config = core.load_config(self.root)
            self.assertEqual(config.external_apply_enabled, frozenset(("fixture/demo",)))
            self.assertTrue(core.apply_enabled(config, next(a for a in config.assets if a.id == "fixture/demo")))
            self.assertFalse(
                core.apply_enabled(config, next(a for a in config.assets if a.id == "fixture/standalone"))
            )
            lines, _, _, _ = core.plan_changes(config, lock, ("skill",), ("cursor",))
            self.assertTrue(any("fixture/demo" in line for line in lines))
            self.assertFalse(any("fixture/standalone" in line for line in lines))

        self._run(exercise)

    def test_external_apply_unknown_id_rejected(self) -> None:
        (self.root / "assets.local.toml").write_text(
            textwrap.dedent(
                """
                [external]
                "fixture/nope" = true
                """
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(core.SyncError, "未知の asset.id"):
            core.load_config(self.root)

    def test_sync_cleans_stale_cache_entries(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            stale = self.root / ".cache" / "sources" / "fixture" / self.rev / "deadbeef"
            stale.mkdir(parents=True)
            (stale / "junk.txt").write_text("stale\n", encoding="utf-8")
            other = self.root / ".cache" / "sources" / "old-source" / "abc" / "orphan"
            other.mkdir(parents=True)
            (other / "junk.txt").write_text("orphan\n", encoding="utf-8")

            core.sync_assets(config, None)

            self.assertFalse(stale.exists())
            self.assertFalse((self.root / ".cache" / "sources" / "old-source").exists())
            self.assertTrue(
                (self.root / ".cache" / "sources" / "fixture" / self.rev / "demo").is_dir()
            )
            self.assertTrue(
                (
                    self.root / ".cache" / "sources" / "fixture" / self.rev / "RULE.md"
                ).is_dir()
            )
            self.assertFalse((self.root / "skills" / "demo").exists())

        self._run(exercise)

    def test_pi_skills_apply_to_tree_not_markers(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock = core.load_lock(config, required=True)
            pi_file = self.home / ".pi" / "agent" / "APPEND_SYSTEM.md"
            pi_file.parent.mkdir(parents=True)
            pi_file.write_text("# Native\n", encoding="utf-8")

            lines, operations, pi, applied = core.plan_changes(
                config, lock, ("skill",), ("pi",)
            )
            self.assertTrue(lines)
            self.assertIsNone(pi)
            self.assertTrue(operations)
            core.apply_changes(config, operations, pi, applied)
            self.assertTrue(
                (self.home / ".pi" / "agent" / "skills" / "demo" / "SKILL.md").is_file()
            )
            self.assertTrue(
                (
                    self.home / ".pi" / "agent" / "skills" / "standalone" / "SKILL.md"
                ).is_file()
            )
            self.assertEqual(pi_file.read_text(encoding="utf-8"), "# Native\n")
            self.assertNotIn("external-skill-sync", pi_file.read_text(encoding="utf-8"))

        self._run(exercise)

    def test_partial_sync_updates_sibling_lock_revs(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            (self.upstream / "skills" / "demo" / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Use when testing.\n---\n# Demo v2\n",
                encoding="utf-8",
            )
            git(self.upstream, "add", ".")
            git(
                self.upstream,
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "bump",
            )
            new_rev = git(self.upstream, "rev-parse", "HEAD")
            manifest = self.root / "sources.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(self.rev, new_rev),
                encoding="utf-8",
            )
            config = core.load_config(self.root)
            core.sync_assets(config, frozenset(("fixture/demo",)))
            lock = core.load_lock(config, required=True)
            self.assertEqual(lock["fixture/demo"].rev, new_rev)
            self.assertEqual(lock["fixture/standalone"].rev, new_rev)
            self.assertEqual(lock["fixture/rule"].rev, new_rev)
            core.validate(config, lock)

        self._run(exercise)

    def test_failed_sync_preserves_previous_cache_and_lock(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock_before = (self.root / "sources.lock.toml").read_text(encoding="utf-8")
            cache_demo = (
                self.root / ".cache" / "sources" / "fixture" / self.rev / "demo"
            )
            self.assertTrue(cache_demo.is_dir())
            skill_before = (cache_demo / "SKILL.md").read_bytes()

            manifest = self.root / "sources.toml"
            bad_rev = "0" * 40
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(self.rev, bad_rev),
                encoding="utf-8",
            )
            config = core.load_config(self.root)
            with self.assertRaises(core.SyncError):
                core.sync_assets(config, None)

            self.assertEqual(
                (self.root / "sources.lock.toml").read_text(encoding="utf-8"),
                lock_before,
            )
            self.assertTrue(cache_demo.is_dir())
            self.assertEqual((cache_demo / "SKILL.md").read_bytes(), skill_before)
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(bad_rev, self.rev),
                encoding="utf-8",
            )
            good = core.load_config(self.root)
            lock = core.load_lock(good, required=True)
            core.validate(good, lock)
            lines, _, _, _ = core.plan_changes(good, lock, ("skill",), ("cursor",))
            self.assertTrue(isinstance(lines, list))

        self._run(exercise)

    def test_pi_marker_replacement_is_literal(self) -> None:
        def exercise() -> None:
            body = "Capture \\1 and path C:\\path\\to\\file\n"
            (self.upstream / "context" / "RULE.md").write_text(body, encoding="utf-8")
            git(self.upstream, "add", ".")
            git(
                self.upstream,
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "backslash",
            )
            new_rev = git(self.upstream, "rev-parse", "HEAD")
            manifest = self.root / "sources.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(self.rev, new_rev),
                encoding="utf-8",
            )
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock = core.load_lock(config, required=True)
            pi_file = self.home / ".pi" / "agent" / "APPEND_SYSTEM.md"
            pi_file.parent.mkdir(parents=True)
            pi_file.write_text("", encoding="utf-8")

            for _ in range(2):
                lines, operations, pi, applied = core.plan_changes(
                    config, lock, ("context",), ("pi",)
                )
                if lines:
                    core.apply_changes(config, operations, pi, applied)
            content = pi_file.read_text(encoding="utf-8")
            self.assertIn("Capture \\1 and path C:\\path\\to\\file", content)
            self.assertNotIn("Capture \x01", content)

        self._run(exercise)

    def test_sync_removes_dropped_catalog_target_and_pi_orphan(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock = core.load_lock(config, required=True)
            self.assertFalse((self.root / "context" / "RULE.md").exists())
            # Simulate a leftover copy from the old materialize-into-repo behavior.
            (self.root / "context").mkdir(parents=True, exist_ok=True)
            (self.root / "context" / "RULE.md").write_text("# Leftover\n", encoding="utf-8")

            pi_file = self.home / ".pi" / "agent" / "APPEND_SYSTEM.md"
            pi_file.parent.mkdir(parents=True)
            pi_file.write_text("# Native\n", encoding="utf-8")
            _, operations, pi, applied = core.plan_changes(config, lock, ("context",), ("pi",))
            core.apply_changes(config, operations, pi, applied)
            self.assertIn("external-skill-sync:fixture/rule:begin", pi_file.read_text())

            manifest = self.root / "sources.toml"
            text = manifest.read_text(encoding="utf-8")
            # Drop the rule asset block from the manifest.
            start = text.index("[[assets]]\nid = \"fixture/rule\"")
            manifest.write_text(text[:start].rstrip() + "\n", encoding="utf-8")
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            self.assertFalse((self.root / "context" / "RULE.md").exists())
            lock = core.load_lock(config, required=True)
            self.assertNotIn("fixture/rule", lock)

            lines, operations, pi, applied = core.plan_changes(
                config, lock, ("context",), ("pi",)
            )
            self.assertTrue(lines)
            core.apply_changes(config, operations, pi, applied)
            content = pi_file.read_text(encoding="utf-8")
            self.assertIn("# Native", content)
            self.assertNotIn("external-skill-sync:fixture/rule", content)

        self._run(exercise)

    def test_export_preserves_executable_mode(self) -> None:
        def exercise() -> None:
            script = self.upstream / "skills" / "demo" / "run.sh"
            script.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
            git(self.upstream, "add", ".")
            blob = git(self.upstream, "hash-object", "-w", str(script))
            git(
                self.upstream,
                "update-index",
                "--add",
                "--cacheinfo",
                f"100755,{blob},skills/demo/run.sh",
            )
            git(
                self.upstream,
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "exec",
            )
            new_rev = git(self.upstream, "rev-parse", "HEAD")
            manifest = self.root / "sources.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(self.rev, new_rev),
                encoding="utf-8",
            )
            config = core.load_config(self.root)
            with mock.patch.object(
                core, "_set_file_mode", wraps=core._set_file_mode
            ) as mocked:
                core.sync_assets(config, frozenset(("fixture/demo",)))
                chmod_modes = [
                    call.args[1]
                    for call in mocked.call_args_list
                    if call.args and call.args[0].name == "run.sh"
                ]
                self.assertIn(core.EXECUTABLE_FILE_MODE, chmod_modes)

            lock = core.load_lock(config, required=True)
            cache_script = (
                self.root
                / ".cache"
                / "sources"
                / "fixture"
                / new_rev
                / "demo"
                / "run.sh"
            )
            self.assertTrue(cache_script.is_file())
            self.assertFalse((self.root / "skills" / "demo" / "run.sh").exists())
            if os.name != "nt":
                self.assertTrue(cache_script.stat().st_mode & 0o111)

            lines, operations, pi, applied = core.plan_changes(
                config, lock, ("skill",), ("cursor",)
            )
            core.apply_changes(config, operations, pi, applied)
            applied = self.home / ".cursor" / "skills" / "demo" / "run.sh"
            self.assertTrue(applied.is_file())
            if os.name != "nt":
                self.assertTrue(applied.stat().st_mode & 0o111)

        self._run(exercise)

    def test_partial_sync_cleans_obsolete_sibling_cache(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            dead = (
                self.root / ".cache" / "sources" / "fixture" / self.rev / "dead"
            )
            dead.mkdir(parents=True)
            (dead / "junk.txt").write_text("stale\n", encoding="utf-8")

            core.sync_assets(config, frozenset(("fixture/demo",)))
            self.assertFalse(dead.exists())
            self.assertTrue(
                (self.root / ".cache" / "sources" / "fixture" / self.rev / "demo").is_dir()
            )

        self._run(exercise)

    def test_export_hash_uses_git_mode_not_filesystem(self) -> None:
        def exercise() -> None:
            script = self.upstream / "skills" / "demo" / "run.sh"
            script.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
            git(self.upstream, "add", ".")
            blob = git(self.upstream, "hash-object", "-w", str(script))
            git(
                self.upstream,
                "update-index",
                "--add",
                "--cacheinfo",
                f"100755,{blob},skills/demo/run.sh",
            )
            git(
                self.upstream,
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "exec",
            )
            new_rev = git(self.upstream, "rev-parse", "HEAD")
            manifest = self.root / "sources.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(self.rev, new_rev),
                encoding="utf-8",
            )
            config = core.load_config(self.root)
            core.sync_assets(config, frozenset(("fixture/demo",)))
            lock = core.load_lock(config, required=True)
            cache = (
                self.root / ".cache" / "sources" / "fixture" / new_rev / "demo"
            )
            meta = core._read_export_meta(cache)
            self.assertIsNotNone(meta)
            assert meta is not None
            self.assertEqual(meta["run.sh"], core.EXECUTABLE_FILE_MODE)
            hash_with_meta = core._tree_hash(cache)
            self.assertEqual(lock["fixture/demo"].export_hash, hash_with_meta)

            # Even if the filesystem mode looks non-executable, the hash must
            # still follow export metadata (Windows-safe).
            original_stat = Path.stat

            def fake_stat(self, *args, **kwargs):
                result = original_stat(self, *args, **kwargs)
                if self.name == "run.sh":
                    mode = (result.st_mode & ~0o111) | 0o644
                    return result.__class__(
                        (
                            mode,
                            result.st_ino,
                            result.st_dev,
                            result.st_nlink,
                            result.st_uid,
                            result.st_gid,
                            result.st_size,
                            result.st_atime,
                            result.st_mtime,
                            result.st_ctime,
                        )
                    )
                return result

            with mock.patch.object(Path, "stat", fake_stat):
                self.assertEqual(core._tree_hash(cache), hash_with_meta)
                files = core._cache_files(config, lock["fixture/demo"])
                self.assertEqual(files["run.sh"][1], core.EXECUTABLE_FILE_MODE)

        self._run(exercise)

    def test_prune_removes_old_target_on_retarget(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            # Leftover catalog copy under the old target name.
            old = self.root / "skills" / "demo"
            old.mkdir(parents=True)
            (old / "SKILL.md").write_text("# Leftover\n", encoding="utf-8")
            core.sync_assets(config, None)
            self.assertFalse((self.root / "skills" / "demo").exists())
            manifest = self.root / "sources.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'target = "skills/demo"',
                    'target = "skills/demo-renamed"',
                    1,
                ),
                encoding="utf-8",
            )
            config = core.load_config(self.root)
            # Plant another leftover after retarget to confirm both old and new are pruned.
            renamed = self.root / "skills" / "demo-renamed"
            renamed.mkdir(parents=True)
            (renamed / "SKILL.md").write_text("# Leftover renamed\n", encoding="utf-8")
            core.sync_assets(config, None)
            self.assertFalse((self.root / "skills" / "demo").exists())
            self.assertFalse((self.root / "skills" / "demo-renamed").exists())
            lock = core.load_lock(config, required=True)
            self.assertEqual(lock["fixture/demo"].target, "skills/demo-renamed")
            self.assertTrue(
                (
                    self.root
                    / ".cache"
                    / "sources"
                    / "fixture"
                    / self.rev
                    / "demo-renamed"
                ).is_dir()
            )

        self._run(exercise)

    def test_apply_removes_stale_harness_outputs(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock = core.load_lock(config, required=True)
            lines, operations, pi, applied = core.plan_changes(
                config, lock, ("skill",), ("cursor",)
            )
            core.apply_changes(
                config, operations, pi, applied, kinds=("skill",)
            )
            demo = self.home / ".cursor" / "skills" / "demo"
            self.assertTrue((demo / "SKILL.md").is_file())
            manifest_path = self.home / ".cursor" / core.APPLIED_MANIFEST_REL
            self.assertTrue(manifest_path.is_file())

            text = (self.root / "sources.toml").read_text(encoding="utf-8")
            start = text.index('[[assets]]\nid = "fixture/demo"')
            end = text.index('[[assets]]\nid = "fixture/standalone"')
            (self.root / "sources.toml").write_text(
                text[:start] + text[end:], encoding="utf-8"
            )
            config = core.load_config(self.root)
            lock = core.load_lock(config, required=True)
            # Drop lock entry for removed asset to mimic post-sync state.
            del_entries = {k: v for k, v in lock.items() if k != "fixture/demo"}
            core.write_lock(config, del_entries)
            lock = core.load_lock(config, required=True)
            lines, operations, pi, applied = core.plan_changes(
                config, lock, ("skill",), ("cursor",)
            )
            self.assertTrue(any(" remove] " in line for line in lines))
            core.apply_changes(
                config, operations, pi, applied, kinds=("skill",)
            )
            self.assertFalse(demo.exists())
            remaining = core._load_applied_manifest(self.home / ".cursor")
            self.assertFalse(any(item.asset_id == "fixture/demo" for item in remaining))

        self._run(exercise)

    def test_render_diff_output_summary_and_color(self) -> None:
        lines = [
            "[fixture/demo → cursor] + skills/demo/SKILL.md",
            "[fixture/demo → cursor] ~ skills/demo/notes.txt",
            "[fixture/old → cursor remove] - skills/old/SKILL.md",
            "[fixture/demo → cursor]   --- skills/demo/notes.txt",
        ]
        plain = core.render_diff_output(lines, color=False)
        self.assertTrue(plain.startswith("summary: +1  ~1  -1\n"))
        self.assertIn("[fixture/old → cursor remove] - skills/old/SKILL.md", plain)
        self.assertNotIn("\033[", plain)

        colored = core.render_diff_output(lines, color=True)
        self.assertIn(core._ANSI_GREEN, colored)
        self.assertIn(core._ANSI_YELLOW, colored)
        self.assertIn(core._ANSI_RED, colored)
        self.assertIn(core._ANSI_RESET, colored)
        # Unified-diff body lines stay uncolored.
        self.assertIn(
            "[fixture/demo → cursor]   --- skills/demo/notes.txt",
            colored,
        )

        self.assertEqual(core.render_diff_output([], color=False), "no changes\n")

    def test_pi_markers_stripped_when_pi_removed_from_harnesses(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock = core.load_lock(config, required=True)
            pi_file = self.home / ".pi" / "agent" / "APPEND_SYSTEM.md"
            pi_file.parent.mkdir(parents=True)
            pi_file.write_text("# Native\n", encoding="utf-8")
            _, operations, pi, applied = core.plan_changes(
                config, lock, ("context",), ("pi",)
            )
            core.apply_changes(config, operations, pi, applied, kinds=("context",))
            self.assertIn("external-skill-sync:fixture/rule:begin", pi_file.read_text())

            manifest = self.root / "sources.toml"
            text = manifest.read_text(encoding="utf-8")
            # Restrict the rule asset to cursor only.
            old = (
                'id = "fixture/rule"\n'
                'source = "fixture"\n'
                'kind = "context"\n'
                'path = "context/RULE.md"\n'
                'target = "context/RULE.md"\n'
            )
            new = old + 'harnesses = ["cursor"]\n'
            self.assertIn(old, text)
            manifest.write_text(text.replace(old, new, 1), encoding="utf-8")
            config = core.load_config(self.root)
            lock = core.load_lock(config, required=True)
            lines, operations, pi, applied = core.plan_changes(
                config, lock, ("context",), ("pi",)
            )
            self.assertTrue(lines)
            core.apply_changes(config, operations, pi, applied, kinds=("context",))
            content = pi_file.read_text(encoding="utf-8")
            self.assertIn("# Native", content)
            self.assertNotIn("external-skill-sync:fixture/rule", content)

        self._run(exercise)

    def test_partial_sync_expands_changed_pins_on_other_sources(self) -> None:
        def exercise() -> None:
            other = Path(self.temporary.name) / "upstream-other"
            other.mkdir()
            git(other, "init", "--quiet")
            (other / "skills" / "other").mkdir(parents=True)
            (other / "skills" / "other" / "SKILL.md").write_text(
                "# Other\n", encoding="utf-8"
            )
            git(other, "add", ".")
            git(
                other,
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "other",
            )
            other_rev = git(other, "rev-parse", "HEAD")
            manifest = self.root / "sources.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8")
                + textwrap.dedent(
                    f"""
                    [[sources]]
                    id = "other"
                    url = {str(other).replace(os.sep, '/').__repr__()}
                    rev = "{other_rev}"
                    license = "MIT"

                    [[assets]]
                    id = "other/skill"
                    source = "other"
                    kind = "skill"
                    path = "skills/other"
                    target = "skills/other"
                    """
                ),
                encoding="utf-8",
            )
            config = core.load_config(self.root)
            core.sync_assets(config, None)

            (other / "skills" / "other" / "SKILL.md").write_text(
                "# Other v2\n", encoding="utf-8"
            )
            git(other, "add", ".")
            git(
                other,
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "bump-other",
            )
            new_other = git(other, "rev-parse", "HEAD")
            text = manifest.read_text(encoding="utf-8").replace(other_rev, new_other)
            manifest.write_text(text, encoding="utf-8")
            config = core.load_config(self.root)
            # Request only fixture/demo; changed pin on "other" must be pulled in.
            core.sync_assets(config, frozenset(("fixture/demo",)))
            lock = core.load_lock(config, required=True)
            self.assertEqual(lock["other/skill"].rev, new_other)
            core.validate(config, lock)

        self._run(exercise)

    def test_clean_cache_unlinks_symlink_aliases(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            sources = self.root / ".cache" / "sources"
            alias = sources / "alias-skill.md"
            alias.write_text("alias\n", encoding="utf-8")
            real_is_symlink = Path.is_symlink

            def fake_is_symlink(self: Path) -> bool:
                if self == alias:
                    return True
                return real_is_symlink(self)

            with mock.patch.object(Path, "is_symlink", fake_is_symlink):
                core._clean_cache(config, core.load_lock(config, required=True))
            self.assertFalse(alias.exists())
            self.assertTrue(
                (
                    self.root
                    / ".cache"
                    / "sources"
                    / "fixture"
                    / self.rev
                    / "demo"
                    / "SKILL.md"
                ).is_file()
            )

        self._run(exercise)

    def test_sync_lock_rejects_concurrent_holder(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            with core._exclusive_sync_lock(config.root):
                with self.assertRaisesRegex(core.SyncError, "別の sync"):
                    with core._exclusive_sync_lock(config.root):
                        pass

        self._run(exercise)

    def test_promote_failure_rolls_back_lock(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock_before = (self.root / "sources.lock.toml").read_text(encoding="utf-8")
            cache_before = (
                self.root / ".cache" / "sources" / "fixture" / self.rev / "demo" / "SKILL.md"
            ).read_text(encoding="utf-8")

            (self.upstream / "skills" / "demo" / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Use when testing.\n---\n# Demo boom\n",
                encoding="utf-8",
            )
            git(self.upstream, "add", ".")
            git(
                self.upstream,
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "boom",
            )
            new_rev = git(self.upstream, "rev-parse", "HEAD")
            manifest = self.root / "sources.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(self.rev, new_rev),
                encoding="utf-8",
            )
            config = core.load_config(self.root)

            original_promote = core._promote_path

            def boom_promote(source, destination):
                if destination.name == "demo":
                    raise core.SyncError("simulated promote failure")
                return original_promote(source, destination)

            with mock.patch.object(core, "_promote_path", side_effect=boom_promote):
                with self.assertRaisesRegex(core.SyncError, "simulated promote"):
                    core.sync_assets(config, frozenset(("fixture/demo",)))

            self.assertEqual(
                (self.root / "sources.lock.toml").read_text(encoding="utf-8"),
                lock_before,
            )
            self.assertEqual(
                (
                    self.root
                    / ".cache"
                    / "sources"
                    / "fixture"
                    / self.rev
                    / "demo"
                    / "SKILL.md"
                ).read_text(encoding="utf-8"),
                cache_before,
            )

        self._run(exercise)

    def test_sync_rejects_cache_symlink(self) -> None:
        def exercise() -> None:
            if os.name == "nt":
                self.skipTest("symlink creation requires elevated privileges on Windows")
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            cache_dir = self.root / ".cache" / "sources" / "fixture" / self.rev / "demo"
            outside = self.root / "outside-secret"
            outside.mkdir()
            (outside / "SKILL.md").write_text("pwned\n", encoding="utf-8")
            core._remove_tree(cache_dir)
            cache_dir.symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(core.SyncError, "symlink"):
                core.sync_assets(config, frozenset(("fixture/demo",)))

        self._run(exercise)

    def test_validate_rejects_cache_path_mismatch(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock = core.load_lock(config, required=True)
            entry = lock["fixture/demo"]
            bad = core.LockAsset(
                entry.id,
                entry.source,
                entry.rev,
                entry.export_hash,
                entry.target,
                ".cache/sources/fixture/" + self.rev + "/other-name",
                entry.source_is_file,
            )
            core.write_lock(config, {**lock, entry.id: bad})
            lock = core.load_lock(config, required=True)
            with self.assertRaisesRegex(core.SyncError, "一致しません"):
                core.validate(config, lock)

        self._run(exercise)

    def test_partial_sync_refreshes_cache_path_mismatch(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock = core.load_lock(config, required=True)
            entry = lock["fixture/demo"]
            bad = core.LockAsset(
                entry.id,
                entry.source,
                entry.rev,
                entry.export_hash,
                entry.target,
                ".cache/sources/fixture/" + self.rev + "/wrong-cache",
                entry.source_is_file,
            )
            core.write_lock(config, {**lock, entry.id: bad})
            core.sync_assets(config, frozenset(("fixture/demo",)))
            lock = core.load_lock(config, required=True)
            self.assertEqual(
                lock["fixture/demo"].cache,
                f".cache/sources/fixture/{self.rev}/demo",
            )
            core.validate(config, lock)

        self._run(exercise)

    def test_local_only_partial_sync_expands_incompatible_lock(self) -> None:
        def exercise() -> None:
            local_dir = self.root / "skills" / "native"
            local_dir.mkdir(parents=True)
            (local_dir / "SKILL.md").write_text("# Native\n", encoding="utf-8")
            (self.root / "assets.local.toml").write_text(
                textwrap.dedent(
                    """
                    [skills]
                    native = true
                    """
                ),
                encoding="utf-8",
            )
            manifest = self.root / "sources.toml"
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            (self.upstream / "skills" / "demo" / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Use when testing.\n---\n# Demo v2\n",
                encoding="utf-8",
            )
            git(self.upstream, "add", ".")
            git(
                self.upstream,
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "bump",
            )
            new_rev = git(self.upstream, "rev-parse", "HEAD")
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(self.rev, new_rev),
                encoding="utf-8",
            )
            config = core.load_config(self.root)
            core.sync_assets(config, frozenset(("local/native",)))
            lock = core.load_lock(config, required=True)
            core.validate(config, lock)
            self.assertEqual(lock["fixture/demo"].rev, new_rev)

        self._run(exercise)

    def test_load_config_rejects_overlapping_catalog_targets(self) -> None:
        manifest = self.root / "sources.toml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8")
            + textwrap.dedent(
                """
                [[assets]]
                id = "fixture/nested"
                source = "fixture"
                kind = "skill"
                path = "skills/demo"
                target = "skills/demo/extra"
                """
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(core.SyncError, "重な"):
            core.load_config(self.root)

    def test_load_config_rejects_overlapping_harness_target(self) -> None:
        manifest = self.root / "sources.toml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8")
            + textwrap.dedent(
                """
                [[assets]]
                id = "fixture/nested-harness"
                source = "fixture"
                kind = "skill"
                path = "skills/demo"
                target = "skills/demo/nested"
                """
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(core.SyncError, "重な"):
            core.load_config(self.root)

    def test_export_rejects_reserved_export_meta(self) -> None:
        (self.upstream / "skills" / "demo" / core.EXPORT_META_REL).write_text(
            "schema_version = 1\n", encoding="utf-8"
        )
        git(self.upstream, "add", ".")
        git(
            self.upstream,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "meta",
        )
        new_rev = git(self.upstream, "rev-parse", "HEAD")
        manifest = self.root / "sources.toml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(self.rev, new_rev),
            encoding="utf-8",
        )
        config = core.load_config(self.root)

        def exercise() -> None:
            with self.assertRaisesRegex(core.SyncError, core.EXPORT_META_REL):
                core.sync_assets(config, frozenset(("fixture/demo",)))

        self._run(exercise)

    def test_promote_replace_failure_restores_destination(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            cache_before = (
                self.root / ".cache" / "sources" / "fixture" / self.rev / "demo" / "SKILL.md"
            ).read_text(encoding="utf-8")
            original_replace = Path.replace
            calls = {"count": 0}

            def flaky_replace(self, target):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise OSError("simulated replace failure")
                return original_replace(self, target)

            with mock.patch.object(Path, "replace", flaky_replace):
                with self.assertRaises(OSError):
                    core.sync_assets(config, frozenset(("fixture/demo",)))
            restored = (
                self.root / ".cache" / "sources" / "fixture" / self.rev / "demo" / "SKILL.md"
            )
            self.assertTrue(restored.is_file())
            self.assertEqual(restored.read_text(encoding="utf-8"), cache_before)
            parent = restored.parent.parent
            self.assertFalse(any(path.name.endswith(".bak-") for path in parent.iterdir()))

        self._run(exercise)

    def test_pre_commit_failure_restores_lock_cache_and_quarantine(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            cache_before = (
                self.root / ".cache" / "sources" / "fixture" / self.rev / "demo" / "SKILL.md"
            ).read_text(encoding="utf-8")

            manifest = self.root / "sources.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    'target = "skills/demo"',
                    'target = "skills/demo-renamed"',
                    1,
                ),
                encoding="utf-8",
            )
            config = core.load_config(self.root)
            renamed = self.root / "skills" / "demo-renamed"
            renamed.mkdir(parents=True)
            (renamed / "SKILL.md").write_text("# Copy\n", encoding="utf-8")
            stale = self.root / "skills" / "old-stale"
            stale.mkdir(parents=True)
            (stale / "SKILL.md").write_text("# Stale\n", encoding="utf-8")
            lock = core.load_lock(config, required=True)
            core.write_lock(
                config,
                {
                    **lock,
                    "fixture/demo": core.LockAsset(
                        lock["fixture/demo"].id,
                        lock["fixture/demo"].source,
                        lock["fixture/demo"].rev,
                        lock["fixture/demo"].export_hash,
                        "skills/old-stale",
                        lock["fixture/demo"].cache,
                        lock["fixture/demo"].source_is_file,
                    ),
                },
            )
            lock_before = (self.root / "sources.lock.toml").read_text(encoding="utf-8")

            def boom_write(*args, **kwargs):
                raise core.SyncError("simulated lock write failure")

            with mock.patch.object(core, "write_lock", side_effect=boom_write):
                with self.assertRaisesRegex(core.SyncError, "simulated lock"):
                    core.sync_assets(config, None)

            self.assertEqual(
                (self.root / "sources.lock.toml").read_text(encoding="utf-8"),
                lock_before,
            )
            self.assertEqual(
                (
                    self.root
                    / ".cache"
                    / "sources"
                    / "fixture"
                    / self.rev
                    / "demo"
                    / "SKILL.md"
                ).read_text(encoding="utf-8"),
                cache_before,
            )
            self.assertTrue(renamed.exists())
            self.assertTrue(stale.exists())

        self._run(exercise)

    def test_post_commit_finalize_failure_keeps_new_lock(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock_before = (self.root / "sources.lock.toml").read_text(encoding="utf-8")

            (self.upstream / "skills" / "demo" / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Use when testing.\n---\n# Demo v3\n",
                encoding="utf-8",
            )
            git(self.upstream, "add", ".")
            git(
                self.upstream,
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "v3",
            )
            new_rev = git(self.upstream, "rev-parse", "HEAD")
            manifest = self.root / "sources.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(self.rev, new_rev),
                encoding="utf-8",
            )
            config = core.load_config(self.root)

            original_finalize = core._finalize_sync_quarantine

            def boom_finalize(*args, **kwargs):
                raise OSError("simulated finalize failure")

            with mock.patch.object(core, "_finalize_sync_quarantine", side_effect=boom_finalize):
                core.sync_assets(config, frozenset(("fixture/demo",)))

            lock_after = (self.root / "sources.lock.toml").read_text(encoding="utf-8")
            self.assertNotEqual(lock_after, lock_before)
            lock = core.load_lock(config, required=True)
            self.assertEqual(lock["fixture/demo"].rev, new_rev)
            cache = self.root / ".cache" / "sources" / "fixture" / new_rev / "demo" / "SKILL.md"
            self.assertTrue(cache.is_file())
            self.assertIn("# Demo v3", cache.read_text(encoding="utf-8"))

        self._run(exercise)

    def test_first_sync_pre_commit_failure_leaves_no_lock(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            (self.root / "sources.lock.toml").unlink()
            original_write = core.write_lock

            def boom_write(*args, **kwargs):
                raise core.SyncError("simulated first-sync lock failure")

            with mock.patch.object(core, "write_lock", side_effect=boom_write):
                with self.assertRaisesRegex(core.SyncError, "simulated first-sync"):
                    core.sync_assets(config, None)
            self.assertFalse((self.root / "sources.lock.toml").exists())

        self._run(exercise)

    def test_reader_lock_held_during_plan_changes(self) -> None:
        lock_state = {"held": False}

        @contextlib.contextmanager
        def tracking_lock(root):
            lock_state["held"] = True
            try:
                yield
            finally:
                lock_state["held"] = False

        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            original_load = core.load_lock

            def tracked_load(*args, **kwargs):
                self.assertTrue(lock_state["held"], "load_lock must run under reader lock")
                return original_load(*args, **kwargs)

            with mock.patch.object(core, "_exclusive_sync_lock", tracking_lock):
                with mock.patch.object(core, "load_lock", side_effect=tracked_load):
                    core.main(["--root", str(self.root), "diff"])

        self._run(exercise)

    def test_sync_does_not_double_enter_lock(self) -> None:
        enter_count = {"count": 0}

        @contextlib.contextmanager
        def counting_lock(root):
            enter_count["count"] += 1
            try:
                yield
            finally:
                enter_count["count"] -= 1

        def exercise() -> None:
            config = core.load_config(self.root)
            with mock.patch.object(core, "_exclusive_sync_lock", counting_lock):
                core.sync_assets(config, None)
            self.assertEqual(enter_count["count"], 0)

        self._run(exercise)

    def test_same_rev_pre_commit_failure_restores_cache(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            cache_file = (
                self.root / ".cache" / "sources" / "fixture" / self.rev / "demo" / "SKILL.md"
            )
            cache_before = cache_file.read_text(encoding="utf-8")
            lock_before = (self.root / "sources.lock.toml").read_text(encoding="utf-8")

            def boom_write(*args, **kwargs):
                raise core.SyncError("simulated lock write failure")

            with mock.patch.object(core, "write_lock", side_effect=boom_write):
                with self.assertRaisesRegex(core.SyncError, "simulated lock"):
                    core.sync_assets(config, frozenset(("fixture/demo",)))

            self.assertEqual(
                (self.root / "sources.lock.toml").read_text(encoding="utf-8"),
                lock_before,
            )
            self.assertTrue(cache_file.is_file())
            self.assertEqual(cache_file.read_text(encoding="utf-8"), cache_before)
            parent = cache_file.parent.parent
            self.assertFalse(
                any(".bak-" in path.name for path in parent.iterdir())
            )

        self._run(exercise)

    def test_load_config_rejects_casefold_catalog_targets(self) -> None:
        manifest = self.root / "sources.toml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8")
            + textwrap.dedent(
                """
                [[assets]]
                id = "fixture/demo-case"
                source = "fixture"
                kind = "skill"
                path = "skills/demo"
                target = "skills/Demo"
                """
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(core.SyncError, "重な|重複"):
            core.load_config(self.root)

    def test_load_config_rejects_casefold_harness_targets(self) -> None:
        manifest = self.root / "sources.toml"
        text = manifest.read_text(encoding="utf-8")
        # Drop fixture skills so harness basename collision is isolated.
        for asset_id in ('id = "fixture/demo"', 'id = "fixture/standalone"'):
            start = text.index(f"[[assets]]\n{asset_id}")
            end = text.find("[[assets]]", start + 1)
            text = text[:start] + (text[end:] if end != -1 else "")
        manifest.write_text(text, encoding="utf-8")
        # One on-disk dir is enough: case-insensitive FS still sees both keys as present,
        # and case-sensitive FS gets a second dir when possible.
        (self.root / "skills" / "demo").mkdir(parents=True)
        (self.root / "skills" / "demo" / "SKILL.md").write_text("# A\n", encoding="utf-8")
        demo_upper = self.root / "skills" / "Demo"
        if not demo_upper.exists():
            demo_upper.mkdir(parents=True)
            (demo_upper / "SKILL.md").write_text("# B\n", encoding="utf-8")
        (self.root / "assets.local.toml").write_text(
            textwrap.dedent(
                """
                [skills]
                Demo = true
                demo = true
                """
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(core.SyncError, "harness target|重な|重複"):
            core.load_config(self.root)

    def test_load_config_rejects_local_external_target_overlap(self) -> None:
        (self.root / "skills" / "demo").mkdir(parents=True)
        (self.root / "skills" / "demo" / "SKILL.md").write_text("# Local\n", encoding="utf-8")
        (self.root / "assets.local.toml").write_text(
            textwrap.dedent(
                """
                [skills]
                demo = true
                """
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(core.SyncError, "重な|重複"):
            core.load_config(self.root)

    def test_pi_context_absent_and_empty_are_idempotent(self) -> None:
        def exercise() -> None:
            manifest = self.root / "sources.toml"
            text = manifest.read_text(encoding="utf-8")
            start = text.index('[[assets]]\nid = "fixture/rule"')
            manifest.write_text(text[:start].rstrip() + "\n", encoding="utf-8")
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            lock = core.load_lock(config, required=True)

            pi_file = self.home / ".pi" / "agent" / "APPEND_SYSTEM.md"
            self.assertFalse(pi_file.exists())
            lines, operations, pi, applied = core.plan_changes(
                config, lock, ("context",), ("pi",)
            )
            self.assertFalse(any(line.startswith("[pi]") for line in lines))
            self.assertIsNone(pi)
            core.apply_changes(config, operations, pi, applied, kinds=("context",))
            self.assertFalse(pi_file.exists())

            pi_file.parent.mkdir(parents=True, exist_ok=True)
            pi_file.write_bytes(b"")
            lines, operations, pi, applied = core.plan_changes(
                config, lock, ("context",), ("pi",)
            )
            self.assertFalse(any(line.startswith("[pi]") for line in lines))
            self.assertIsNone(pi)
            core.apply_changes(config, operations, pi, applied, kinds=("context",))
            self.assertEqual(pi_file.read_bytes(), b"")

        self._run(exercise)

    def _commit_upstream(self, message: str, content: str) -> str:
        (self.upstream / "skills" / "demo" / "SKILL.md").write_text(
            content, encoding="utf-8"
        )
        git(self.upstream, "add", ".")
        git(
            self.upstream,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--quiet",
            "-m",
            message,
        )
        return git(self.upstream, "rev-parse", "HEAD")

    def test_update_advances_pin_and_syncs_cache(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            new_rev = self._commit_upstream(
                "bump",
                "---\nname: demo\ndescription: Use when testing.\n---\n# Demo v2\n",
            )

            code = core.update_sources(config, None)
            self.assertEqual(code, 0)

            updated = core.load_config(self.root)
            self.assertEqual(updated.sources["fixture"].rev, new_rev)
            lock = core.load_lock(updated, required=True)
            self.assertEqual(lock["fixture/demo"].rev, new_rev)
            cache = (
                self.root / ".cache" / "sources" / "fixture" / new_rev / "demo" / "SKILL.md"
            )
            self.assertTrue(cache.is_file())
            self.assertIn("# Demo v2", cache.read_text(encoding="utf-8"))
            core.validate(updated, lock)

        self._run(exercise)

    def test_update_noop_when_up_to_date(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            manifest_before = (self.root / "sources.toml").read_text(encoding="utf-8")
            lock_before = (self.root / "sources.lock.toml").read_text(encoding="utf-8")

            code = core.update_sources(config, None)
            self.assertEqual(code, 0)
            self.assertEqual(
                (self.root / "sources.toml").read_text(encoding="utf-8"),
                manifest_before,
            )
            self.assertEqual(
                (self.root / "sources.lock.toml").read_text(encoding="utf-8"),
                lock_before,
            )

        self._run(exercise)

    def test_update_source_option_and_unknown(self) -> None:
        def exercise() -> None:
            second = Path(self.temporary.name) / "upstream2"
            second.mkdir()
            git(second, "init", "--quiet")
            (second / "skills" / "other").mkdir(parents=True)
            (second / "skills" / "other" / "SKILL.md").write_text(
                "---\nname: other\ndescription: Other.\n---\n# Other\n",
                encoding="utf-8",
            )
            git(second, "add", ".")
            git(
                second,
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "other",
            )
            other_rev = git(second, "rev-parse", "HEAD")
            manifest = self.root / "sources.toml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8")
                + textwrap.dedent(
                    f"""
                    [[sources]]
                    id = "other"
                    url = {str(second).replace(os.sep, '/').__repr__()}
                    rev = "{other_rev}"
                    license = "MIT"

                    [[assets]]
                    id = "other/skill"
                    source = "other"
                    kind = "skill"
                    path = "skills/other"
                    target = "skills/other"
                    """
                ),
                encoding="utf-8",
            )
            config = core.load_config(self.root)
            core.sync_assets(config, None)

            fixture_new = self._commit_upstream(
                "fixture-only",
                "---\nname: demo\ndescription: Use when testing.\n---\n# Demo selected\n",
            )
            (second / "skills" / "other" / "SKILL.md").write_text(
                "---\nname: other\ndescription: Other.\n---\n# Other v2\n",
                encoding="utf-8",
            )
            git(second, "add", ".")
            git(
                second,
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "other-bump",
            )
            other_new = git(second, "rev-parse", "HEAD")

            code = core.main(
                ["--root", str(self.root), "update", "--source", "fixture"]
            )
            self.assertEqual(code, 0)
            updated = core.load_config(self.root)
            self.assertEqual(updated.sources["fixture"].rev, fixture_new)
            self.assertEqual(updated.sources["other"].rev, other_rev)
            self.assertNotEqual(other_rev, other_new)

            with self.assertRaisesRegex(core.SyncError, "未知の source"):
                core.update_sources(updated, frozenset(("missing",)))

        self._run(exercise)

    def test_rewrite_source_revs_preserves_unrelated_text(self) -> None:
        text = textwrap.dedent(
            f"""
            # keep me
            schema_version = 1

            [apply]
            default_kinds = ["skill"]

            [[sources]]
            id = "fixture"
            url = "https://example.invalid/fixture.git"
            rev = "{self.rev}"  # pinned
            license = "MIT"

            [[assets]]
            id = "fixture/demo"
            source = "fixture"
            kind = "skill"
            path = "skills/demo"
            """
        ).lstrip()
        new_rev = "0123456789abcdef0123456789abcdef01234567"
        rewritten = core._rewrite_source_revs(
            text, {"fixture": self.rev}, {"fixture": new_rev}
        )
        self.assertIn("# keep me", rewritten)
        self.assertIn('rev = "0123456789abcdef0123456789abcdef01234567"  # pinned', rewritten)
        self.assertIn('id = "fixture/demo"', rewritten)
        self.assertIn("[apply]", rewritten)

    def test_update_rolls_back_manifest_on_sync_failure(self) -> None:
        def exercise() -> None:
            config = core.load_config(self.root)
            core.sync_assets(config, None)
            manifest_before = (self.root / "sources.toml").read_text(encoding="utf-8")
            lock_before = (self.root / "sources.lock.toml").read_text(encoding="utf-8")
            cache_before = (
                self.root / ".cache" / "sources" / "fixture" / self.rev / "demo" / "SKILL.md"
            ).read_text(encoding="utf-8")

            self._commit_upstream(
                "boom",
                "---\nname: demo\ndescription: Use when testing.\n---\n# Demo boom\n",
            )

            original_promote = core._promote_path

            def boom_promote(source, destination):
                if destination.name == "demo":
                    raise core.SyncError("simulated promote failure")
                return original_promote(source, destination)

            with mock.patch.object(core, "_promote_path", side_effect=boom_promote):
                with self.assertRaisesRegex(core.SyncError, "simulated promote"):
                    core.update_sources(config, frozenset(("fixture",)))

            self.assertEqual(
                (self.root / "sources.toml").read_text(encoding="utf-8"),
                manifest_before,
            )
            self.assertEqual(
                (self.root / "sources.lock.toml").read_text(encoding="utf-8"),
                lock_before,
            )
            self.assertEqual(
                (
                    self.root
                    / ".cache"
                    / "sources"
                    / "fixture"
                    / self.rev
                    / "demo"
                    / "SKILL.md"
                ).read_text(encoding="utf-8"),
                cache_before,
            )
            restored = core.load_config(self.root)
            self.assertEqual(restored.sources["fixture"].rev, self.rev)

        self._run(exercise)


if __name__ == "__main__":
    unittest.main()
