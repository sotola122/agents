from __future__ import annotations

from pathlib import Path
import re
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ("pi", "codex", "cursor")
LINK_RE = re.compile(r"\[[^]]+\]\((?!https?://|#)([^)]+)\)")
CURSOR_FILES = {
    "profiles.yaml",
    "prompts/smoke.md",
    "prompts/review.md",
    "prompts/verify.md",
    "prompts/implement.md",
    "prompts/append/adversarial.md",
}


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

    def test_obsolete_package_directories_are_absent(self) -> None:
        self.assertFalse((ROOT / "skills" / "delegate-pi").exists())
        self.assertFalse((ROOT / "skills" / "delegate-codex").exists())

    def test_cursor_companion_files_exist(self) -> None:
        package = ROOT / "skills" / "cursor"
        missing = sorted(path for path in CURSOR_FILES if not (package / path).is_file())
        self.assertEqual(missing, [])

    def test_cursor_skill_pins_workspace_and_preserves_dirty_state(self) -> None:
        text = (ROOT / "skills" / "cursor" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn('--workspace "$WORKSPACE"', text)
        self.assertIn("dirty.patch", text)
        self.assertIn("archive untracked", text)
        self.assertIn("compare the reconstructed manifest", text)

    def test_local_asset_example_enables_current_names(self) -> None:
        with (ROOT / "assets.local.toml.example").open("rb") as stream:
            skills = tomllib.load(stream)["skills"]

        for name in PACKAGES:
            self.assertIs(skills.get(name), True, name)
        self.assertNotIn("delegate-pi", skills)
        self.assertNotIn("delegate-codex", skills)


if __name__ == "__main__":
    unittest.main()
