# Tool details

Scripts need Python 3.10+ and the standard library. External commands are optional except when a source format requires them.

## fetch.py

`scripts/fetch.py <sources_dir> <name> <url> [--no-fallback]` downloads into a temporary directory, validates the body, and moves only a passing file into `sources_dir`. `name` is a single filename.

- PDF: save `.pdf` and `.txt` with Poppler or Xpdf `pdftotext -layout`, otherwise pdfminer.six. OCR an image-only PDF with `pdftoppm` and `tesseract`, at most 60 pages. Add installed `jpn` and `jpn_vert` to English, or use `DEEPSEARCH_OCR_LANG` (`chi_sim+eng`, `kor+eng`, `deu+eng`, `fra+eng`, `rus+eng`, `ara+eng`). Reject OCR below confidence 50 or OCR that missed a page, and name the missing command on `FAIL`.
- HTML: save `.md`. Pass saved HTML to [ax](https://github.com/yusukebe/ax) for conversion only when ax is installed; `fetch.py` performs the download. Resolve the encoding from a BOM, UTF-8, a declared charset, an HTML `lang` hint, then a generic fallback. Convert an internationalized domain to Punycode before the public-address check. Request the page once more with a non-browser User-Agent and keep a returned PDF when it meets the length floor. HAL returns HTML to a browser User-Agent and a PDF to another.
- YouTube: save captions as timestamped Markdown with `yt-dlp`, and do not save the video. Prefer Japanese and English manual captions, then a manual track in the spoken language, then automatic captions in that language. `DEEPSEARCH_YT_LANGS` (`zh-Hans,en`) overrides the preference order. `all` and `live_chat` are rejected. Cite a passage as `sources/video.md [12:34]`.
- PMC article pages come from Europe PMC full-text XML, one Markdown block per heading, paragraph, figure caption, and reference.
- Retry HTTP 429, 503, 504, and timeouts up to twice with jitter. Honor `Retry-After` only up to 15 seconds. Do not retry 400, 401, 403, or 404.
- Without `--no-fallback`, a failed URL that contains an explicit DOI or PMCID may be replaced by a DOI/PMCID-exact open copy from Europe PMC or OpenAlex (JATS XML, an OA PDF, or HTML). A failed `hal.science` record page may be replaced by its `/document` PDF. `fetch-log.jsonl` records `via` and `resolved_url`.
- `FAIL` covers 404, login, a challenge page (including Anubis wording), and text below the floor. The floor is 3,000 characters for a PDF and 1,000 for HTML. A PDF whose non-whitespace text is more than 30% Japanese, Chinese, or Hangul uses 1,000. An existing verified file with the same name is left in place. X returns `FAIL` without a download.
- Decode gzip bodies, including gzip sent as a text response, up to the byte limit. A broken gzip stream is `FAIL`.
- Name files `<author>-<year>-<short-title>`, or `arxiv-<id>-<short-title>`.

## ingest.py

`scripts/ingest.py <sources_dir> (--file <path> [--name <name>] [--url <url>] | --inbox <dir>) [--short-ok] [--move-processed]`

Validate a local HTML, PDF, or text file the user saved in a browser, then move it into `sources/` and append `fetch-log.jsonl` with `"via": "user-browser"`. Read the original URL from a `saved from url=` comment or a `.meta.json` sidecar. `--short-ok` accepts a document that is genuinely short; the wall and challenge checks remain.

## Browser fallback

Before calling a canonical source unreachable, look for a lawful copy on an author, lab, university, or subject site, or an earlier technical report. Do not use sites that bypass payment.

1. A 403, or an HTML page of only a few dozen characters because the text is drawn by JavaScript: open it in a real browser such as Playwright and save the returned PDF or rendered text. Launch Playwright with the sandbox explicit: Python `p.chromium.launch(chromium_sandbox=True)`, JavaScript `chromium.launch({ chromiumSandbox: true })`. Playwright's default adds `--no-sandbox`. Adding `channel="chrome"` is optional when local Chrome is available. If a sandboxed launch fails, report the failure and switch to the user's browser. Do not add `--no-sandbox`, including when a CLI or MCP starts Playwright.
2. A “too short” `FAIL` may be a genuinely short document. Check the page count or rendered text. If it is short, save it with `ingest.py --short-ok` and mark the source row as a short document.
3. A Cloudflare or similar challenge that a headless browser also cannot pass: ask the user to open the URL, or use a browser tool that drives the user's own browser, then pass the destination URL back to `fetch.py` or the saved file to `ingest.py`.

Run the same checks `fetch.py` uses before placing a browser-saved file in `sources/`, and note the method in `fetch-log.jsonl`. Do not fetch local or private destinations in a browser either, and do not bypass challenges.

## chain.py

`scripts/chain.py find|refs|cites|author [--log <topic_dir> --round N]` queries OpenAlex. With `--log`, the listed works are appended to `queries.jsonl`.

Use the anonymous daily allowance. Do not create an API key or register payment. A paper about a year old may return zero references and citations because indexing is behind; search the saved reference section and the web, and do not treat zero as absence. Check the year and title of a `find` candidate before using it. A name search prints other author candidates as `# 別の候補`; confirm affiliation and work count before accepting the first hit. Older author records may lack an ID or merge several people. Compare `chain.py author` with a publication list from the person's own page. Full-width punctuation is treated as a word break, and a single non-ASCII title longer than 12 characters is retried from its first 10 characters.

## report.py, digest.py, and watch.py

- `scripts/report.py <topic_dir> [--check]` verifies `extracts.json` and writes `report.html`.
- `scripts/digest.py add <topic_dir> [--round N] [--by name]` appends search-hit JSON from stdin to `queries.jsonl`.
- `scripts/digest.py <topic_dir> [--check]` verifies every explanatory sentence and writes `digest.html`.
- `scripts/watch.py add|list|check` reads RSS and Atom, including gzip. It rejects a feed that declares DOCTYPE or ENTITY, and a feed URL that contains whitespace or control characters. It uses the same public http(s) check and connect-time IP pin as `fetch.py`.

`dashboard.py` is not bundled. One investigation does not need a cross-topic history page.
