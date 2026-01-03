import logging
import os
from typing import List, Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Try to import PRAW, but make it optional
try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    praw = None


class RedditService:
    """Service for fetching Reddit posts and comments using public JSON endpoints or PRAW"""
    
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
        timeout: int = 10,
        max_retries: int = 3,
        cache_service: Optional[Any] = None,
        cache_ttl: int = 1800  # 30 minutes
    ):
        """
        Initialize Reddit service
        
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
        
        # Setup requests session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # User-Agent is required by Reddit API
        self.session.headers.update({
            'User-Agent': 'BallPulse/1.0 (Python/RedditService)'
        })
        
        # Initialize PRAW if credentials are available
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
                    self.logger.info("PRAW client initialized with credentials")
                except Exception as e:
                    self.logger.warning(f"Failed to initialize PRAW client: {e}")
    
    def _get_team_subreddit(self, team_name: str) -> Optional[str]:
        """Get subreddit name for a team"""
        team_lower = team_name.lower()
        return self.TEAM_SUBREDDIT_MAP.get(team_lower)
    
    def _fetch_json_endpoint(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch data from Reddit JSON endpoint with retries and timeout
        
        Args:
            url: Reddit JSON API URL
            
        Returns:
            JSON data or None if failed
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching Reddit JSON endpoint {url}: {e}")
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
    
    def _fetch_comments_json(self, post_id: str) -> List[Dict[str, Any]]:
        """
        Fetch comments for a post using JSON API
        
        Args:
            post_id: Reddit post ID (without 't3_' prefix)
            
        Returns:
            List of comment dictionaries
        """
        url = f"https://www.reddit.com/comments/{post_id}.json"
        data = self._fetch_json_endpoint(url)
        
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
    
    def _fetch_posts_json(self, subreddit: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Fetch posts from a subreddit using JSON API
        
        Args:
            subreddit: Subreddit name
            limit: Maximum number of posts to fetch
            
        Returns:
            List of post dictionaries
        """
        url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}"
        data = self._fetch_json_endpoint(url)
        
        if not data:
            return []
        
        posts = []
        children = data.get('data', {}).get('children', [])
        
        for child in children:
            post = self._parse_reddit_post(child)
            posts.append(post)
        
        return posts
    
    def _fetch_posts_praw(self, subreddit: str, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Fetch posts from a subreddit using PRAW
        
        Args:
            subreddit: Subreddit name
            limit: Maximum number of posts to fetch
            
        Returns:
            List of post dictionaries
        """
        if not self.praw_client:
            return []
        
        try:
            subreddit_obj = self.praw_client.subreddit(subreddit)
            posts = []
            
            for submission in subreddit_obj.new(limit=limit):
                posts.append({
                    'title': submission.title,
                    'text': submission.selftext,
                    'url': f"https://www.reddit.com{submission.permalink}",
                    'score': submission.score,
                    'num_comments': submission.num_comments,
                    'created_utc': submission.created_utc,
                    'author': str(submission.author) if submission.author else ''
                })
            
            return posts
        except Exception as e:
            self.logger.error(f"Error fetching posts with PRAW from r/{subreddit}: {e}")
            return []
    
    def _fetch_comments_praw(self, post_url: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch comments for a post using PRAW
        
        Args:
            post_url: Reddit post URL or permalink
            limit: Maximum number of comments to fetch
            
        Returns:
            List of comment dictionaries
        """
        if not self.praw_client:
            return []
        
        try:
            submission = self.praw_client.submission(url=post_url)
            submission.comments.replace_more(limit=0)  # Remove "more comments" placeholders
            
            comments = []
            for comment in submission.comments.list()[:limit]:
                if hasattr(comment, 'body') and comment.body:
                    comments.append({
                        'text': comment.body,
                        'score': comment.score,
                        'author': str(comment.author) if comment.author else '',
                        'url': f"https://www.reddit.com{comment.permalink}"
                    })
            
            return comments
        except Exception as e:
            self.logger.error(f"Error fetching comments with PRAW: {e}")
            return []
    
    def fetch_team_posts(
        self,
        team_name: str,
        limit: int = 10,
        include_comments: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent posts related to a team
        
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
                self.logger.info(f"Cache hit for team posts: {team_name}")
                return cached
        
        subreddit = self._get_team_subreddit(team_name)
        if not subreddit:
            self.logger.warning(f"No subreddit mapping found for team: {team_name}")
            return []
        
        # Try PRAW first if available, otherwise use JSON API
        if self.praw_client:
            posts = self._fetch_posts_praw(subreddit, limit=limit)
        else:
            posts = self._fetch_posts_json(subreddit, limit=limit)
        
        # Add comments if requested
        if include_comments and posts:
            for post in posts[:5]:  # Add comments to top 5 posts
                post_id = post['url'].split('/')[-3] if '/' in post['url'] else None
                if post_id and not self.praw_client:
                    # Extract post ID from URL for JSON API
                    comments = self._fetch_comments_json(post_id)
                    post['comments'] = comments
                elif self.praw_client:
                    comments = self._fetch_comments_praw(post['url'], limit=5)
                    post['comments'] = comments
        
        # Cache the result
        if self.cache_service:
            cache_key = f"reddit:team:{team_name.lower()}:{limit}"
            self.cache_service.cache.set(cache_key, posts, expire=self.cache_ttl)
        
        return posts
    
    def fetch_nba_posts(
        self,
        limit: int = 25,
        include_comments: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent posts from r/nba
        
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
        
        # Try PRAW first if available, otherwise use JSON API
        if self.praw_client:
            posts = self._fetch_posts_praw('nba', limit=limit)
        else:
            posts = self._fetch_posts_json('nba', limit=limit)
        
        # Add comments if requested
        if include_comments and posts:
            for post in posts[:5]:  # Add comments to top 5 posts
                post_id = post['url'].split('/')[-3] if '/' in post['url'] else None
                if post_id and not self.praw_client:
                    comments = self._fetch_comments_json(post_id)
                    post['comments'] = comments
                elif self.praw_client:
                    comments = self._fetch_comments_praw(post['url'], limit=5)
                    post['comments'] = comments
        
        # Cache the result
        if self.cache_service:
            cache_key = f"reddit:nba:{limit}"
            self.cache_service.cache.set(cache_key, posts, expire=self.cache_ttl)
        
        return posts

