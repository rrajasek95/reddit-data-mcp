# Reddit Data MCP

MCP server for accessing Reddit posts and comments. Searches across subreddits, fetches comment threads, and returns structured data ready for downstream analysis.

No API keys required — uses the public [PullPush.io](https://pullpush.io/) archive.

## Tool

One tool: `search`

```
search(query, subreddit?, sort="score", time_filter="all", limit=10, include_comments=False, comments_per_post=5, max_text=2000)
```

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `query` | required | Search terms (empty string to browse a subreddit) |
| `subreddit` | all | Filter to one subreddit |
| `sort` | `score` | `score`, `num_comments`, or `created_utc` |
| `time_filter` | `all` | `all`, `day`, `week`, `month`, `year` |
| `limit` | 10 | Number of posts (1-100) |
| `include_comments` | False | Fetch top comments per post |
| `comments_per_post` | 5 | Comments per post when enabled |
| `max_text` | 2000 | Max chars for post/comment text (0 = no limit) |

## Quick Start

```bash
cd server
uv sync
uv run python server.py
```

## Claude Code Integration

Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "reddit": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/reddit-data-mcp/server", "python", "server.py"]
    }
  }
}
```

## Data Source

[PullPush.io](https://pullpush.io/) — public Reddit archive API. No authentication required. Rate limits: 15-30 requests/minute, 1000/hour.

## License

MIT
