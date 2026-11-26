# Excerpt page and explanation page

Write these after a stopping decision. Read this file before writing `extracts.json` or `digest.json`.

## Excerpt page

1. Write `<topic_dir>/extracts.json`, organized by required claim. Copy passages exactly, with `file`, `line`, and optional `end`. Put a Japanese translation in `ja` for any non-Japanese excerpt. Set `lang` (`zh`, `ko`, `de`, `fr`, `ru`, `ar`, and similar BCP 47 tags) when the script guess would pick the wrong font or direction. Put source type or an automatic-caption warning in `mark`.
2. Source-page links come from `url` on the quote, otherwise from the map's source table, otherwise from `fetch-log.jsonl`. Set `url` only when neither record has a complete http(s) URL.
3. For two-column text, use `…` between omitted spans. `report.py` verifies the remaining pieces in order.
4. When the copied span starts with a number, include a minus or dash (`-`, `−`, `－`, `–`) that sits immediately before that number. Copy a list item that starts with a number together with its `- ` marker.
5. Put conflicting excerpts in `disagreements` without deciding which is right. Put unreachable material in `unreached`.
6. Run `python3 <skill_dir>/scripts/report.py <topic_dir>`. A mismatch stops generation. A match writes `report.html` with expandable context.
7. Write only headings, statuses, one-line factual notes, and labeled translations. Use **根拠あり**, **一部のみ**, and **根拠なし**. Keep automatic-caption errors and label them.

```text
{"title", "question", "stopped",
 "claims": [{"claim", "status": "根拠あり|一部のみ|根拠なし", "note"?,
             "quotes": [{"file", "line", "end"?, "text", "ja"?, "lang"?,
                         "mark"?, "context_note"?, "url"?}]}],
 "disagreements"?: [{"topic", "quotes": [{"file", "line", "text", "who", ...}]}],
 "unreached"?: ["..."]}
```

## Explanation page

The page has three levels that change what is explained: Lv1 for a reader with no background, Lv2 for a neighboring field, and Lv3 for a specialist. Do not reuse a Lv2 sentence as Lv3. Every sentence in `summary`, term definitions, answers, optional quiz answers, and `people_places` needs at least one verbatim quote. Add two or three quiz questions at the end of each level; their answers use the same quote rule. `digest.py` refuses HTML when any level is missing or any quote fails the same check as `report.py`. The search record is assembled from `queries.jsonl` and `fetch-log.jsonl`.

```text
{"title", "question", "stopped",
 "claims"?: [{"claim", "status": "根拠あり|一部のみ|根拠なし"}],
 "levels": {"lv1": level, "lv2": level, "lv3": level},
 "people_places"?: [sentence], "unresolved"?: ["..."]}
level = {"summary": [sentence], "terms": [{"term", "sentences": [sentence]}],
         "answers": [{"claim", "sentences": [sentence]}],
         "quiz"?: [{"q", "answer": [sentence]}]}
sentence = {"text", "quotes": [{"file", "line", "end"?, "text"}]}
```
