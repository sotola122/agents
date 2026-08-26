from __future__ import annotations

from pathlib import Path
import re
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ("pi", "codex", "cursor")
LINK_RE = re.compile(r"\[[^]]+\]\((?!https?://|#)([^)]+)\)")


class DelegationSkillTests(unittest.TestCase):
    def test_package_names_match_directories(self) -> None:
        for name in PACKAGES:
            skill = ROOT / "skills" / name / "SKILL.md"
            self.assertTrue(skill.is_file(), name)
            self.assertTrue(
                skill.read_text(encoding="utf-8").startswith(
                    f"---\nname: {name}\n"
                ),
                name,
            )

    def test_package_links_resolve(self) -> None:
        for name in PACKAGES:
            package = ROOT / "skills" / name
            text = (package / "SKILL.md").read_text(encoding="utf-8")
            for relative in LINK_RE.findall(text):
                self.assertTrue((package / relative).exists(), f"{name}: {relative}")

    def test_packages_are_cli_only(self) -> None:
        forbidden = (
            "prompts/",
            "profiles.yaml",
            "provider.yaml",
            "modalities.yaml",
            "acceptance_checks",
            "task block",
            "output heading",
        )
        for name in PACKAGES:
            package = ROOT / "skills" / name
            files = {
                path.relative_to(package).as_posix()
                for path in package.rglob("*")
                if path.is_file()
            }
            self.assertEqual(files, {"SKILL.md"}, name)

            text = (package / "SKILL.md").read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{name}: {token}")

    def test_codex_exec_only_flags_are_scoped(self) -> None:
        text = (ROOT / "skills" / "codex" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("The following controls are `codex exec` only", text)
        self.assertIn("`codex review` does not accept them", text)

    def test_obsolete_package_directories_are_absent(self) -> None:
        self.assertFalse((ROOT / "skills" / "delegate-pi").exists())
        self.assertFalse((ROOT / "skills" / "delegate-codex").exists())

    def test_local_asset_example_enables_current_names(self) -> None:
        with (ROOT / "assets.local.toml.example").open("rb") as stream:
            skills = tomllib.load(stream)["skills"]

        for name in PACKAGES:
            self.assertIs(skills.get(name), True, name)
        self.assertNotIn("delegate-pi", skills)
        self.assertNotIn("delegate-codex", skills)

    def test_anago_codex_is_excluded_only_from_hermes(self) -> None:
        with (ROOT / "sources.toml").open("rb") as stream:
            apply = tomllib.load(stream)["apply"]

        self.assertEqual(apply["local_skill_excludes"], {"hermes": ["codex"]})

    def test_official_herdr_skill_is_pinned_and_enabled(self) -> None:
        with (ROOT / "sources.toml").open("rb") as stream:
            catalog = tomllib.load(stream)
        with (ROOT / "assets.local.toml.example").open("rb") as stream:
            enabled = tomllib.load(stream)["external"]

        source = next(item for item in catalog["sources"] if item["id"] == "herdr")
        self.assertEqual(source["url"], "https://github.com/herdrdev/herdr.git")
        self.assertEqual(source["rev"], "9eb521456ac0d19d3ab3d9d7cea3cca10baa8a4c")
        self.assertEqual(source["license"], "Apache-2.0")

        asset = next(
            item for item in catalog["assets"] if item["id"] == "herdrdev/herdr"
        )
        self.assertEqual(asset["source"], "herdr")
        self.assertEqual(asset["kind"], "skill")
        self.assertEqual(asset["path"], "skills/herdr")
        self.assertEqual(asset["target"], "skills/herdr")
        self.assertIs(enabled["herdrdev/herdr"], True)

    def test_unslop_skill_is_pinned_as_repo_root_export(self) -> None:
        with (ROOT / "sources.toml").open("rb") as stream:
            catalog = tomllib.load(stream)
        with (ROOT / "assets.local.toml.example").open("rb") as stream:
            enabled = tomllib.load(stream)["external"]

        source = next(item for item in catalog["sources"] if item["id"] == "unslop")
        self.assertEqual(source["url"], "https://github.com/theclaymethod/unslop.git")
        self.assertEqual(source["rev"], "d81f5196167ded24f46fced04958c0c12d681798")
        self.assertEqual(source["license"], "MIT")

        asset = next(
            item for item in catalog["assets"] if item["id"] == "theclaymethod/unslop"
        )
        self.assertEqual(asset["source"], "unslop")
        self.assertEqual(asset["kind"], "skill")
        self.assertEqual(asset["path"], ".")
        self.assertEqual(asset["target"], "skills/unslop")
        self.assertIs(enabled["theclaymethod/unslop"], True)


if __name__ == "__main__":
    unittest.main()
