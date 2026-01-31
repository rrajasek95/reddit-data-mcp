# Reddit Data Skill

Access Reddit posts and comments via MCP.

## Tool

### search
```
search(query, subreddit?, sort="score", time_filter="all", limit=10, include_comments=False, comments_per_post=5)
```

## Common Patterns

### Find posts on a topic
```
search("best broker for options trading")
```

### Scope to a subreddit
```
search("DD", subreddit="wallstreetbets", time_filter="week")
```

### Get posts with comments
```
search("what do people think about Robinhood", include_comments=True)
```

### See what a community is discussing
```
search("", subreddit="options", time_filter="week", sort="created_utc")
```

### Deep dive with more data
```
search("Tesla", limit=25, include_comments=True, comments_per_post=10)
```

## Parameters

- **query**: Search terms (empty string for browsing a subreddit)
- **subreddit**: Filter to one subreddit
- **sort**: `score`, `num_comments`, or `created_utc`
- **time_filter**: `all`, `day`, `week`, `month`, `year`
- **limit**: Number of posts (1-100)
- **include_comments**: Fetch top comments per post
- **comments_per_post**: How many comments per post (default 5)

## Notes

- No API keys required
- Data comes from PullPush.io (public Reddit archive)
- Posts include: title, score, subreddit, author, URL, text snippet
- Comments include: author, score, body text
- Removed/deleted comments are filtered out
