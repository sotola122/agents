# Searching outside English and Japanese

English and Japanese miss primary work that appears first in another language.
Choose that language from evidence, then follow its own terms and venues.

## Choose the language region

1. When the subject is already tied to one place, language, product, or technique, assign one of the two round-0 searches to that language.
2. Otherwise, include language-region evidence in the first claim:
   - Compare other-language Wikipedias linked from the English or Japanese article, and note which versions have thicker text or references.
   - From round-0 hits and `chain.py`, note repeated authors' regions and the languages of the cited originals.
3. Keep at most two search workers at once. When evidence names another language region, give one later worker that language and its local terms.
4. Count saturation only across different approaches to the same question. A round that newly opens one language region is further work in that region, not a saturation sample.

## Collect local terms before translating

A direct translation often misses the name used in that field.

1. Open the target-language Wikipedia from the English or Japanese article. Record the article title, headings, and references.
2. Take keywords from OpenAlex and from abstracts in the original language.
3. Record each term in `map.md` as `<local term> (<language>, <Japanese name>) — <source>`, and search those terms in a later round.

## Starting venues

Discover venues in round 0. Use this table only when no venue is known yet. Prefer sources `fetch.py` can save. For a login wall, a paid database, or a challenge page, look for a lawful public copy or hand the URL to the user. Do not bypass the wall.

| Region | Easier for `fetch.py` | Often needs a browser save and `ingest.py` |
|---|---|---|
| Chinese | Zcool, NetEase, university-press PDFs, GitHub blogs, arXiv, CLIP STUDIO TIPS (Traditional), GCORES | Zhihu, CSDN, Moegirl (JavaScript), Xiaohongshu (login), CNKI full text (paid) |
| Korean | YouTube captions, Paintingstack, CLIP STUDIO KR, KCI, university repositories, personal sites | Tistory, Postype, Naver paid or member articles |
| German | University repositories, Wikisource, Wikibooks, archive.org `_djvu.txt`, heise, personal blogs | Heidelberg ArtDok (Anubis), some university wikis, paid journals |
| French | HAL `/document` PDFs (`fetch.py` retries these), Persée, archive.org `_djvu.txt`, technical blogs | OpenEdition (Anubis), the ordinary HAL record page, paid journals |
| Spanish and Portuguese | SciELO, Redalyc, Dialnet, university and institute publications | Member or paid venues |
| Russian | CyberLeninka, Habr, personal blogs | Some hosts that time out, login-only forums |
| Arabic and others | That language's Wikipedia references, university or official primary announcements, YouTube captions | Login-only social networks |

These notes come from an upstream trial on 2026-11-26. Domain-restricted queries such as `site:hal.science` or `site:cyberleninka.ru` find repositories that ordinary search misses. For archive.org, pass the `/download/<id>/<id>_djvu.txt` text URL, not the `/details/<id>` catalog page.

## Fetch, verify, and display

- `fetch.py` tries UTF-8, a declared charset, then a code page suggested by the HTML `lang` (including GB18030, Big5, CP949, CP1251, CP1252, and CP1256). It converts an internationalized domain name to Punycode before the public-address check and the download.
- A PDF whose non-whitespace text is more than 30% Japanese, Chinese, or Hangul uses the 1,000-character floor. On a low-confidence OCR `FAIL`, set `DEEPSEARCH_OCR_LANG` to the matching tesseract data, such as `chi_sim+eng`, `kor+eng`, `deu+eng`, `fra+eng`, `rus+eng`, or `ara+eng`, and fetch again.
- YouTube captions try Japanese and English manual tracks, then a manual track in the video's spoken language, then automatic captions in that spoken language. Set `DEEPSEARCH_YT_LANGS` to a comma-separated list such as `zh-Hans,en` to prefer those tracks. `all` and `live_chat` are rejected.
- `report.py` normalizes quotes to NFC before comparing them, so a composed accent matches a decomposed one. Copy the original text. Do not translate it into `text`.
- Put a Japanese translation in `ja`. Set `lang` (for example `zh`, `ko`, `de`, `fr`, `ru`, or `ar`) when the script guess would be wrong. Arabic and Hebrew then use `dir="auto"`.
