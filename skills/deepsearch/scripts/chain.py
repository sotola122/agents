#!/usr/bin/env python3
"""Follow references, citations, and authors through OpenAlex.

Backward and forward citation chaining can find papers without knowing the
field's vocabulary (Bates 1989). Use anonymous access within service limits;
do not create API keys or register payment for this workflow.

Usage:
    chain.py find <DOI or title>       Identify a work; show up to five title matches.
    chain.py refs <ID or DOI> [-n 20]  Follow references backward.
    chain.py cites <ID or DOI> [-n 20] Follow citations forward, most cited first.
    chain.py author <name> [-n 20]     Find an author's works, most cited first.
Output: tab-separated year, citation count, ID, title, DOI, and open-access PDF.
"""

import json
import sys
import urllib.parse
import urllib.request

API = "https://api.openalex.org"
FIELDS = "id,display_name,publication_year,cited_by_count,doi,best_oa_location"


def get(path: str, **params) -> dict:
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "deepsearch (mailto omitted)"})
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.load(res)


def search_title(key: str) -> list[dict]:
    """Search titles only and return up to five works by citation count.

    Full-text search can rank commentary or duplicate records above the original.
    Use title words without author names. If the full title has no matches, retry its
    first three words because indexed titles may omit subtitles.
    """
    words = key.replace(",", " ").replace(":", " ").split()
    for terms in (words, words[:3]):
        hits = get("/works", filter="title.search:" + " ".join(terms),
                   sort="cited_by_count:desc", **{"per-page": 5}, select=FIELDS)["results"]
        if hits:
            return hits
    return []


def resolve(key: str) -> dict:
    """Resolve a DOI, OpenAlex ID, or title; titles select the most-cited match."""
    if key.startswith("W") or "openalex.org/" in key:
        return get(f"/works/{key.rsplit('/', 1)[-1]}", select=FIELDS)
    if key.startswith("10.") or "doi.org/" in key:
        doi = key.split("doi.org/")[-1]
        return get(f"/works/doi:{doi}", select=FIELDS)
    hits = search_title(key)
    if not hits:
        raise SystemExit(f"見つからない: {key}")
    return hits[0]


def row(w: dict) -> str:
    oa = (w.get("best_oa_location") or {}).get("pdf_url") or ""
    wid = (w.get("id") or "").rsplit("/", 1)[-1]
    return "\t".join(str(x) for x in (
        w.get("publication_year"), w.get("cited_by_count"), wid,
        (w.get("display_name") or "")[:120], w.get("doi") or "", oa))


def main() -> int:
    args = sys.argv[1:]
    n = 20
    if "-n" in args:
        i = args.index("-n")
        n = int(args[i + 1])
        del args[i:i + 2]
    if len(args) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, key = args[0], " ".join(args[1:])

    if cmd == "find":
        # Show all title candidates so the reader can identify the original.
        hits = [resolve(key)] if key.startswith(("W", "10.")) or "/" in key else search_title(key)
        if not hits:
            print(f"候補なし: {key}（DOI で引き直すか、題名の語を減らす）")
        for w in hits:
            print(row(w))
    elif cmd in ("refs", "cites"):
        wid = resolve(key)["id"].rsplit("/", 1)[-1]
        flt = f"cited_by:{wid}" if cmd == "refs" else f"cites:{wid}"
        res = get("/works", filter=flt, sort="cited_by_count:desc",
                  **{"per-page": n}, select=FIELDS)
        print(f"# {cmd} {wid} 全{res['meta']['count']}本中 上位{len(res['results'])}本")
        for w in res["results"]:
            print(row(w))
    elif cmd == "author":
        hits = get("/authors", search=key, **{"per-page": 1})["results"]
        if not hits:
            raise SystemExit(f"著者が見つからない: {key}")
        a = hits[0]
        aid = a["id"].rsplit("/", 1)[-1]
        inst = ", ".join(i["display_name"] for i in a.get("last_known_institutions") or [])
        print(f"# author {a['display_name']} {aid} {inst} 論文{a.get('works_count')}本")
        res = get("/works", filter=f"author.id:{aid}", sort="cited_by_count:desc",
                  **{"per-page": n}, select=FIELDS)
        for w in res["results"]:
            print(row(w))
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
