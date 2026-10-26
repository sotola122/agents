"""Check Japanese research output and preservation of verbatim source excerpts."""

import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


SCRIPTS = Path(__file__).resolve().parents[2] / "skills/deepsearch/scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(f"deepsearch_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report = load("report")
watch = load("watch")
fetch = load("fetch")
chain = load("chain")


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
            (topic / "fetch-log.jsonl").write_text(
                json.dumps({"url": "https://example.test/paper", "name": "source",
                            "status": "OK", "file": "source.txt"},
                           ensure_ascii=False) + "\n",
                encoding="utf-8")
            with patch.object(sys, "argv", ["report.py", str(topic)]), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(report.main(), 0)
            output = topic / "report.html"
            page = output.read_text(encoding="utf-8")
            for expected in ('lang="ja"', "調査を区切った理由", "根拠あり", "前後を読む", "訳",
                             "元のページを開く", "https://example.test/paper",
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


class FetchSafetyTests(unittest.TestCase):
    def test_non_http_url_is_rejected_without_reading(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = Path(tmp) / "sources"
            sources.mkdir()
            secret = Path(tmp) / "secret.txt"
            secret.write_text("local secret\n" * 200, encoding="utf-8")
            for url in (secret.as_uri(), "FILE://" + secret.as_posix(),
                        "ftp://example.test/paper.txt", "-o/tmp/x"):
                with self.subTest(url=url), patch.object(fetch, "download") as download, \
                        contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(fetch.fetch_source(sources, "paper", url, sources), 1)
                download.assert_not_called()
                self.assertIn("http(s) の URL だけを取りに行く", output.getvalue())
                self.assertEqual(list(sources.iterdir()), [])

    def test_unsafe_names_are_rejected_before_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = Path(tmp) / "sources"
            sources.mkdir()
            for name in ("", ".", "..", "...", "   ", "../outside", "a/b", "a\\b",
                         "/outside", "C:\\outside", "C:outside", "CON", "a\x00b", "a\nb"):
                with self.subTest(name=name), patch.object(fetch, "download") as download, \
                        contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(
                        fetch.fetch_source(sources, name, "https://example.test/a", sources), 1)
                download.assert_not_called()
            self.assertEqual(list(sources.iterdir()), [])

    def test_japanese_path_and_query_are_encoded(self):
        seen = []

        def open_(req, timeout):
            seen.append(req.full_url)
            response = MagicMock()
            response.__enter__.return_value.read.return_value = b"body"
            response.__enter__.return_value.length = 0
            return response

        with patch.object(fetch, "resolve", return_value={"1.1.1.1"}), \
                patch.object(fetch._OPENER, "open", side_effect=open_):
            fetch.download("https://kotobank.jp/word/漆工芸")
            fetch.download("https://example.test/search?q=和竿&page=2")
            encoded = "https://kotobank.jp/word/%E6%BC%86%E5%B7%A5%E8%8A%B8"
            fetch.download(encoded)
        self.assertEqual(seen[0], "https://kotobank.jp/word/%E6%BC%86%E5%B7%A5%E8%8A%B8")
        self.assertEqual(seen[1], "https://example.test/search?q=%E5%92%8C%E7%AB%BF&page=2")
        self.assertEqual(seen[2], encoded)

    def test_short_japanese_pdf_uses_html_floor(self):
        text = "日本語の本文です。\n" * 150
        self.assertLess(len(text), fetch.MIN_TEXT_CHARS)
        self.assertGreater(len(text), fetch.MIN_HTML_CHARS)

        def convert(pdf):
            pdf.with_suffix(".txt").write_text(text, encoding="utf-8")
            return text

        with tempfile.TemporaryDirectory() as tmp:
            sources = Path(tmp)
            with patch.object(fetch, "resolve", return_value={"1.1.1.1"}), \
                    patch.object(fetch, "download", return_value=(b"%PDF-1.4\nshort", "application/pdf")), \
                    patch.object(fetch, "pdf_to_text", side_effect=convert), \
                    patch.object(fetch, "missing", return_value=[]), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    fetch.fetch_source(sources, "paper", "https://example.test/paper.pdf", sources), 0)
            self.assertEqual((sources / "paper.txt").read_text(encoding="utf-8"), text)

    def test_auto_captions_use_the_spoken_language(self):
        asked = []

        def yt_dlp(cmd, **kwargs):
            flag = next(c for c in cmd if c.startswith("--write-"))
            langs = cmd[cmd.index("--sub-langs") + 1]
            asked.append((flag, langs))
            self.assertLess(cmd.index("--"), len(cmd) - 1)
            tracks = {"en-orig": "English speech", "ja-orig": "吹き替え"} if flag == "--write-auto-subs" else {}
            folder = Path(cmd[cmd.index("-o") + 1]).parent
            for lang in langs.split(","):
                if lang in tracks:
                    (folder / f"v.{lang}.vtt").write_text(
                        f"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n{tracks[lang]}\n",
                        encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "Talk\tSpeaker\t20220820\ten-US\n", "")

        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(fetch, "run_tool", side_effect=yt_dlp):
            out = Path(tmp) / "talk.md"
            body = fetch.youtube_to_md("https://www.youtube.com/watch?v=example", out)
            text = out.read_text(encoding="utf-8")
        self.assertEqual(asked, [("--write-subs", "ja,en"), ("--write-auto-subs", "en-orig")])
        self.assertEqual(body, "[00:01] English speech")
        self.assertIn("Speaker / 20220820", text)
        self.assertNotIn("en-US", text.split("字幕:", 1)[0])


class ChainKeyTests(unittest.TestCase):
    def test_title_starting_with_w_is_searched(self):
        work = {"id": "https://openalex.org/W2073651707", "display_name": "Weak Bourbaki",
                "publication_year": 2004, "cited_by_count": 10, "doi": None,
                "best_oa_location": None}
        seen = []

        def get(path, **params):
            seen.append(path)
            return work if path.startswith("/works/") else {"results": [work]}

        with patch.object(chain, "get", side_effect=get), \
                patch.object(sys, "argv", ["chain.py", "find", "Weak", "Bourbaki"]), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(chain.main(), 0)
        self.assertEqual(seen, ["/works"])
        with patch.object(chain, "get", return_value={"results": [work]}) as get:
            self.assertEqual(chain.resolve("What is exploratory search"), work)
        self.assertEqual(get.call_args.args[0], "/works")

    def test_work_id_and_doi_resolve_directly(self):
        work = {"id": "https://openalex.org/W1", "display_name": "Paper",
                "publication_year": 2000, "cited_by_count": 1, "doi": "https://doi.org/10.1/x",
                "best_oa_location": None}

        def paths(*argv):
            seen = []

            def get(path, **params):
                seen.append(path)
                return work if path.startswith("/works/") else {"results": [work]}

            with patch.object(chain, "get", side_effect=get), \
                    patch.object(sys, "argv", ["chain.py", *argv]), \
                    contextlib.redirect_stdout(io.StringIO()):
                chain.main()
            return seen

        self.assertEqual(paths("find", "W2073651707"), ["/works/W2073651707"])
        self.assertEqual(paths("find", "10.1016/j.jalgebra.2004.01.001"),
                         ["/works/doi:10.1016/j.jalgebra.2004.01.001"])


class ExcerptBoundaryTests(unittest.TestCase):
    def quote(self, file, text="Original sentence"):
        return {"file": file, "line": 1, "text": text}

    def test_report_rejects_paths_outside_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            topic = Path(tmp) / "topic"
            sources = topic / "sources"
            sources.mkdir(parents=True)
            outside = topic / "outside.md"
            outside.write_text("Original sentence", encoding="utf-8")
            for file in ("../outside.md", str(outside), "C:\\outside.md", "\x00"):
                with self.subTest(file=file):
                    self.assertEqual(report.verify(sources, self.quote(file)), (False, [], 0, 0))

    def test_report_rejects_empty_excerpts_and_accepts_nested_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = Path(tmp) / "topic" / "sources"
            nested = sources / "archive"
            nested.mkdir(parents=True)
            (nested / "paper.md").write_text("Original sentence", encoding="utf-8")
            for text in ("", " \t\n ", "…", " …  … "):
                with self.subTest(text=text):
                    self.assertFalse(report.verify(sources, self.quote("archive/paper.md", text))[0])
            ok, context, _, _ = report.verify(sources, self.quote("archive/paper.md"))
            self.assertTrue(ok)
            self.assertIn("Original sentence", context)

    def test_line_numbers_must_fall_inside_the_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = Path(tmp) / "topic" / "sources"
            sources.mkdir(parents=True)
            (sources / "paper.md").write_text("Original sentence\n", encoding="utf-8")
            for line, end in ((0, None), (-1, None), (3, None), (1, 0), ("1", None)):
                quote = {"file": "paper.md", "line": line, "text": "Original sentence"}
                if end is not None:
                    quote["end"] = end
                with self.subTest(line=line, end=end):
                    self.assertFalse(report.verify(sources, quote)[0])
            self.assertTrue(report.verify(sources, {"file": "paper.md", "line": 1,
                                                     "end": None, "text": "Original sentence"})[0])

    def test_markdown_list_quotes_drop_markers_and_pdf_hyphens_stay(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = Path(tmp) / "topic" / "sources"
            sources.mkdir(parents=True)
            (sources / "notes.md").write_text("- first item\n- second item\n", encoding="utf-8")
            (sources / "dose.txt").write_text("- 5 mg\n- 10 mg\n", encoding="utf-8")
            spanned = {"line": 1, "end": 2, "text": "first item second item"}
            self.assertTrue(report.verify(sources, {"file": "notes.md", **spanned})[0])
            self.assertFalse(report.verify(sources, {"file": "dose.txt", "line": 1, "end": 2,
                                                      "text": "5 mg 10 mg"})[0])
            self.assertTrue(report.verify(sources, {"file": "dose.txt", "line": 1, "end": 2,
                                                     "text": "5 mg - 10 mg"})[0])

    def test_save_refuses_to_replace_a_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "sources"
            staging = Path(tmp) / "staging"
            destination.mkdir()
            staging.mkdir()
            (destination / "paper.md").mkdir()
            saved = staging / "paper.md"
            saved.write_text("original text\n", encoding="utf-8")
            with self.assertRaises(IsADirectoryError):
                fetch.save_verified(saved, saved, destination)
            self.assertTrue((destination / "paper.md").is_dir())
            self.assertTrue(saved.is_file())


class UntrustedInputTests(unittest.TestCase):
    def test_private_and_non_http_urls_are_refused(self):
        self.assertIn("手元や内側", fetch.url_problem("http://127.0.0.1/secret"))
        self.assertIn("http(s)", fetch.url_problem("file:///etc/passwd"))
        with patch.object(fetch, "resolve", return_value={"1.1.1.1"}):
            self.assertIsNone(fetch.url_problem("https://example.test/paper"))
        with patch.dict("os.environ", {"DEEPSEARCH_ALLOW_PRIVATE": "1"}):
            self.assertIsNone(fetch.url_problem("http://127.0.0.1/secret"))
            self.assertIn("http(s)", fetch.url_problem("file:///etc/passwd"))

    def test_connect_time_resolution_refuses_a_private_address(self):
        with patch.object(fetch, "resolve", return_value=["127.0.0.1"]):
            with self.assertRaises(fetch.UnsafeURL) as caught:
                fetch._pinned_connection("example.test", 443, 5, None)
        self.assertIn("手元や内側", str(caught.exception))
        self.assertEqual(
            fetch._connect_order(["2001:db8::1", "2001:db8::2", "1.1.1.1"]),
            ["2001:db8::1", "1.1.1.1", "2001:db8::2"])
        self.assertEqual(
            fetch.pmc_id("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2655834/"),
            "PMC2655834")
        self.assertIsNone(fetch.pmc_id("https://example.test/pmc/articles/PMC1"))

    def test_ocr_language_and_unused_note(self):
        listed = subprocess.CompletedProcess(
            ["tesseract"], 0, "List of available languages:\neng\njpn\njpn_vert\n", "")
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DEEPSEARCH_OCR_LANG", None)
            with patch.object(fetch, "run_tool", return_value=listed):
                self.assertEqual(fetch.ocr_langs(), "jpn+jpn_vert+eng")
        with patch.dict(os.environ, {"DEEPSEARCH_OCR_LANG": "jpn+eng"}):
            self.assertEqual(fetch.ocr_langs(), "jpn+eng")
        with patch.dict(os.environ, {"DEEPSEARCH_OCR_LANG": "eng;rm"}), \
                patch.object(fetch, "run_tool", return_value=listed), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(fetch.ocr_langs(), "jpn+jpn_vert+eng")
        with patch.object(fetch, "ocr_pdf", return_value=("", "確信度が低い")):
            text, note = fetch.ocr_if_longer(Path("paper.pdf"), "extracted")
        self.assertEqual((text, note), ("extracted", "確信度が低い"))

    def test_youtube_detection_uses_the_host(self):
        self.assertTrue(fetch.is_youtube("https://www.youtube.com/watch?v=abc"))
        self.assertTrue(fetch.is_youtube("https://youtu.be/abc"))
        self.assertFalse(fetch.is_youtube("https://evil.example/?next=youtu.be/abc"))
        self.assertFalse(fetch.is_youtube("https://www.youtube.com/feed/library"))

    def test_doctype_feed_is_refused_and_gzip_is_inflated(self):
        payload = b"<?xml version='1.0'?><!DOCTYPE rss [<!ENTITY x 'y'>]><rss></rss>"
        with self.assertRaises(ValueError):
            watch.items(payload)
        import gzip
        body = gzip.compress(b"<rss><channel></channel></rss>")
        self.assertTrue(watch.gunzip(body).startswith(b"<rss>"))

    def test_chain_output_strips_control_characters_and_lists_authors(self):
        work = {"id": "https://openalex.org/W1", "display_name": "Title\twith\nbreak",
                "publication_year": 2000, "cited_by_count": 1, "doi": None,
                "best_oa_location": None}
        self.assertEqual(len(chain.row(work).split("\t")), 6)
        self.assertNotIn("\n", chain.row(work))
        authors = [
            {"id": "https://openalex.org/A1", "display_name": "Ada", "works_count": 2,
             "last_known_institutions": []},
            {"id": "https://openalex.org/A2", "display_name": "Ada Other", "works_count": 9,
             "last_known_institutions": []},
        ]

        def get(path, **params):
            if path == "/authors":
                return {"results": authors}
            if path.startswith("/authors/"):
                return authors[0]
            return {"results": [work], "meta": {"count": 1}}

        with patch.object(chain, "get", side_effect=get), \
                patch.object(sys, "argv", ["chain.py", "author", "Ada"]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(chain.main(), 0)
        text = output.getvalue()
        self.assertIn("# author Ada A1", text)
        self.assertIn("# 別の候補 Ada Other A2", text)
        self.assertIn("chain.py author A2", text)


if __name__ == "__main__":
    unittest.main()
