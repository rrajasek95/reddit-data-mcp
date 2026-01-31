"""Reddit Sentiment MCP Server — read-only Reddit research and sentiment analysis via PullPush API."""

import time
import uuid
from typing import Optional

import httpx
from fastmcp import FastMCP

mcp = FastMCP("Reddit Sentiment")

# --- PullPush API ---

PULLPUSH_BASE = "https://api.pullpush.io/reddit"
HTTP_TIMEOUT = 30.0

_sessions: dict[str, dict] = {}


# --- Helpers ---


def _time_filter_to_epoch(time_filter: str) -> int | None:
    """Convert a time filter string to a UTC epoch timestamp."""
    mapping = {
        "day": 86400,
        "week": 7 * 86400,
        "month": 30 * 86400,
        "year": 365 * 86400,
    }
    seconds = mapping.get(time_filter)
    if seconds:
        return int(time.time()) - seconds
    return None  # "all"


def _fetch_posts(
    query: str,
    subreddit: Optional[str] = None,
    sort: str = "score",
    time_filter: str = "all",
    limit: int = 10,
) -> list[dict]:
    """Search Reddit posts via PullPush."""
    params: dict = {
        "q": query,
        "size": min(limit, 100),
        "sort": "desc",
        "sort_type": sort,
    }
    if subreddit:
        params["subreddit"] = subreddit

    after = _time_filter_to_epoch(time_filter)
    if after:
        params["after"] = after

    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        resp = client.get(f"{PULLPUSH_BASE}/search/submission/", params=params)
        resp.raise_for_status()
        data = resp.json()

    posts = []
    for p in data.get("data", []):
        selftext = p.get("selftext", "") or ""
        posts.append({
            "id": p["id"],
            "title": p.get("title", ""),
            "subreddit": p.get("subreddit", ""),
            "score": p.get("score", 0),
            "upvote_ratio": p.get("upvote_ratio", 0),
            "num_comments": p.get("num_comments", 0),
            "url": f"https://reddit.com{p['permalink']}" if p.get("permalink") else "",
            "selftext": (selftext[:500] + "...") if len(selftext) > 500 else selftext,
            "created_utc": p.get("created_utc", 0),
            "author": p.get("author", "[deleted]"),
        })
    return posts


def _fetch_comments(post_id: str, limit: int = 10) -> list[dict]:
    """Fetch top comments for a post via PullPush."""
    params: dict = {
        "link_id": post_id,
        "size": min(limit, 100),
        "sort": "desc",
        "sort_type": "score",
    }

    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        resp = client.get(f"{PULLPUSH_BASE}/search/comment/", params=params)
        resp.raise_for_status()
        data = resp.json()

    comments = []
    for c in data.get("data", []):
        body = c.get("body", "") or ""
        if body in ("[removed]", "[deleted]"):
            continue
        comments.append({
            "author": c.get("author", "[deleted]"),
            "score": c.get("score", 0),
            "body": (body[:500] + "...") if len(body) > 500 else body,
        })
    return comments


def _format_post(post: dict, include_text: bool = False) -> str:
    """Format a single post for output."""
    lines = [
        f"### {post['title']}",
        f"r/{post['subreddit']} | Score: {post['score']} | Comments: {post['num_comments']} | Upvote ratio: {post['upvote_ratio']}",
        f"By u/{post['author']} | {post['url']}",
    ]
    if include_text and post["selftext"]:
        lines.append(f"\n{post['selftext']}")
    return "\n".join(lines)


def _format_comments(comments: list[dict]) -> str:
    """Format comments for output."""
    if not comments:
        return "_No comments_"
    lines = []
    for c in comments:
        lines.append(f"- **u/{c['author']}** (score: {c['score']}): {c['body']}")
    return "\n".join(lines)


def _format_response(
    text: str,
    response_id: Optional[str] = None,
    post_count: int = 0,
    query: str = "",
) -> str:
    """Unified response formatter."""
    parts = [text]

    if post_count:
        parts.append(f"\n---\n_Analyzed {post_count} posts for query: \"{query}\"_")

    if response_id:
        parts.append(
            f"\n_response_id: `{response_id}` — pass this to follow-up calls to refine without re-fetching._"
        )

    return "\n".join(parts)


# --- MCP Tools ---


@mcp.tool
def search(
    query: str,
    subreddit: Optional[str] = None,
    sort: str = "score",
    time_filter: str = "all",
    limit: int = 10,
) -> str:
    """
    Quick Reddit search — returns structured results.

    Search Reddit for posts matching a query. Returns titles, scores, subreddits,
    URLs, and text snippets. Good for broad discovery.

    Args:
        query: Search query string
        subreddit: Limit search to a specific subreddit (optional)
        sort: Sort type — score, num_comments, created_utc
        time_filter: Time filter — all, day, week, month, year
        limit: Max number of results (1-100, default 10)

    Returns:
        Formatted search results with post metadata
    """
    try:
        posts = _fetch_posts(query, subreddit, sort, time_filter, limit)
    except Exception as e:
        return _format_response(f"**Error:** {e}")

    if not posts:
        return _format_response(f"No results found for \"{query}\".")

    lines = [f"## Reddit Search: \"{query}\"\n"]
    for post in posts:
        lines.append(_format_post(post, include_text=True))
        lines.append("")

    return _format_response("\n".join(lines), post_count=len(posts), query=query)


@mcp.tool
def ask(
    query: str,
    subreddit: Optional[str] = None,
    time_filter: str = "week",
    limit: int = 25,
    response_id: Optional[str] = None,
) -> str:
    """
    Fetch relevant Reddit posts and top comments for sentiment synthesis.

    Searches Reddit, fetches top comments for the most relevant posts, and returns
    structured data for Claude to synthesize into a sentiment summary. Supports
    follow-up queries via response_id to refine analysis without re-fetching.

    Args:
        query: Question or topic to research
        subreddit: Limit to a specific subreddit (optional)
        time_filter: Time filter — all, day, week, month, year (default: week)
        limit: Number of posts to fetch (default 25)
        response_id: Pass a previous response_id to refine analysis on cached data

    Returns:
        Structured posts and comments for sentiment analysis
    """
    if response_id and response_id in _sessions:
        session = _sessions[response_id]
        posts_with_comments = session["data"]
        rid = response_id
    else:
        try:
            posts = _fetch_posts(query, subreddit, "score", time_filter, limit)
        except Exception as e:
            return _format_response(f"**Error:** {e}")

        if not posts:
            return _format_response(f"No results found for \"{query}\".")

        posts_with_comments = []
        for post in posts[:10]:
            try:
                comments = _fetch_comments(post["id"], limit=5)
            except Exception:
                comments = []
            posts_with_comments.append({"post": post, "comments": comments})

        rid = str(uuid.uuid4())[:12]
        _sessions[rid] = {"query": query, "data": posts_with_comments}

    lines = [f"## Reddit Sentiment Data: \"{query}\"\n"]
    for item in posts_with_comments:
        post = item["post"]
        lines.append(_format_post(post, include_text=True))
        lines.append("\n**Top comments:**")
        lines.append(_format_comments(item["comments"]))
        lines.append("")

    return _format_response(
        "\n".join(lines),
        response_id=rid,
        post_count=len(posts_with_comments),
        query=query,
    )


@mcp.tool
def think(
    query: str,
    subreddit: Optional[str] = None,
    time_filter: str = "month",
    limit: int = 50,
    response_id: Optional[str] = None,
) -> str:
    """
    Deep Reddit sentiment analysis — pulls more posts and comments for thorough breakdown.

    Fetches a larger dataset of posts and comments across subreddits for detailed
    sentiment analysis. Returns structured data with enough context for Claude to
    produce a detailed sentiment breakdown (positive/negative/neutral themes,
    common complaints, praise patterns). Supports follow-up via response_id.

    Args:
        query: Topic or question for deep analysis
        subreddit: Limit to a specific subreddit (optional, searches broadly if omitted)
        time_filter: Time filter — all, day, week, month, year (default: month)
        limit: Number of posts to fetch (default 50)
        response_id: Pass a previous response_id to drill into cached data

    Returns:
        Comprehensive structured data for detailed sentiment analysis
    """
    if response_id and response_id in _sessions:
        session = _sessions[response_id]
        posts_with_comments = session["data"]
        rid = response_id
    else:
        try:
            posts = _fetch_posts(query, subreddit, "score", time_filter, limit)
        except Exception as e:
            return _format_response(f"**Error:** {e}")

        if not posts:
            return _format_response(f"No results found for \"{query}\".")

        posts_with_comments = []
        for post in posts[:20]:
            try:
                comments = _fetch_comments(post["id"], limit=10)
            except Exception:
                comments = []
            posts_with_comments.append({"post": post, "comments": comments})

        rid = str(uuid.uuid4())[:12]
        _sessions[rid] = {"query": query, "data": posts_with_comments}

    # Summary stats
    lines = [f"## Reddit Deep Analysis: \"{query}\"\n"]

    all_scores = [item["post"]["score"] for item in posts_with_comments]
    subreddits_seen = set(item["post"]["subreddit"] for item in posts_with_comments)
    total_comments_fetched = sum(len(item["comments"]) for item in posts_with_comments)

    lines.append("### Dataset Summary")
    lines.append(f"- Posts analyzed: {len(posts_with_comments)}")
    lines.append(f"- Subreddits represented: {', '.join(f'r/{s}' for s in sorted(subreddits_seen))}")
    lines.append(f"- Score range: {min(all_scores)} to {max(all_scores)}")
    lines.append(f"- Total comments fetched: {total_comments_fetched}")
    lines.append("")

    for item in posts_with_comments:
        post = item["post"]
        lines.append(_format_post(post, include_text=True))
        lines.append("\n**Top comments:**")
        lines.append(_format_comments(item["comments"]))
        lines.append("")

    return _format_response(
        "\n".join(lines),
        response_id=rid,
        post_count=len(posts_with_comments),
        query=query,
    )


@mcp.tool
def subreddit_overview(subreddit: str) -> str:
    """
    Quick subreddit overview via recent posts.

    Fetches recent high-scoring posts from a subreddit to show what the community
    is currently discussing. Useful for understanding a community before deeper research.

    Args:
        subreddit: Subreddit name (without r/ prefix)

    Returns:
        Recent hot topics and post summaries
    """
    try:
        posts = _fetch_posts("", subreddit=subreddit, sort="created_utc", time_filter="week", limit=15)
    except Exception as e:
        return _format_response(f"**Error:** Could not fetch r/{subreddit}: {e}")

    if not posts:
        return _format_response(f"No recent posts found in r/{subreddit}.")

    lines = [
        f"## r/{subreddit} — Recent Activity\n",
        "### Recent Posts\n",
    ]

    for post in posts:
        lines.append(f"- **{post['title']}** (score: {post['score']}, comments: {post['num_comments']})")

    return _format_response("\n".join(lines))


if __name__ == "__main__":
    mcp.run()
