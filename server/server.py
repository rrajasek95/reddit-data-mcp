"""Reddit Data MCP Server — access Reddit posts and comments via PullPush API."""

import time
from typing import Optional

import httpx
from fastmcp import FastMCP

mcp = FastMCP("Reddit Data")

PULLPUSH_BASE = "https://api.pullpush.io/reddit"
HTTP_TIMEOUT = 30.0


def _time_filter_to_epoch(time_filter: str) -> int | None:
    """Convert a time filter string to a UTC epoch timestamp."""
    seconds = {
        "day": 86400,
        "week": 7 * 86400,
        "month": 30 * 86400,
        "year": 365 * 86400,
    }.get(time_filter)
    if seconds:
        return int(time.time()) - seconds
    return None


def _truncate(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    remaining = len(text) - max_chars
    return text[:max_chars] + f"... ({remaining:,} more chars)"


def _fetch_posts(query: str, subreddit: Optional[str], sort: str, time_filter: str, limit: int, max_text: int = 2000) -> list[dict]:
    params: dict = {"q": query, "size": min(limit, 100), "sort": "desc", "sort_type": sort}
    if subreddit:
        params["subreddit"] = subreddit
    after = _time_filter_to_epoch(time_filter)
    if after:
        params["after"] = after

    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        resp = client.get(f"{PULLPUSH_BASE}/search/submission/", params=params)
        resp.raise_for_status()

    posts = []
    for p in resp.json().get("data", []):
        selftext = p.get("selftext", "") or ""
        posts.append({
            "id": p["id"],
            "title": p.get("title", ""),
            "subreddit": p.get("subreddit", ""),
            "score": p.get("score", 0),
            "num_comments": p.get("num_comments", 0),
            "url": f"https://reddit.com{p['permalink']}" if p.get("permalink") else "",
            "selftext": _truncate(selftext, max_text),
            "author": p.get("author", "[deleted]"),
        })
    return posts


def _fetch_comments(post_id: str, limit: int, max_text: int = 2000) -> list[dict]:
    params: dict = {"link_id": post_id, "size": min(limit, 100), "sort": "desc", "sort_type": "score"}

    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        resp = client.get(f"{PULLPUSH_BASE}/search/comment/", params=params)
        resp.raise_for_status()

    comments = []
    for c in resp.json().get("data", []):
        body = c.get("body", "") or ""
        if body in ("[removed]", "[deleted]"):
            continue
        comments.append({
            "author": c.get("author", "[deleted]"),
            "score": c.get("score", 0),
            "body": _truncate(body, max_text),
        })
    return comments


@mcp.tool
def search(
    query: str,
    subreddit: Optional[str] = None,
    sort: str = "score",
    time_filter: str = "all",
    limit: int = 10,
    include_comments: bool = False,
    comments_per_post: int = 5,
    max_text: int = 2000,
) -> str:
    """
    Search Reddit posts and optionally fetch top comments.

    Returns structured post data (title, score, subreddit, URL, text snippet).
    When include_comments is True, also fetches top comments for each post.
    Truncated text shows how many chars remain — increase max_text to fetch more.

    Common patterns:
    - Broad search: search("topic")
    - Scoped to subreddit: search("topic", subreddit="wallstreetbets")
    - With discussion: search("topic", include_comments=True)
    - Recent activity in a community: search("", subreddit="options", time_filter="week", sort="created_utc")
    - More data: increase limit (max 100)
    - Deep dive with comments: search("topic", limit=25, include_comments=True, comments_per_post=10)
    - Full text: search("topic", max_text=0) for no truncation

    Args:
        query: Search query string
        subreddit: Limit to a specific subreddit (optional)
        sort: Sort type — score, num_comments, created_utc
        time_filter: Time filter — all, day, week, month, year
        limit: Number of posts to return (1-100, default 10)
        include_comments: Fetch top comments for each post (default False)
        comments_per_post: Number of comments per post when include_comments is True (default 5)
        max_text: Max characters for post text and comment bodies (default 2000, 0 for no limit)

    Returns:
        Formatted post data with optional comments
    """
    try:
        posts = _fetch_posts(query, subreddit, sort, time_filter, limit, max_text)
    except Exception as e:
        return f"**Error:** {e}"

    if not posts:
        return f"No results found for \"{query}\"."

    lines = []
    for post in posts:
        lines.append(f"### {post['title']}")
        lines.append(f"r/{post['subreddit']} | Score: {post['score']} | Comments: {post['num_comments']}")
        lines.append(f"By u/{post['author']} | {post['url']}")
        if post["selftext"]:
            lines.append(f"\n{post['selftext']}")

        if include_comments:
            try:
                comments = _fetch_comments(post["id"], comments_per_post, max_text)
            except Exception:
                comments = []
            if comments:
                lines.append("\n**Top comments:**")
                for c in comments:
                    lines.append(f"- **u/{c['author']}** (score: {c['score']}): {c['body']}")
            else:
                lines.append("\n_No comments_")

        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
