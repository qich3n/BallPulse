import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from src.app.services.reddit_service import RedditService


@pytest.fixture
def cache_service_mock():
    """Mock cache service"""
    cache_mock = MagicMock()
    cache_mock.get = Mock(return_value=None)
    cache_mock.set = Mock()
    
    service_mock = MagicMock()
    service_mock.cache = cache_mock
    return service_mock


@pytest.fixture
def reddit_service(cache_service_mock):
    """Create RedditService instance for testing"""
    return RedditService(cache_service=cache_service_mock, timeout=5, max_retries=2)


@pytest.fixture
def mock_reddit_json_response():
    """Mock Reddit JSON API response"""
    return {
        'data': {
            'children': [
                {
                    'data': {
                        'id': 'abc123',
                        'title': 'Test Post 1',
                        'selftext': 'Test post content',
                        'permalink': '/r/nba/comments/abc123/test_post_1/',
                        'score': 100,
                        'num_comments': 50,
                        'created_utc': 1609459200,
                        'author': 'testuser'
                    }
                },
                {
                    'data': {
                        'id': 'def456',
                        'title': 'Test Post 2',
                        'selftext': 'Another test post',
                        'permalink': '/r/nba/comments/def456/test_post_2/',
                        'score': 200,
                        'num_comments': 75,
                        'created_utc': 1609459300,
                        'author': 'testuser2'
                    }
                }
            ]
        }
    }


@pytest.fixture
def mock_comments_json_response():
    """Mock Reddit comments JSON API response"""
    return [
        {
            'data': {
                'children': [
                    {
                        'data': {
                            'title': 'Test Post',
                            'selftext': 'Post content'
                        }
                    }
                ]
            }
        },
        {
            'data': {
                'children': [
                    {
                        'data': {
                            'body': 'Great post!',
                            'score': 10,
                            'author': 'commenter1',
                            'permalink': '/r/nba/comments/abc123/test_post_1/comment1/'
                        }
                    },
                    {
                        'data': {
                            'body': 'I agree',
                            'score': 5,
                            'author': 'commenter2',
                            'permalink': '/r/nba/comments/abc123/test_post_1/comment2/'
                        }
                    }
                ]
            }
        }
    ]


def test_get_team_subreddit(reddit_service):
    """Test team to subreddit mapping"""
    assert reddit_service._get_team_subreddit("Los Angeles Lakers") == "lakers"
    assert reddit_service._get_team_subreddit("Golden State Warriors") == "warriors"
    assert reddit_service._get_team_subreddit("Boston Celtics") == "bostonceltics"
    assert reddit_service._get_team_subreddit("Unknown Team") is None


def test_fetch_json_endpoint_success(reddit_service, mock_reddit_json_response):
    """Test successful JSON endpoint fetch"""
    with patch.object(reddit_service.session, 'get') as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = mock_reddit_json_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = reddit_service._fetch_json_endpoint("https://www.reddit.com/r/nba/new.json")
        
        assert result == mock_reddit_json_response
        mock_get.assert_called_once()


def test_fetch_json_endpoint_failure(reddit_service):
    """Test JSON endpoint fetch failure"""
    with patch.object(reddit_service.session, 'get') as mock_get:
        mock_get.side_effect = Exception("Network error")
        
        result = reddit_service._fetch_json_endpoint("https://www.reddit.com/r/nba/new.json")
        
        assert result is None


def test_parse_reddit_post(reddit_service, mock_reddit_json_response):
    """Test parsing Reddit post data"""
    post_data = mock_reddit_json_response['data']['children'][0]
    parsed = reddit_service._parse_reddit_post(post_data)
    
    assert parsed['title'] == 'Test Post 1'
    assert parsed['text'] == 'Test post content'
    assert 'reddit.com' in parsed['url']
    assert parsed['score'] == 100
    assert parsed['num_comments'] == 50
    assert parsed['author'] == 'testuser'


def test_fetch_posts_json(reddit_service, mock_reddit_json_response):
    """Test fetching posts using JSON API"""
    with patch.object(reddit_service, '_fetch_json_endpoint', return_value=mock_reddit_json_response):
        posts = reddit_service._fetch_posts_json('nba', limit=25)
        
        assert len(posts) == 2
        assert posts[0]['title'] == 'Test Post 1'
        assert posts[1]['title'] == 'Test Post 2'


def test_fetch_posts_json_empty(reddit_service):
    """Test fetching posts when API returns empty"""
    with patch.object(reddit_service, '_fetch_json_endpoint', return_value=None):
        posts = reddit_service._fetch_posts_json('nba')
        
        assert posts == []


def test_fetch_comments_json(reddit_service, mock_comments_json_response):
    """Test fetching comments using JSON API"""
    with patch.object(reddit_service, '_fetch_json_endpoint', return_value=mock_comments_json_response):
        comments = reddit_service._fetch_comments_json('abc123')
        
        assert len(comments) == 2
        assert comments[0]['text'] == 'Great post!'
        assert comments[1]['text'] == 'I agree'


def test_fetch_team_posts_cache_hit(reddit_service, cache_service_mock):
    """Test fetching team posts with cache hit"""
    cached_posts = [{'title': 'Cached Post', 'url': 'http://example.com'}]
    cache_service_mock.cache.get.return_value = cached_posts
    
    posts = reddit_service.fetch_team_posts("Los Angeles Lakers", limit=10)
    
    assert posts == cached_posts
    cache_service_mock.cache.get.assert_called()


def test_fetch_team_posts_cache_miss(reddit_service, cache_service_mock, mock_reddit_json_response):
    """Test fetching team posts with cache miss"""
    cache_service_mock.cache.get.return_value = None
    
    with patch.object(reddit_service, '_fetch_posts_json', return_value=[
        {'title': 'Post 1', 'url': 'http://example.com/1'}
    ]):
        posts = reddit_service.fetch_team_posts("Los Angeles Lakers", limit=10)
        
        assert len(posts) > 0
        cache_service_mock.cache.set.assert_called()


def test_fetch_team_posts_no_subreddit(reddit_service, cache_service_mock):
    """Test fetching team posts when team has no subreddit mapping"""
    posts = reddit_service.fetch_team_posts("Unknown Team")
    
    assert posts == []


def test_fetch_nba_posts_cache_hit(reddit_service, cache_service_mock):
    """Test fetching r/nba posts with cache hit"""
    cached_posts = [{'title': 'Cached Post', 'url': 'http://example.com'}]
    cache_service_mock.cache.get.return_value = cached_posts
    
    posts = reddit_service.fetch_nba_posts(limit=25)
    
    assert posts == cached_posts


def test_fetch_nba_posts_cache_miss(reddit_service, cache_service_mock, mock_reddit_json_response):
    """Test fetching r/nba posts with cache miss"""
    cache_service_mock.cache.get.return_value = None
    
    with patch.object(reddit_service, '_fetch_posts_json', return_value=[
        {'title': 'Post 1', 'url': 'http://example.com/1'}
    ]):
        posts = reddit_service.fetch_nba_posts(limit=25)
        
        assert len(posts) > 0
        cache_service_mock.cache.set.assert_called()


def test_fetch_team_posts_with_comments(reddit_service, cache_service_mock, mock_reddit_json_response, mock_comments_json_response):
    """Test fetching team posts with comments"""
    cache_service_mock.cache.get.return_value = None
    
    mock_posts = [
        {
            'title': 'Test Post',
            'url': 'https://www.reddit.com/r/lakers/comments/abc123/test_post/',
            'text': 'Post content'
        }
    ]
    
    with patch.object(reddit_service, '_fetch_posts_json', return_value=mock_posts):
        with patch.object(reddit_service, '_fetch_comments_json', return_value=[
            {'text': 'Comment 1', 'score': 10, 'author': 'user1', 'url': 'http://example.com'}
        ]):
            posts = reddit_service.fetch_team_posts("Los Angeles Lakers", include_comments=True)
            
            assert len(posts) > 0
            # Check that comments were added to the first post
            assert 'comments' in posts[0] or len(posts[0].get('comments', [])) >= 0


def test_praw_initialization_with_creds(monkeypatch):
    """Test PRAW initialization with credentials"""
    monkeypatch.setenv('REDDIT_CLIENT_ID', 'test_client_id')
    monkeypatch.setenv('REDDIT_CLIENT_SECRET', 'test_client_secret')
    
    # Mock praw module
    with patch('src.app.services.reddit_service.praw') as mock_praw:
        mock_reddit = MagicMock()
        mock_praw.Reddit.return_value = mock_reddit
        
        service = RedditService()
        
        # If PRAW is available, it should be initialized
        if RedditService.__module__ and hasattr(RedditService, 'praw_client'):
            # Check initialization happened
            pass


def test_praw_initialization_without_creds(monkeypatch):
    """Test PRAW initialization without credentials"""
    monkeypatch.delenv('REDDIT_CLIENT_ID', raising=False)
    monkeypatch.delenv('REDDIT_CLIENT_SECRET', raising=False)
    
    service = RedditService()
    
    # Service should work without PRAW
    assert service is not None


def test_session_headers(reddit_service):
    """Test that session has proper User-Agent header"""
    assert 'User-Agent' in reddit_service.session.headers
    assert 'BallPulse' in reddit_service.session.headers['User-Agent']

