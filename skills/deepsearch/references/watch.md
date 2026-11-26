# Watch mode

Use the map's venues as feed subscriptions. Enter on requests such as “what's new in X?” or `/deepsearch watch <topic>`. Run only when requested. Recurring scheduling requires a separate user request.

Topic files live under `.research/<topic>/` in the current project, unless the user named another directory.

1. Read `.research/<topic>/map.md`. If it is missing and the venues are familiar, subscribe to known official blogs, GitHub releases, relevant tags, and established personal blogs, and create a minimal map of the question, venues, and people. If the venues are unfamiliar, perform only round 0 first.
2. Add a venue with `python3 <skill_dir>/scripts/watch.py add <topic_dir> <url>`. Supported sources include Qiita tags and users, Zenn topics and users, note users, Reddit, YouTube channels, RSS blogs, and arXiv query feeds such as `https://export.arxiv.org/api/query?search_query=...&sortBy=submittedDate&sortOrder=descending`. X and pixiv do not provide supported feeds; say so. Verify a feed with `watch.py add`, not a guessed URL.
3. Run `python3 <skill_dir>/scripts/watch.py check <topic_dir>`. A new feed uses 14 days; change it with `--days N`. Results go to timestamped files in `watch/`. A quiet feed still shows its newest dated item from before that period. Use `--fresh` to ignore seen history and reselect by a wider date range.
4. Show title, date, venue, and one quoted opening line from the feed per item. Add no summaries or scores unless requested. Fetch only items the user selects or those relevant to required claims, then add them to the source table. For more than about 20 items, filter categories to match the request, disclose the filtering, and give the full results path. Append quiet feeds' latest items.
5. Add repeatedly appearing new people, venues, or terms to **Next leads**, and ask whether to subscribe to the new venues.
