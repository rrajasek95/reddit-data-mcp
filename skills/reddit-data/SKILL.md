---
name: reddit-data
description: Search Reddit posts and comments via MCP. Use when the user wants to search Reddit, find discussions on a topic, browse subreddits, get comment threads, or analyze Reddit sentiment. Always provide a subreddit parameter when one can be inferred from context.
version: 0.2.0
---

# Reddit Data

Search Reddit posts and optionally fetch top comments.

## Tool

### search
```
search(query, subreddit?, sort="score", time_filter="all", limit=10, include_comments=False, comments_per_post=5, max_text=2000)
```

## Critical: Always Provide a Subreddit

Subreddit-scoped searches use a fast archival backend with no rate limits.
Omitting subreddit forces a rate-limited global search (~3 requests/minute).

**Always infer a subreddit when possible:**
- Python libraries → subreddit="Python"
- Stock/trading sentiment → subreddit="wallstreetbets"
- Machine learning → subreddit="MachineLearning"
- Gaming → subreddit="gaming"
- Startups/tech → subreddit="technology"
- Only omit subreddit for genuinely cross-community searches.

## Common Patterns

### Scoped search (preferred — fast, no rate limit)
```
search("best broker for options", subreddit="options")
```

### Browse recent activity in a community
```
search("", subreddit="wallstreetbets", time_filter="week", sort="created_utc")
```

### Get posts with comments
```
search("what do people think about Robinhood", subreddit="stocks", include_comments=True)
```

### Deep dive with more data
```
search("Tesla", subreddit="wallstreetbets", limit=25, include_comments=True, comments_per_post=10)
```

### Global search (rate-limited — use sparingly)
```
search("topic with no obvious subreddit")
```

### Full text (no truncation)
```
search("Tesla", subreddit="wallstreetbets", max_text=0)
```

## Parameters

- **query**: Search terms (empty string for browsing a subreddit)
- **subreddit**: Target subreddit (strongly recommended — enables fast archival search)
- **sort**: `score`, `num_comments`, or `created_utc`
- **time_filter**: `all`, `day`, `week`, `month`, `year`
- **limit**: Number of posts (1-100)
- **include_comments**: Fetch top comments per post
- **comments_per_post**: How many comments per post (default 5)
- **max_text**: Max chars for post/comment text (default 2000, 0 for no limit)

## Notes

- No API keys required
- Subreddit searches use Arctic-Shift (archival backend, no rate limits)
- Global searches use Reddit .json API (rate-limited to ~3 req/min)
- Posts include: title, score, subreddit, author, URL, text snippet, source indicator
- Comments include: author, score, body text
- Archival results show a synthetic popularity rank based on engagement signals
- Removed/deleted comments are filtered out
