#!/usr/bin/env python3
"""Monitor the map's venues for new items through RSS/Atom (Ellis's monitoring).

Show each feed's original opening text, without agent-written summaries.

Usage:
    watch.py add <topic_dir> <url> [name]  Discover and add a feed.
    watch.py list <topic_dir>             List subscriptions.
    watch.py check <topic_dir> [--days N] [--fresh]
        Save updates to watch/<date-time>.md. New feeds use the last N days
        (default 14). --fresh ignores seen history and reselects by the window.
        Quiet feeds still show their latest dated item outside the window.

Storage (<topic_dir> = .research/<topic>/ under the project/workspace root):
    watch.tsv         Tab-separated kind, name, feed URL, original URL.
    watch-state.json  Previously seen item URLs per feed.
    watch/<date-time>.md  Results of each check.
"""

import datetime as dt
import email.utils
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 deepsearch-watch"}
ATOM = "{http://www.w3.org/2005/Atom}"
# Keep the opening snippet short enough to guide selection without replacing the source.
HEAD_CHARS = 120
# Maximum seen URLs per feed; feeds normally return only a few dozen recent items.
# Retain enough history to avoid presenting old items as new.
SEEN_LIMIT = 500


class _Redirect308(urllib.request.HTTPRedirectHandler):
    """Follow HTTP 308 redirects on Python 3.10, which lacks native support.

    Duplicate fetch.py's handler so scripts remain usable with isolated Python (-I),
    which omits the script directory from the import path.
    """

    http_error_308 = urllib.request.HTTPRedirectHandler.http_error_302

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, 307 if code == 308 else code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_Redirect308)


def fetch(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers=UA)
    with _OPENER.open(req, timeout=60) as res:
        return res.read(5_000_000), res.headers.get("Content-Type", "")


def known_feed(url: str) -> tuple[str, str] | None:
    """Return the kind and feed URL for recognized website URL patterns."""
    rules = [
        (r"^https?://qiita\.com/tags/([^/?#]+)", "qiita-tag", "https://qiita.com/tags/{0}/feed"),
        (r"^https?://zenn\.dev/topics/([^/?#]+)", "zenn-topic", "https://zenn.dev/topics/{0}/feed"),
        (r"^https?://zenn\.dev/([^/?#]+)/?$", "zenn-user", "https://zenn.dev/{0}/feed"),
        (r"^https?://note\.com/([^/?#]+)/?$", "note-user", "https://note.com/{0}/rss"),
        (r"^https?://qiita\.com/([^/?#]+)/?$", "qiita-user", "https://qiita.com/{0}/feed"),
        (r"^https?://(?:www\.|old\.)?reddit\.com/r/([^/?#]+)", "reddit", "https://www.reddit.com/r/{0}/.rss"),
    ]
    for pat, kind, tmpl in rules:
        m = re.match(pat, url)
        if m:
            return kind, tmpl.format(*m.groups())
    if "export.arxiv.org/api/query" in url:
        return "arxiv", url
    return None


def discover(url: str) -> tuple[str, str]:
    """Discover an RSS/Atom alternate link, or accept a direct feed URL.

    Blogs, WordPress, Hatena, and YouTube channel pages can advertise these links.
    """
    hit = known_feed(url)
    if hit:
        return hit
    body, ctype = fetch(url)
    if "xml" in ctype or body.lstrip()[:5] in (b"<?xml", b"<rss ", b"<feed"):
        return "feed", url
    text = body.decode("utf-8", errors="replace")
    for m in re.finditer(r"<link\b[^>]*>", text, re.I):
        tag = m.group(0)
        if re.search(r'type=["\']application/(rss|atom)\+xml', tag, re.I):
            href = re.search(r'href=["\']([^"\']+)', tag)
            if href:
                feed = html.unescape(href.group(1))
                if feed.startswith("/"):
                    root = re.match(r"^https?://[^/]+", url).group(0)
                    feed = root + feed
                kind = "youtube" if "youtube.com/feeds" in feed else "site"
                return kind, feed
    raise SystemExit(f"RSS が見つからない: {url}（ページに RSS の案内が無い。X・pixiv はそもそも出していない）")


def plain(s: str | None) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def parse_date(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    s = s.strip()
    try:
        d = email.utils.parsedate_to_datetime(s)  # RSS 2.0 date format.
    except (TypeError, ValueError):
        try:
            d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))  # Atom date format.
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def items(feed_bytes: bytes) -> list[dict]:
    """Normalize RSS 2.0 and Atom entries into title, link, date, and opening text.

    Reject DOCTYPE and ENTITY declarations in untrusted feed prologs before parsing.
    Ordinary RSS/Atom feeds do not need them; this avoids adding an XML dependency.
    """
    # Declarations belong before the root element; inspect only the prolog.
    # A DOCTYPE mentioned inside article CDATA must not reject the feed.
    root_at = re.search(rb"<(rss|feed|rdf:RDF)\b", feed_bytes)
    prolog = feed_bytes[: root_at.start()] if root_at else feed_bytes
    if re.search(rb"<!(DOCTYPE|ENTITY)", prolog, re.I):
        raise ValueError("DOCTYPE か ENTITY を含むフィードは読まない")
    root = ET.fromstring(feed_bytes)
    out = []
    for it in root.iter("item"):
        out.append({
            "title": plain(it.findtext("title")),
            "link": (it.findtext("link") or "").strip(),
            "date": parse_date(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")),
            "head": plain(it.findtext("description")),
        })
    for en in root.iter(f"{ATOM}entry"):
        link = ""
        for ln in en.findall(f"{ATOM}link"):
            if ln.get("rel", "alternate") == "alternate":
                link = ln.get("href", "")
                break
        head = en.findtext(f"{ATOM}summary") or en.findtext(f"{ATOM}content") \
            or en.findtext("{http://search.yahoo.com/mrss/}group/{http://search.yahoo.com/mrss/}description")
        out.append({
            "title": plain(en.findtext(f"{ATOM}title")),
            "link": link,
            "date": parse_date(en.findtext(f"{ATOM}published") or en.findtext(f"{ATOM}updated")),
            "head": plain(head),
        })
    return out


def load_watch(topic: Path) -> list[list[str]]:
    p = topic / "watch.tsv"
    if not p.exists():
        return []
    return [ln.split("\t") for ln in p.read_text(encoding="utf-8").splitlines()
            if ln and not ln.startswith("#")]


def cmd_add(topic: Path, url: str, name: str | None) -> int:
    # Return a short error so a failed feed does not prevent adding other feeds.
    # Upstream encountered a Reddit 429 response during a trial.
    try:
        kind, feed = discover(url)
        found = items(fetch(feed)[0])  # Validate the feed before adding it.
    except SystemExit as e:
        print(f"足せなかった: {e}")
        return 1
    except Exception as e:
        print(f"足せなかった: {url}（{type(e).__name__}: {e}）")
        return 1
    for row in load_watch(topic):
        if row[2] == feed:
            print(f"もう見張っている: {row[1]} {feed}")
            return 0
    if name:
        label = name
    elif kind == "arxiv":
        q = re.search(r"search_query=([^&]+)", url)
        label = "arxiv " + (urllib.parse.unquote(q.group(1)) if q else "query")
    elif kind == "feed" and found:
        label = found[0]["title"][:30]
    else:
        # Use domain and path; final components such as blog/releases are ambiguous.
        label = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")[:40]
    topic.mkdir(parents=True, exist_ok=True)
    p = topic / "watch.tsv"
    if not p.exists():
        p.write_text("# 種類\t名前\tフィード\t元の URL\n", encoding="utf-8")
    with p.open("a", encoding="utf-8") as f:
        f.write(f"{kind}\t{label}\t{feed}\t{url}\n")
    print(f"足した: {kind}\t{label}\t{feed}（いま {len(found)} 件）")
    return 0


def cmd_check(topic: Path, days: int, fresh: bool) -> None:
    """Show new items; fresh ignores seen history and selects only by days.

    The first check also marks items outside its window as seen. Use fresh when
    widening that window so the earlier history does not suppress those items.
    """
    rows = load_watch(topic)
    if not rows:
        raise SystemExit(f"見張る先が無い: {topic}/watch.tsv（watch.py add で足す）")
    state_p = topic / "watch-state.json"
    state = json.loads(state_p.read_text(encoding="utf-8")) if state_p.exists() else {}
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=days)
    lines = [f"# 新着 {now.astimezone():%Y-%m-%d %H:%M}", ""]
    quiet: list[str] = []
    total = 0
    for kind, label, feed, *_ in rows:
        try:
            got = items(fetch(feed)[0])
        except Exception as e:  # Keep checking other feeds if one fails.
            lines += [f"## {label}（{kind}）", f"- 取れなかった: {type(e).__name__}: {e}", ""]
            continue
        seen = set() if fresh else set(state.get(feed, []))
        first = fresh or feed not in state
        new = [i for i in got if i["link"] and i["link"] not in seen
               and (not first or (i["date"] and i["date"] >= cutoff))]
        new.sort(key=lambda i: i["date"] or now, reverse=True)
        state[feed] = ([i["link"] for i in got] + list(set(state.get(feed, [])) - {i["link"] for i in got}))[:SEEN_LIMIT]
        if not new:
            # Show a quiet feed's newest item regardless of the date window.
            # This keeps a significant official update visible even when it is older.
            dated = [i for i in got if i["date"]]
            if dated:
                last = max(dated, key=lambda i: i["date"])
                quiet.append(f"- {label}（{kind}）最新 {last['date'].astimezone():%Y-%m-%d} [{last['title']}]({last['link']})")
            else:
                quiet.append(f"- {label}（{kind}）記事なし")
            continue
        total += len(new)
        lines.append(f"## {label}（{kind}）{'・直近' + str(days) + '日' if first else ''}")
        for i in new:
            day = i["date"].astimezone().strftime("%Y-%m-%d") if i["date"] else "日付なし"
            lines.append(f"- {day} [{i['title']}]({i['link']})")
            if i["head"]:
                lines.append(f"  > {i['head'][:HEAD_CHARS]}{'…' if len(i['head']) > HEAD_CHARS else ''}")
        lines.append("")
    if total == 0:
        lines += ["新着なし", ""]
    if quiet:
        lines += ["## 新着の無かった場所（窓に関係なく最新の1件）", *quiet, ""]
    state_p.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    # Include seconds to avoid overwriting earlier checks on the same day.
    out = topic / "watch" / f"{now.astimezone():%Y-%m-%d-%H%M%S}.md"
    n = 2
    while out.exists():  # Preserve earlier results even when checks run within the same second.
        out = out.with_name(f"{now.astimezone():%Y-%m-%d-%H%M%S}-{n}.md")
        n += 1
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n→ {out}（新着 {total} 件・見張る先 {len(rows)}）")


def main() -> int:
    args = sys.argv[1:]
    days = 14
    fresh = "--fresh" in args
    if fresh:
        args.remove("--fresh")
    if "--days" in args:
        i = args.index("--days")
        days = int(args[i + 1])
        del args[i:i + 2]
    if len(args) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, topic = args[0], Path(args[1]).expanduser()
    if cmd == "add" and len(args) >= 3:
        return cmd_add(topic, args[2], args[3] if len(args) > 3 else None)
    elif cmd == "list":
        for row in load_watch(topic):
            print("\t".join(row))
    elif cmd == "check":
        cmd_check(topic, days, fresh)
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    # Replace characters unsupported by the terminal encoding instead of crashing.
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
