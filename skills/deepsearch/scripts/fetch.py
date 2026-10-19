#!/usr/bin/env python3
"""Download one original source and validate it before saving it in sources/.

Check content signatures and extracted length: a successful HTTP request or a
filename extension does not distinguish an original from an error or login page.
Save papers and practitioner accounts. YouTube captions become timestamped
Markdown; X returns FAIL because its original text requires login.

Usage:
    fetch.py <sources_dir> <name> <url>
Output (one tab-separated line):
    OK   <name> <saved_file> <character_count> <first_line>
    FAIL <name> <reason>
"""

import codecs
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

# Minimum readable length; error and login pages are often short.
# Use a higher floor for papers and a lower one for short Japanese articles.
# An upstream trial rejected a genuine 2,904-character article at 3,000.
MIN_TEXT_CHARS = 3000
MIN_HTML_CHARS = 1000
MAX_BYTES = 40_000_000
# Access-barrier phrases, matched case-insensitively.
WALL_PATTERNS = (
    "404 not found",
    "page not found",
    "access denied",
    "you do not currently have access",
    "sign in to continue",
    "log in to continue",
    "enable javascript",
    "are you a robot",
    "captcha",
)


class _Redirect308(urllib.request.HTTPRedirectHandler):
    """Follow HTTP 308 redirects on Python 3.10 too.

    Python 3.10 lacks both the 308 handler and redirect_request support added in 3.11.
    Treat 308 as 307: both retain the request method when following the new URL.
    """

    http_error_308 = urllib.request.HTTPRedirectHandler.http_error_302

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, 307 if code == 308 else code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_Redirect308)


def download(url: str) -> tuple[bytes, str]:
    """Fetch a URL and return its body and Content-Type."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 deepsearch"})
    with _OPENER.open(req, timeout=90) as res:
        return res.read(MAX_BYTES), res.headers.get("Content-Type", "")


# Many Shift_JIS pages contain Windows extensions; decode with compatible cp932.
_CHARSET_ALIASES = {"shift_jis": "cp932", "shift-jis": "cp932", "sjis": "cp932", "x-sjis": "cp932",
                    "windows-31j": "cp932", "ms_kanji": "cp932"}


def _declared_charsets(body: bytes, ctype: str) -> list[str]:
    """Return charset declarations from Content-Type, then HTML metadata."""
    found = re.findall(r"charset\s*=\s*[\"']?([\w.:-]+)", ctype or "", re.I)
    # Inspect the first 4096 bytes for metadata (the HTML limit is 1024 bytes).
    found += re.findall(rb"<meta[^>]*charset\s*=\s*[\"']?([\w.:-]+)", body[:4096], re.I)
    names = [(n.decode("ascii", "ignore") if isinstance(n, bytes) else n).lower() for n in found]
    return [_CHARSET_ALIASES.get(n, n) for n in names]


def decode_text(body: bytes, ctype: str = "") -> str:
    """Decode text using declared encodings, UTF-8, then common Japanese encodings.

    Accept the first strict decoding that succeeds. If every candidate fails, choose
    the decoding with the fewest replacement characters. Declarations can be wrong.
    """
    candidates = []
    for name in [*_declared_charsets(body, ctype), "utf-8", "cp932", "euc_jp"]:
        try:
            codec = codecs.lookup(name).name
        except LookupError:  # Skip unknown charset declarations such as x-user-defined.
            continue
        if codec not in candidates:
            candidates.append(codec)
    for codec in candidates:
        try:
            return body.decode(codec)
        except UnicodeDecodeError:
            continue
    return min((body.decode(c, errors="replace") for c in candidates), key=lambda t: t.count("�"))


def missing(*commands: str) -> list[str]:
    """Return missing external commands so callers can report them without crashing."""
    return [c for c in commands if shutil.which(c) is None]


def pdf_to_text(pdf: Path) -> str:
    """Extract text with layout and explicit UTF-8 for stable source line references.

    Xpdf defaults to Latin-1; both Xpdf and Poppler accept -enc UTF-8.
    """
    if missing("pdftotext"):
        return ""
    out = pdf.with_suffix(".txt")
    subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), str(out)], check=False,
                   stderr=subprocess.DEVNULL)
    return out.read_text(encoding="utf-8", errors="replace") if out.exists() else ""


def ocr_pdf(pdf: Path) -> str:
    """OCR image-only PDFs with local pdftoppm and tesseract.

    Render at 200 dpi and use English language data. Label extracted text as OCR so
    readers can check quotations against the PDF. Return empty text if tools are absent.
    """
    if missing("pdftoppm", "tesseract"):
        return ""
    tmp = pdf.parent / f".{pdf.stem}-ocr"
    tmp.mkdir(exist_ok=True)
    subprocess.run(["pdftoppm", "-r", "200", "-png", str(pdf), str(tmp / "p")],
                   check=False, stderr=subprocess.DEVNULL)
    pages = []
    for img in sorted(tmp.glob("p-*.png")):
        res = subprocess.run(["tesseract", str(img), "-", "-l", "eng"],
                             capture_output=True, encoding="utf-8", errors="replace")
        pages.append(f"=== page {img.stem.split('-')[-1]} ===\n{res.stdout}")
        img.unlink()
    tmp.rmdir()
    text = "\n".join(pages)
    out = pdf.with_suffix(".txt")
    out.write_text("（OCR で起こした本文。誤りが残るので、引用は原本の PDF で確かめる）\n\n" + text,
                   encoding="utf-8")
    return text


HAS_AX = shutil.which("ax") is not None


class _TextExtractor(HTMLParser):
    """Extract HTML text when ax is unavailable, preserving Markdown links.

    Prefer a sufficiently long main/article body. Otherwise include all readable
    text, potentially including navigation and footers. Links support backward chaining.
    """

    FOCUS = {"main", "article"}

    SKIP = {"script", "style", "noscript", "svg", "template", "iframe"}
    BLOCK = {"p", "div", "section", "article", "main", "header", "footer", "nav", "aside",
             "li", "tr", "br", "hr", "pre", "blockquote", "table", "ul", "ol", "dl", "dt", "dd",
             "figure", "figcaption"}
    HEADING = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### ", "h5": "##### ", "h6": "###### "}

    def __init__(self, base: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base = base
        self.parts: list[str] = []
        self.skip = 0
        self.href: str | None = None
        self.link_text: list[str] = []
        self.focus = 0
        self.focus_parts: list[str] = []

    def _emit(self, piece: str) -> None:
        self.parts.append(piece)
        if self.focus:
            self.focus_parts.append(piece)

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif self.skip:
            return
        elif tag in self.FOCUS:
            self.focus += 1
        elif tag in self.HEADING:
            self._emit("\n\n" + self.HEADING[tag])
        elif tag in self.BLOCK:
            self._emit("\n")
        elif tag == "a":
            href = dict(attrs).get("href")
            if href and not href.startswith(("#", "javascript:")):
                self.href = urllib.parse.urljoin(self.base, href)
                self.link_text = []

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif self.skip:
            return
        elif tag in self.FOCUS:
            self.focus = max(0, self.focus - 1)
        elif tag in self.HEADING or tag in self.BLOCK:
            self._emit("\n")
        elif tag == "a" and self.href is not None:
            text = " ".join("".join(self.link_text).split())
            self._emit(f"[{text}]({self.href})" if text else "")
            self.href = None

    def handle_data(self, data):
        if self.skip:
            return
        if self.href is not None:
            self.link_text.append(data)
        else:
            self._emit(data)

    def text(self) -> str:
        focused = "".join(self.focus_parts)
        # Fall back to the full page when main contains only a thin shell.
        raw = focused if len(focused.strip()) >= MIN_HTML_CHARS else "".join(self.parts)
        lines = (" ".join(line.split()) for line in raw.splitlines())
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


def html_to_md(url: str, out: Path, body: bytes | None = None, ctype: str = "") -> str:
    """Convert original text to Markdown without summarizing it.

    Use ax --all when installed, otherwise the standard-library extractor. Reuse a
    provided body to avoid downloading twice; ctype carries its charset declaration.
    """
    if HAS_AX:
        res = subprocess.run(["ax", url, "--md", "--all"], capture_output=True,
                             encoding="utf-8", errors="replace")
        text = res.stdout
    else:
        if body is None:
            body, ctype = download(url)
        if body[:5] == b"%PDF-":
            # Signal a redirected PDF so the caller re-fetches the raw bytes.
            text = "%PDF"
        else:
            parser = _TextExtractor(url)
            parser.feed(decode_text(body, ctype))
            text = parser.text()
    out.write_text(text, encoding="utf-8")
    return text


def ax_save(url: str, out: Path) -> bool:
    """Save the raw response and return whether a nonempty file was written.

    Some sites return HTML to urllib but redirect ax to a PDF. Re-fetch that response
    as bytes rather than saving decoded PDF data as Markdown. Fall back to urllib.
    """
    if HAS_AX:
        subprocess.run(["ax", url, "-o", str(out)], capture_output=True)
    else:
        try:
            out.write_bytes(download(url)[0])
        except Exception:  # Let the caller report FAIL if fetching fails.
            return False
    return out.exists() and out.stat().st_size > 0


YOUTUBE = re.compile(r"(youtube\.com/(watch|shorts|live)|youtu\.be/)")
X_POST = re.compile(r"^https?://(www\.)?(x|twitter)\.com/")
# Short video captions need a lower minimum length than papers.
MIN_TRANSCRIPT_CHARS = 300


def youtube_to_md(url: str, out: Path) -> str:
    """Download captions only with yt-dlp and preserve timestamps.

    Prefer manual captions, then automatic captions; prefer Japanese, then English.
    Drop consecutive duplicate lines. Label automatic captions so readers can check
    errors against the video. Try manual and automatic downloads separately because
    their filenames coincide. Force UTF-8 for metadata piped on Windows.
    """
    tmp = out.parent / f".{out.stem}-subs"
    tmp.mkdir(exist_ok=True)
    kind = "手動"
    for flag in ("--write-subs", "--write-auto-subs"):
        meta = subprocess.run(
            ["yt-dlp", "--no-update", "--skip-download", flag, "--encoding", "utf-8",
             "--sub-langs", "ja,en", "--sub-format", "vtt", "--no-simulate",
             "--print", "%(title)s\t%(uploader)s\t%(upload_date)s",
             "-o", str(tmp / "v.%(ext)s"), url],
            capture_output=True, encoding="utf-8", errors="replace")
        if any(tmp.glob("*.vtt")):
            break
        kind = "自動（誤変換あり・引用は動画で確かめる）"
    vtts = sorted(tmp.glob("*.vtt"), key=lambda p: (".ja" not in p.name, p.name))
    lines, last = [], ""
    if vtts:
        stamp = "00:00"
        for raw in vtts[0].read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"(\d\d):(\d\d):(\d\d)\.\d+ -->", raw)
            if m:
                h, mi, s = (int(x) for x in m.groups())
                stamp = f"{h * 60 + mi:02d}:{s:02d}"
                continue
            text = re.sub(r"<[^>]+>", "", raw).strip()
            if not text or text in ("WEBVTT",) or text.startswith(("Kind:", "Language:")):
                continue
            if text != last:
                lines.append(f"[{stamp}] {text}")
                last = text
    for p in tmp.iterdir():
        p.unlink()
    tmp.rmdir()
    head = meta.stdout.strip().split("\t")
    title = head[0] if head and head[0] else url
    info = " / ".join(head[1:]) if len(head) > 1 else ""
    body = "\n".join(lines)
    out.write_text(f"# {title}\n\n{url}\n{info}\n字幕: {kind + ' ' + vtts[0].name if vtts else 'なし'}\n\n{body}\n",
                   encoding="utf-8")
    return body


def first_line(text: str) -> str:
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if len(line) > 8:
            return line[:100]
    return ""


def save_verified(saved: Path, kept: Path, destination: Path) -> Path:
    """Move only validated files to the destination on the same filesystem."""
    if saved != kept:
        saved.replace(destination / saved.name)
    target = destination / kept.name
    kept.replace(target)
    return target


def fetch_source(sources: Path, name: str, url: str, destination: Path) -> int:
    """Stage this fetch separately; preserve existing sources during validation."""

    if X_POST.match(url):
        print(f"FAIL\t{name}\tX はログインの壁で本文が取れない（URL を map.md に残す）")
        return 1
    if YOUTUBE.search(url):
        if missing("yt-dlp"):
            print(f"FAIL\t{name}\tyt-dlp が無いので字幕を落とせない")
            return 1
        kept = sources / f"{name}.md"
        body = youtube_to_md(url, kept)
        if len(body) < MIN_TRANSCRIPT_CHARS:
            kept.unlink(missing_ok=True)
            print(f"FAIL\t{name}\t字幕が無いか短すぎる（{len(body)}文字）")
            return 1
        kept = save_verified(kept, kept, destination)
        print(f"OK\t{name}\t{kept}\t{len(body)}\t{first_line(body)}")
        return 0

    try:
        body, ctype = download(url)
    except Exception as e:  # HTTP and connection errors both mean the source could not be fetched.
        print(f"FAIL\t{name}\t{type(e).__name__}: {e}")
        return 1

    if not body.strip():
        # Some servers return empty bodies with successful 200/202 status codes.
        # A browser-only challenge may require the user to open the public page.
        print(f"FAIL\t{name}\t空の応答（ボット対策の可能性・ブラウザで開けば読めるかも）")
        return 1
    if body[:5] == b"%PDF-":
        saved = sources / f"{name}.pdf"
        saved.write_bytes(body)
        text = pdf_to_text(saved)
        kept = saved.with_suffix(".txt")
        if len(text.strip()) < 200 and not re.search(r"arxiv\.org", url):
            text = ocr_pdf(saved)  # OCR image-only PDFs; try arXiv HTML below instead.
    elif ctype.startswith(("text/plain", "text/markdown", "application/json", "text/csv")):
        # Raw GitHub README files and datasets use these content types.
        # Preserve their original text without HTML conversion.
        # Check this before HTML: Markdown can begin with an HTML comment.
        # Misclassifying such Markdown through ax can discard its line breaks.
        ext = ".json" if "json" in ctype else ".csv" if "csv" in ctype else ".md"
        kept = saved = sources / f"{name}{ext}"
        text = decode_text(body, ctype)
        kept.write_text(text, encoding="utf-8")
    elif "html" in ctype or body.lstrip()[:1] == b"<":
        kept = sources / f"{name}.md"
        text = html_to_md(url, kept, body, ctype)
        saved = kept
        # ax followed an HTML URL to a PDF; re-fetch it as PDF bytes.
        if text.lstrip().startswith("%PDF"):
            kept.unlink(missing_ok=True)
            saved = sources / f"{name}.pdf"
            if ax_save(url, saved) and saved.read_bytes()[:5] == b"%PDF-":
                text = pdf_to_text(saved)
                kept = saved.with_suffix(".txt")
                if len(text.strip()) < 200:
                    text = ocr_pdf(saved)
            else:
                saved.unlink(missing_ok=True)
                print(f"FAIL\t{name}\t転送先の PDF を保存できなかった")
                return 1
    else:
        print(f"FAIL\t{name}\t扱えない形式: {ctype or '不明'}")
        return 1

    # Some arXiv PDFs yield no text through pdftotext.
    # Try the same paper as HTML only when the extracted text is too short.
    arxiv_id = re.search(r"arxiv\.org/(?:pdf|abs)/(\d{4}\.\d{4,5}(?:v\d+)?)", url)
    if arxiv_id and len(text) < MIN_TEXT_CHARS:
        for p in (saved, kept):
            p.unlink(missing_ok=True)
        kept = saved = sources / f"{name}.md"
        text = html_to_md(f"https://arxiv.org/html/{arxiv_id.group(1)}", kept)

    floor = MIN_TEXT_CHARS if saved.suffix == ".pdf" else MIN_HTML_CHARS
    head = text[:4000].lower()
    wall = next((p for p in WALL_PATTERNS if p in head), None)
    if len(text) < floor or (wall and len(text) < MIN_TEXT_CHARS * 4):
        for p in (saved, kept):
            p.unlink(missing_ok=True)
        reason = f"壁に当たった（{wall}）" if wall else f"本文が短すぎる（{len(text)}文字）"
        # Missing PDF extraction commands often explain a short result.
        lacking = missing("pdftotext", "pdftoppm", "tesseract") if saved.suffix == ".pdf" else []
        if lacking:
            reason += f"。{'・'.join(lacking)} が無い"
        print(f"FAIL\t{name}\t{reason}")
        return 1

    kept = save_verified(saved, kept, destination)
    print(f"OK\t{name}\t{kept}\t{len(text)}\t{first_line(text)}")
    return 0


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    sources, name, url = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    sources.mkdir(parents=True, exist_ok=True)
    # Convert and clean up within staging; preserve existing sources until validation.
    # Stage inside the destination so successful replacements stay on one filesystem.
    with tempfile.TemporaryDirectory(prefix=".deepsearch-fetch-", dir=sources) as tmp:
        return fetch_source(Path(tmp), name, url, sources)


if __name__ == "__main__":
    # Replace characters unsupported by the terminal encoding instead of crashing.
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
