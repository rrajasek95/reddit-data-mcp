# Reddit Data MCP

MCP server for accessing Reddit posts and comments. Searches across subreddits, fetches comment threads, and returns structured data ready for downstream analysis.

No API keys required. Uses a hybrid backend:
- **Arctic-Shift** — archival backend for subreddit-scoped searches (no rate limits)
- **Reddit .json** — live Reddit data for global searches (rate-limited to ~3 req/min)

## Install as Claude Code Plugin

```bash
# Add the marketplace (one-time)
claude plugin marketplace add rrajasek95/reddit-data-mcp

# Install the plugin
claude plugin install reddit-data-mcp@reddit-data-mcp
```

## Manual Setup

```bash
git clone https://github.com/rrajasek95/reddit-data-mcp.git
cd reddit-data-mcp/server
uv sync
uv run python server.py
```

Or add to `.claude/settings.json`:

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

## Tool

One tool: `search`

```
search(query, subreddit?, sort="score", time_filter="all", limit=10, include_comments=False, comments_per_post=5, max_text=2000)
```

**Always provide a subreddit when possible** — this routes through Arctic-Shift (fast, no rate limits). Omitting subreddit forces a rate-limited global Reddit search.

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `query` | required | Search terms (empty string to browse a subreddit) |
| `subreddit` | all | Target subreddit (strongly recommended) |
| `sort` | `score` | `score`, `num_comments`, or `created_utc` |
| `time_filter` | `all` | `all`, `day`, `week`, `month`, `year` |
| `limit` | 10 | Number of posts (1-100) |
| `include_comments` | False | Fetch top comments per post |
| `comments_per_post` | 5 | Comments per post when enabled |
| `max_text` | 2000 | Max chars for post/comment text (0 = no limit) |

## How It Works

- **Subreddit-scoped searches** hit [Arctic-Shift](https://arctic-shift.photon-reddit.com/) first. Results are overfetched and re-ranked by a synthetic popularity score (`log(num_comments + 1) × upvote_ratio`) since archival scores are ingest-time snapshots. Falls back to Reddit .json if Arctic-Shift returns nothing.
- **Global searches** (no subreddit) go directly to Reddit's `.json` API with a token-bucket rate limiter (3 req/min, random jitter).
- **Comments** are fetched from Reddit .json (live scores) when rate budget allows, otherwise from Arctic-Shift.

Each result includes a `Source: reddit` or `Source: arctic-shift` indicator.

## Acknowledgements

- [Arctic-Shift](https://github.com/ArthurHeitmann/arctic_shift) — Reddit archival project providing the search API and data dumps
- [FastMCP](https://github.com/jlowin/fastmcp) — Python framework for building MCP servers
- [httpx](https://github.com/encode/httpx) — HTTP client library
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — Anthropic's CLI tool (plugin target)

## License

MIT
