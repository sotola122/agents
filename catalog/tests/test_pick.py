from __future__ import annotations

import unittest

from catalog.pick import HARNESS_GROUP, Item, Picker, render


def item(section: str, key: str, group: str, on: bool) -> Item:
    return Item(section, key, key.rsplit("/", 1)[-1], group, on, on, key)


def sample() -> Picker:
    return Picker([
        item("apply", "cursor", HARNESS_GROUP, True),
        item("apply", "omp", HARNESS_GROUP, False),
        item("external", "mattpocock/tdd", "skill: mattpocock", True),
        item("external", "mattpocock/writing-beats", "skill: mattpocock", False),
        item("external", "mattpocock/writing-shape", "skill: mattpocock", False),
        item("skills", "pi", "skill: local", False),
    ])


def press(picker: Picker, *keys: str) -> str | None:
    result = None
    for key in keys:
        result = picker.handle(key)
    return result


class PickerTests(unittest.TestCase):
    def test_changes_cover_harnesses_and_assets(self) -> None:
        picker = sample()
        # cursor off, omp on, then tdd off.
        press(picker, "space", "j", "space", "j", "space")
        self.assertEqual(picker.changes(), {
            "apply": {"harnesses": ["omp"]},
            "external": {"mattpocock/tdd": False},
        })
        self.assertEqual(picker.removed_harnesses(), ["cursor"])
        self.assertEqual(picker.describe_changes(), [
            "off -H cursor", "on -H omp", "off: mattpocock/tdd",
        ])
        self.assertEqual(press(picker, "enter"), "save")

    def test_filter_limits_group_toggle_to_matches(self) -> None:
        picker = sample()
        press(picker, "/", "w", "r", "i", "t", "enter", "a")
        self.assertEqual(picker.changes(), {"external": {
            "mattpocock/writing-beats": True, "mattpocock/writing-shape": True,
        }})
        # Esc in filter mode clears the query and shows everything again.
        press(picker, "/", "esc")
        self.assertEqual(len(picker.visible()), 6)

    def test_save_requires_a_harness_and_quit_discards(self) -> None:
        picker = sample()
        self.assertIsNone(press(picker, "space", "enter"))
        self.assertIn("配布先", picker.message)
        self.assertEqual(press(picker, "q"), "quit")

    def test_tab_jumps_to_next_group(self) -> None:
        picker = sample()
        press(picker, "tab")
        self.assertEqual(picker.items[picker.current()].key, "mattpocock/tdd")
        press(picker, "tab", "tab")
        self.assertEqual(picker.items[picker.current()].key, "cursor")

    def test_render_scrolls_to_cursor(self) -> None:
        items = [item("apply", "cursor", HARNESS_GROUP, True)] + [
            item("external", f"x/skill-{n:02d}", "skill: x", False) for n in range(40)
        ]
        picker = Picker(items)
        press(picker, "pgdn", "pgdn", "pgdn")
        lines = render(picker, 60, 10)
        self.assertEqual(len(lines), 9)
        cursor = [text for text, style in lines if style == "cursor"]
        self.assertEqual(cursor, ["  [ ] skill-29"])
