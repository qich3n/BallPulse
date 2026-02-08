"""
Async Reddit Service

Service for fetching Reddit posts and comments using async httpx.
Supports both public JSON endpoints and PRAW (for authenticated requests).
"""

import logging
import os
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

# Try to import PRAW, but make it optional
try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    praw = None


class AsyncRedditService:
    """Async service for fetching Reddit posts and comments using httpx"""
    
    # Team name to subreddit mapping
    TEAM_SUBREDDIT_MAP = {
        "los angeles lakers": "lakers",
        "golden state warriors": "warriors",
        "boston celtics": "bostonceltics",
        "miami heat": "heat",
        "philadelphia 76ers": "sixers",
        "milwaukee bucks": "milwaukeebucks",
        "denver nuggets": "denvernuggets",
        "phoenix suns": "suns",
        "dallas mavericks": "mavericks",
        "brooklyn nets": "gonets",
        "new york knicks": "nyknicks",
        "atlanta hawks": "atlantahawks",
        "chicago bulls": "chicagobulls",
        "cleveland cavaliers": "clevelandcavs",
        "detroit pistons": "detroitpistons",
        "indiana pacers": "pacers",
        "toronto raptors": "torontoraptors",
        "charlotte hornets": "charlottehornets",
        "orlando magic": "orlandomagic",
        "washington wizards": "washingtonwizards",
        "portland trail blazers": "ripcity",
        "utah jazz": "utahjazz",
        "oklahoma city thunder": "thunder",
        "minnesota timberwolves": "timberwolves",
        "sacramento kings": "kings",
        "los angeles clippers": "laclippers",
        "memphis grizzlies": "memphisgrizzlies",
        "new orleans pelicans": "nolapelicans",
        "san antonio spurs": "nbaspurs",
        "houston rockets": "rockets",
    }
    
    def __init__(
        self,
        timeout: float = 10.0,
        max_retries: int = 3,
        cache_service: Optional[Any] = None,
        cache_ttl: int = 1800  # 30 minutes
    ):
        """
        Initialize async Reddit service
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            cache_service: Optional cache service instance
            cache_ttl: Cache TTL in seconds
        """
        self.logger = logging.getLogger(__name__)
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_service = cache_service
        self.cache_ttl = cache_ttl
        
        # User-Agent is required by Reddit API
        self.headers = {
            'User-Agent': 'BallPulse/1.0 (Python/AsyncRedditService)'
        }
        
        # Initialize PRAW if credentials are available (for fallback)
        self.praw_client = None
        if PRAW_AVAILABLE:
            client_id = os.getenv('REDDIT_CLIENT_ID')
            client_secret = os.getenv('REDDIT_CLIENT_SECRET')
            user_agent = os.getenv('REDDIT_USER_AGENT', 'BallPulse/1.0')
            
            if client_id and client_secret:
                try:
                    self.praw_client = praw.Reddit(
                        client_id=client_id,
                        client_secret=client_secret,
                        user_agent=user_agent
                    )
                    self.logger.info("PRAW client initialized with credentials (fallback)")
                except (ImportError, praw.exceptions.PRAWException, ValueError) as e:
                    self.logger.warning("Failed to initialize PRAW client: %s", e)
    
    def _get_team_subreddit(self, team_name: str) -> Optional[str]:
        """Get subreddit name for a team"""
        team_lower = team_name.lower()
        return self.TEAM_SUBREDDIT_MAP.get(team_lower)
    
    async def _fetch_json_endpoint(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch data from Reddit JSON endpoint with retries and timeout (async)
        
        Args:
            url: Reddit JSON API URL
            
        Returns:
            JSON data or None if failed
        """
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response.json()
            except httpx.TimeoutException:
                self.logger.warning("Timeout fetching %s (attempt %d/%d)", url, attempt + 1, self.max_retries)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    self.logger.warning("Rate limited by Reddit (attempt %d/%d)", attempt + 1, self.max_retries)
                    # Exponential backoff could be added here
                else:
                    self.logger.error("HTTP error fetching %s: %s", url, e)
                    return None
            except (httpx.RequestError, ValueError) as e:
                self.logger.error("Error fetching Reddit JSON endpoint %s: %s", url, e)
                return None
        
        return None
    
    def _parse_reddit_post(self, post_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a Reddit post from JSON API response
        
        Args:
            post_data: Post data from Reddit JSON API
            
        Returns:
            Parsed post dictionary
        """
        data = post_data.get('data', {})
        return {
            'title': data.get('title', ''),
            'text': data.get('selftext', ''),
            'url': f"https://www.reddit.com{data.get('permalink', '')}",
            'score': data.get('score', 0),
            'num_comments': data.get('num_comments', 0),
            'created_utc': data.get('created_utc', 0),
            'author': data.get('author', '')
        }
    
    async def _fetch_comments_json(self, post_id: str) -> List[Dict[str, Any]]:
        """
        Fetch comments for a post using JSON API (async)
        
        Args:
            post_id: Reddit post ID (without 't3_' prefix)
            
        Returns:
            List of comment dictionaries
        """
        url = f"https://www.reddit.com/comments/{post_id}.json"
        data = await self._fetch_json_endpoint(url)
        
        if not data or len(data) < 2:
            return []
        
        comments_data = data[1].get('data', {}).get('children', [])
        comments = []
        
        for item in comments_data[:10]:  # Sample top 10 comments
            comment_data = item.get('data', {})
            if comment_data.get('body'):  # Skip deleted/removed comments
                comments.append({
                    'text': comment_data.get('body', ''),
                    'score': comment_data.get('score', 0),
                    'author': comment_data.get('author', ''),
                    'url': f"https://www.reddit.com{comment_data.get('permalink', '')}"
                })
        
        return comments
    
    async def _fetch_posts_json(self, subreddit: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Fetch posts from a subreddit using JSON API (async)
        
        Args:
            subreddit: Subreddit name
            limit: Maximum number of posts to fetch
            
        Returns:
            List of post dictionaries
        """
        url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
        data = await self._fetch_json_endpoint(url)
        
        if not data:
            return []
        
        posts = []
        children = data.get('data', {}).get('children', [])
        
        for child in children:
            post = self._parse_reddit_post(child)
            posts.append(post)
        
        return posts
    
    async def fetch_team_posts(
        self,
        team_name: str,
        limit: int = 10,
        include_comments: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent posts related to a team (async)
        
        Args:
            team_name: Team name
            limit: Maximum number of posts to fetch
            include_comments: Whether to include sample comments
            
        Returns:
            List of post dictionaries with text and URLs
        """
        # Check cache
        if self.cache_service:
            cache_key = f"reddit:team:{team_name.lower()}:{limit}"
            cached = self.cache_service.cache.get(cache_key)
            if cached:
                self.logger.info("Cache hit for team posts: %s", team_name)
                return cached
        
        subreddit = self._get_team_subreddit(team_name)
        if not subreddit:
            self.logger.warning("No subreddit mapping found for team: %s", team_name)
            return []
        
        # Use async JSON API
        posts = await self._fetch_posts_json(subreddit, limit=limit)
        
        # Add comments if requested (fetch in parallel for better performance)
        if include_comments and posts:
            import asyncio
            
            async def fetch_post_comments(post: Dict[str, Any]) -> None:
                post_id = post['url'].split('/')[-3] if '/' in post['url'] else None
                if post_id:
                    comments = await self._fetch_comments_json(post_id)
                    post['comments'] = comments
            
            # Fetch comments for top 5 posts in parallel
            await asyncio.gather(*[fetch_post_comments(post) for post in posts[:5]])
        
        # Cache the result
        if self.cache_service:
            cache_key = f"reddit:team:{team_name.lower()}:{limit}"
            self.cache_service.cache.set(cache_key, posts, expire=self.cache_ttl)
        
        return posts
    
    async def fetch_nba_posts(
        self,
        limit: int = 25,
        include_comments: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent posts from r/nba (async)
        
        Args:
            limit: Maximum number of posts to fetch
            include_comments: Whether to include sample comments
            
        Returns:
            List of post dictionaries with text and URLs
        """
        # Check cache
        if self.cache_service:
            cache_key = f"reddit:nba:{limit}"
            cached = self.cache_service.cache.get(cache_key)
            if cached:
                self.logger.info("Cache hit for r/nba posts")
                return cached
        
        # Use async JSON API
        posts = await self._fetch_posts_json('nba', limit=limit)
        
        # Add comments if requested (fetch in parallel)
        if include_comments and posts:
            import asyncio
            
            async def fetch_post_comments(post: Dict[str, Any]) -> None:
                post_id = post['url'].split('/')[-3] if '/' in post['url'] else None
                if post_id:
                    comments = await self._fetch_comments_json(post_id)
                    post['comments'] = comments
            
            # Fetch comments for top 5 posts in parallel
            await asyncio.gather(*[fetch_post_comments(post) for post in posts[:5]])
        
        # Cache the result
        if self.cache_service:
            cache_key = f"reddit:nba:{limit}"
            self.cache_service.cache.set(cache_key, posts, expire=self.cache_ttl)
        
        return posts


# Keep the old class for backward compatibility but mark as deprecated
class RedditService:
    """
    DEPRECATED: Use AsyncRedditService instead.
    
    This synchronous version is kept for backward compatibility
    but blocks the event loop. Migrate to AsyncRedditService.
    """
    
    def __init__(self, *args, **kwargs):
        import warnings
        warnings.warn(
            "RedditService is deprecated and blocks the event loop. "
            "Use AsyncRedditService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # Delegate to async service for actual implementation
        self._async_service = AsyncRedditService(*args, **kwargs)
    
    def fetch_team_posts(self, team_name: str, limit: int = 10, include_comments: bool = True):
        """Synchronous wrapper - blocks event loop (deprecated)"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in async context, create a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._async_service.fetch_team_posts(team_name, limit, include_comments)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self._async_service.fetch_team_posts(team_name, limit, include_comments)
                )
        except RuntimeError:
            return asyncio.run(
                self._async_service.fetch_team_posts(team_name, limit, include_comments)
            )
    
    def fetch_nba_posts(self, limit: int = 25, include_comments: bool = True):
        """Synchronous wrapper - blocks event loop (deprecated)"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._async_service.fetch_nba_posts(limit, include_comments)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self._async_service.fetch_nba_posts(limit, include_comments)
                )
        except RuntimeError:
            return asyncio.run(
                self._async_service.fetch_nba_posts(limit, include_comments)
            )
