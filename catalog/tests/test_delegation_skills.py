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


if __name__ == "__main__":
    unittest.main()
