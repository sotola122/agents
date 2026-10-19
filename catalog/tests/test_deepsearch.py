"""Check Japanese research output and preservation of verbatim source excerpts."""

import contextlib
import datetime as dt
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[2] / "skills/deepsearch/scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(f"deepsearch_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report = load("report")
watch = load("watch")


class DeepsearchTests(unittest.TestCase):
    def test_japanese_report_preserves_and_verifies_original_quote(self):
        original = "The measurement was repeated three times."
        translation = "測定は3回繰り返された。"
        data = {
            "title": "測定方法の調査",
            "question": "測定を何回行ったか",
            "stopped": "要る主張の全部に原文の場所が付いた",
            "claims": [{
                "claim": "測定回数", "status": "付いた",
                "quotes": [{"file": "source.txt", "line": 1,
                            "text": original, "ja": translation}],
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            topic = Path(tmp) / ".research/measurements"
            (topic / "sources").mkdir(parents=True)
            source = topic / "sources/source.txt"
            source.write_text(original + "\n", encoding="utf-8")
            extracts = topic / "extracts.json"
            extracts.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with patch.object(sys, "argv", ["report.py", str(topic)]), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(report.main(), 0)
            output = topic / "report.html"
            page = output.read_text(encoding="utf-8")
            for expected in ('lang="ja"', "止めた理由", "前後を読む", "訳",
                             original, translation, "deepsearch"):
                self.assertIn(expected, page)
            self.assertEqual(source.read_text(encoding="utf-8"), original + "\n")

            output.unlink()
            data["claims"][0]["quotes"][0]["text"] = "The measurement was repeated ten times."
            extracts.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with patch.object(sys, "argv", ["report.py", str(topic)]), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(report.main(), 1)
            self.assertFalse(output.exists())

    def test_watch_uses_japanese_labels_and_keeps_source_text(self):
        entry = {"title": "Original title", "link": "https://example.test/item",
                 "date": dt.datetime.now(dt.timezone.utc), "head": "Original opening text."}
        with tempfile.TemporaryDirectory() as tmp:
            topic = Path(tmp) / ".research/updates"
            topic.mkdir(parents=True)
            (topic / "watch.tsv").write_text(
                "feed\t公式ブログ\thttps://example.test/feed\thttps://example.test/\n",
                encoding="utf-8")
            with patch.object(watch, "fetch", return_value=(b"", "application/atom+xml")), \
                    patch.object(watch, "items", return_value=[entry]), \
                    contextlib.redirect_stdout(io.StringIO()):
                watch.cmd_check(topic, 14, False)
                first = next((topic / "watch").glob("*.md")).read_text(encoding="utf-8")
                watch.cmd_check(topic, 14, False)
            self.assertIn("# 新着", first)
            self.assertIn("Original title", first)
            self.assertIn("> Original opening text.", first)
            results = list((topic / "watch").glob("*.md"))
            self.assertEqual(len(results), 2)
            self.assertTrue(any("新着なし" in p.read_text(encoding="utf-8") for p in results))


if __name__ == "__main__":
    unittest.main()
