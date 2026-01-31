# Reddit Sentiment MCP

Read-only Reddit research and sentiment analysis via MCP. Fetches posts and comments using the PullPush API; Claude synthesizes the sentiment.

## Features

- **Search**: Quick Reddit search with structured results
- **Sentiment Analysis**: Fetch posts + comments for Claude to synthesize
- **Deep Analysis**: Larger dataset with cross-subreddit coverage
- **Subreddit Overview**: Recent community activity
- **Stateful Follow-ups**: `response_id` caches fetched data for refinement
- **No API keys required**: Uses PullPush.io public API

## Quick Start

```bash
cd server
uv sync
uv run python server.py
```

## Tools

| Tool | Purpose | Posts | Comments |
|------|---------|-------|----------|
| `search` | Quick discovery | up to 100 | None |
| `ask` | Sentiment summary | up to 25 | Top 5 per post |
| `think` | Deep analysis | up to 50 | Top 10 per post |
| `subreddit_overview` | Community activity | 15 recent | None |

## Claude Code Integration

Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "reddit": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/reddit-sentiment-mcp/server", "python", "server.py"]
    }
  }
}
```

## Project Structure

```
reddit-sentiment-mcp/
├── server/
│   ├── server.py        # FastMCP server
│   └── pyproject.toml   # Dependencies
├── skill.md             # Claude Code skill description
└── README.md
```

## Data Source

Uses [PullPush.io](https://pullpush.io/) — a public Reddit archive API. No authentication required. Rate limits: 15-30 requests/minute, 1000/hour.

## License

MIT
