# Reddit Sentiment Skill

Use the Reddit Sentiment MCP to search Reddit and analyze community sentiment on any topic.

## When to Use

- **Market research**: What do people think about a product, broker, or service?
- **Sentiment analysis**: Gauge community opinion on a topic
- **Trend discovery**: Find what's being discussed in specific subreddits
- **Community overview**: Understand a subreddit's focus and activity

## Available Tools

### search - Quick Reddit Search
```
search(query, subreddit?, sort="score", time_filter="all", limit=10)
```
Returns structured results (title, subreddit, score, URL, text snippet).

### ask - Sentiment Summary
```
ask(query, subreddit?, time_filter="week", limit=25, response_id?)
```
Fetches posts + top comments for sentiment synthesis. Pass `response_id` from a previous call to refine without re-fetching.

### think - Deep Analysis
```
think(query, subreddit?, time_filter="month", limit=50, response_id?)
```
Pulls more posts/comments across subreddits for detailed sentiment breakdown (themes, complaints, praise patterns).

### subreddit_overview - Community Activity
```
subreddit_overview(subreddit)
```
Recent posts from a subreddit showing current discussion topics.

## Examples

### Search for discussions
```
search("best broker for options trading")
```

### Get sentiment on a topic
```
ask("what do people think about Robinhood?", subreddit="wallstreetbets")
```

### Deep analysis
```
think("Tesla stock sentiment", time_filter="week")
```

### Follow-up on previous results
```
ask("drill into the negative comments", response_id="abc123def456")
```

### Explore a community
```
subreddit_overview("options")
```

## Output Format

Responses include:
- Structured post data (title, score, subreddit, comments)
- Comment text for sentiment analysis
- response_id for follow-up queries (ask/think only)

## Environment

No API keys required. Uses the PullPush.io public API for Reddit data access.
