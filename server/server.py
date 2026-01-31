"""Reddit Data MCP Server — hybrid Reddit .json + Arctic-Shift backend."""

import logging
import math
import random
import time
from typing import Optional

import httpx
from fastmcp import FastMCP

log = logging.getLogger("reddit-data-mcp")

mcp = FastMCP("Reddit Data")

HTTP_TIMEOUT = 30.0
REDDIT_USER_AGENT = "linux:reddit-data-mcp:v0.2.0 (research tool)"
ARCTIC_SHIFT_BASE = "https://arctic-shift.photon-reddit.com/api"


# ---------------------------------------------------------------------------
# Rate limiter — token bucket for Reddit .json API
# ---------------------------------------------------------------------------
class _RateLimiter:
    """In-memory token bucket: max 3 requests/min with random jitter."""

    def __init__(self, max_tokens: int = 3, refill_seconds: float = 60.0):
        self.max_tokens = max_tokens
        self.refill_seconds = refill_seconds
        self.tokens = float(max_tokens)
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * (self.max_tokens / self.refill_seconds))
        self._last_refill = now

    def acquire(self, wait: bool = False) -> bool:
        """Try to consume one token. Returns True if allowed."""
        self._refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            # Human-like jitter
            time.sleep(random.uniform(1.0, 5.0))
            return True
        if wait:
            deficit = 1.0 - self.tokens
            sleep_time = deficit * (self.refill_seconds / self.max_tokens)
            time.sleep(sleep_time + random.uniform(1.0, 5.0))
            self._refill()
            self.tokens -= 1.0
            return True
        return False


_reddit_limiter = _RateLimiter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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


def _synthetic_score(post: dict) -> float:
    """Estimate popularity from Arctic-Shift snapshot data.

    Combines num_comments (engagement signal) with upvote_ratio (quality signal).
    Returns 0 for posts with no engagement, scales roughly logarithmically.
    """
    nc = post.get("num_comments", 0)
    ur = post.get("upvote_ratio", 1.0)
    if nc <= 0:
        return 0.0
    return math.log(nc + 1) * ur


def _reddit_sort_param(sort: str) -> str:
    """Map user-facing sort values to Reddit .json sort param."""
    mapping = {"score": "top", "num_comments": "comments", "created_utc": "new"}
    return mapping.get(sort, "relevance")


def _reddit_time_param(time_filter: str) -> Optional[str]:
    valid = {"hour", "day", "week", "month", "year", "all"}
    return time_filter if time_filter in valid else None


# ---------------------------------------------------------------------------
# Reddit .json client
# ---------------------------------------------------------------------------
def _fetch_posts_reddit(
    query: str,
    subreddit: Optional[str],
    sort: str,
    time_filter: str,
    limit: int,
    max_text: int,
) -> list[dict]:
    """Fetch posts from Reddit's public .json API."""
    params: dict = {
        "q": query,
        "limit": min(limit, 100),
        "sort": _reddit_sort_param(sort),
        "raw_json": 1,
    }
    t = _reddit_time_param(time_filter)
    if t:
        params["t"] = t
    if subreddit:
        params["restrict_sr"] = "on"

    base = f"https://www.reddit.com/r/{subreddit}/search.json" if subreddit else "https://www.reddit.com/search.json"

    with httpx.Client(timeout=HTTP_TIMEOUT, headers={"User-Agent": REDDIT_USER_AGENT}) as client:
        resp = client.get(base, params=params)
        resp.raise_for_status()

    posts = []
    for child in resp.json().get("data", {}).get("children", []):
        p = child.get("data", {})
        selftext = p.get("selftext", "") or ""
        posts.append({
            "id": p.get("id", ""),
            "title": p.get("title", ""),
            "subreddit": p.get("subreddit", ""),
            "score": p.get("score", 0),
            "num_comments": p.get("num_comments", 0),
            "url": f"https://reddit.com{p['permalink']}" if p.get("permalink") else "",
            "selftext": _truncate(selftext, max_text),
            "author": p.get("author", "[deleted]"),
            "_source": "reddit",
        })
    return posts


# ---------------------------------------------------------------------------
# Arctic-Shift client
# ---------------------------------------------------------------------------
def _fetch_posts_arctic(
    query: str,
    subreddit: str,
    sort: str,
    time_filter: str,
    limit: int,
    max_text: int,
) -> list[dict]:
    """Fetch posts from Arctic-Shift (subreddit required).

    Arctic-Shift scores are ingest-time snapshots, so we overfetch and re-rank
    client-side using a synthetic score (num_comments × upvote_ratio) when the
    user wants popularity-based sorting.
    """
    # Overfetch up to 100 so we have enough candidates to re-rank
    fetch_limit = min(limit * 5, 100) if sort in ("score", "num_comments") else min(limit, 100)

    params: dict = {
        "query": query,
        "subreddit": subreddit,
        "limit": fetch_limit,
        "sort": "desc",
    }
    after_epoch = _time_filter_to_epoch(time_filter)
    if after_epoch:
        params["after"] = after_epoch

    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        resp = client.get(f"{ARCTIC_SHIFT_BASE}/posts/search", params=params)
        resp.raise_for_status()

    posts = []
    for p in resp.json().get("data", []):
        selftext = p.get("selftext", "") or ""
        permalink = p.get("permalink", "")
        synth = _synthetic_score(p)
        posts.append({
            "id": p.get("id", ""),
            "title": p.get("title", ""),
            "subreddit": p.get("subreddit", subreddit),
            "score": p.get("score", 0),
            "num_comments": p.get("num_comments", 0),
            "upvote_ratio": p.get("upvote_ratio", 1.0),
            "url": f"https://reddit.com{permalink}" if permalink else "",
            "selftext": _truncate(selftext, max_text),
            "author": p.get("author", "[deleted]"),
            "_source": "arctic-shift",
            "_synthetic_score": round(synth, 2),
        })

    # Re-rank by synthetic score for popularity sorts
    if sort in ("score", "num_comments"):
        posts.sort(key=lambda p: p["_synthetic_score"], reverse=True)

    return posts[:limit]


# ---------------------------------------------------------------------------
# Comment fetching
# ---------------------------------------------------------------------------
def _fetch_comments_reddit(post_id: str, limit: int, max_text: int) -> list[dict]:
    """Fetch comments from Reddit .json API."""
    url = f"https://www.reddit.com/comments/{post_id}.json"
    params = {"limit": min(limit, 100), "sort": "top", "raw_json": 1}

    with httpx.Client(timeout=HTTP_TIMEOUT, headers={"User-Agent": REDDIT_USER_AGENT}) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()

    data = resp.json()
    if not isinstance(data, list) or len(data) < 2:
        return []

    comments = []
    for child in data[1].get("data", {}).get("children", []):
        c = child.get("data", {})
        body = c.get("body", "") or ""
        if body in ("[removed]", "[deleted]"):
            continue
        comments.append({
            "author": c.get("author", "[deleted]"),
            "score": c.get("score", 0),
            "body": _truncate(body, max_text),
        })
        if len(comments) >= limit:
            break
    return comments


def _fetch_comments_arctic(post_id: str, limit: int, max_text: int) -> list[dict]:
    """Fetch comments from Arctic-Shift (fallback)."""
    params = {"link_id": post_id, "limit": min(limit, 100)}

    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        resp = client.get(f"{ARCTIC_SHIFT_BASE}/comments/search", params=params)
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


def _fetch_comments(post_id: str, limit: int, max_text: int) -> list[dict]:
    """Fetch comments — prefer Reddit .json, fall back to Arctic-Shift."""
    if _reddit_limiter.acquire():
        try:
            return _fetch_comments_reddit(post_id, limit, max_text)
        except Exception:
            pass
    # Fallback
    try:
        return _fetch_comments_arctic(post_id, limit, max_text)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Hybrid search strategy
# ---------------------------------------------------------------------------
def _fetch_posts(
    query: str,
    subreddit: Optional[str],
    sort: str,
    time_filter: str,
    limit: int,
    max_text: int,
) -> list[dict]:
    """
    Hybrid fetch:
    - subreddit provided → Arctic-Shift first, Reddit .json fallback
    - no subreddit → Reddit .json (only option for global search)
    """
    if subreddit:
        # Try Arctic-Shift first (no rate limit concerns)
        try:
            posts = _fetch_posts_arctic(query, subreddit, sort, time_filter, limit, max_text)
            if posts:
                return posts
            log.debug("Arctic-Shift returned 0 results for q=%r sub=%r", query, subreddit)
        except Exception as e:
            log.warning("Arctic-Shift failed for q=%r sub=%r: %s", query, subreddit, e)
        # Fallback to Reddit .json
        if _reddit_limiter.acquire():
            try:
                return _fetch_posts_reddit(query, subreddit, sort, time_filter, limit, max_text)
            except Exception as e:
                log.warning("Reddit .json fallback failed for q=%r sub=%r: %s", query, subreddit, e)
        else:
            log.debug("Rate limiter denied Reddit .json fallback for q=%r sub=%r", query, subreddit)
        return []
    else:
        # Global search — Reddit .json only
        if not _reddit_limiter.acquire(wait=True):
            log.warning("Rate limiter denied global search for q=%r", query)
            return []
        return _fetch_posts_reddit(query, None, sort, time_filter, limit, max_text)


# ---------------------------------------------------------------------------
# MCP Tool
# ---------------------------------------------------------------------------
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

    IMPORTANT: Always provide a subreddit when you can reasonably infer one from
    context. Subreddit-scoped searches use a fast archival backend with no rate
    limits. Omitting subreddit forces a global Reddit search which is rate-limited
    to ~3 requests/minute and may fail under heavy use.

    Examples of inferring subreddit:
    - Python libraries → subreddit="Python"
    - Stock/trading sentiment → subreddit="wallstreetbets"
    - Machine learning papers → subreddit="MachineLearning"
    - Gaming discussion → subreddit="gaming"
    - Only omit subreddit for genuinely open-ended cross-community searches.

    Common patterns:
    - Scoped search (preferred): search("topic", subreddit="Python")
    - Broad search (rate-limited): search("topic")
    - With discussion: search("topic", subreddit="Python", include_comments=True)
    - Recent activity: search("", subreddit="options", time_filter="week", sort="created_utc")
    - More data: increase limit (max 100)
    - Deep dive: search("topic", subreddit="Python", limit=25, include_comments=True, comments_per_post=10)
    - Full text: search("topic", subreddit="Python", max_text=0) for no truncation

    Args:
        query: Search query string
        subreddit: Target subreddit (strongly recommended — enables fast archival search)
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
        source = post.get("_source", "unknown")
        lines.append(f"### {post['title']}")
        meta = f"r/{post['subreddit']} | Score: {post['score']} | Comments: {post['num_comments']} | Source: {source}"
        if source == "arctic-shift" and "_synthetic_score" in post:
            meta += f" | Rank: {post['_synthetic_score']}"
        lines.append(meta)
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
