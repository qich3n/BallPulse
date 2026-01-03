import pytest
from src.app.services.sentiment_service import SentimentService


@pytest.fixture
def sentiment_service():
    """Create a SentimentService instance for testing"""
    return SentimentService()


@pytest.fixture
def sample_reddit_posts():
    """Sample Reddit posts data for testing"""
    return [
        {
            'title': 'Lakers are playing amazing basketball this season!',
            'text': 'The team has been on fire lately. Great defense and offense.',
            'url': 'http://example.com/post1',
            'score': 100,
            'comments': [
                {
                    'text': 'I totally agree! LeBron is incredible!',
                    'score': 50,
                    'author': 'user1',
                    'url': 'http://example.com/comment1'
                },
                {
                    'text': 'Best team in the league right now.',
                    'score': 30,
                    'author': 'user2',
                    'url': 'http://example.com/comment2'
                }
            ]
        },
        {
            'title': 'Concerns about Lakers recent performance',
            'text': 'The defense has been terrible. Too many turnovers and bad shooting.',
            'url': 'http://example.com/post2',
            'score': 25,
            'comments': [
                {
                    'text': 'Yeah, they need to step up their game.',
                    'score': 10,
                    'author': 'user3',
                    'url': 'http://example.com/comment3'
                },
                {
                    'text': 'Not impressed with the coaching decisions.',
                    'score': 5,
                    'author': 'user4',
                    'url': 'http://example.com/comment4'
                }
            ]
        },
        {
            'title': 'Lakers stats update',
            'text': 'Current record is 20-15. Average points per game is 112.',
            'url': 'http://example.com/post3',
            'score': 15,
            'comments': [
                {
                    'text': 'Thanks for the update. Interesting stats.',
                    'score': 3,
                    'author': 'user5',
                    'url': 'http://example.com/comment5'
                }
            ]
        }
    ]


def test_analyze_sentiment_with_data(sentiment_service, sample_reddit_posts):
    """Test sentiment analysis with sample Reddit posts"""
    summary = sentiment_service.analyze_sentiment(sample_reddit_posts)
    
    assert isinstance(summary, str)
    assert len(summary) > 0
    assert 'sentiment' in summary.lower() or 'positive' in summary.lower() or 'negative' in summary.lower()


def test_analyze_sentiment_empty_list(sentiment_service):
    """Test sentiment analysis with empty Reddit posts"""
    summary = sentiment_service.analyze_sentiment([])
    
    assert isinstance(summary, str)
    assert "No Reddit data available" in summary


def test_analyze_sentiment_empty_text(sentiment_service):
    """Test sentiment analysis with posts that have no text"""
    empty_posts = [
        {
            'title': '',
            'text': '',
            'url': 'http://example.com',
            'score': 0,
            'comments': []
        }
    ]
    
    summary = sentiment_service.analyze_sentiment(empty_posts)
    assert isinstance(summary, str)
    assert "No text content" in summary


def test_analyze_sentiment_detailed(sentiment_service, sample_reddit_posts):
    """Test detailed sentiment analysis"""
    result = sentiment_service.analyze_sentiment_detailed(sample_reddit_posts)
    
    assert isinstance(result, dict)
    assert 'avg_compound' in result
    assert 'distribution' in result
    assert 'keywords' in result
    assert 'positive_quotes' in result
    assert 'negative_quotes' in result
    
    # Check avg_compound is in valid range
    assert -1.0 <= result['avg_compound'] <= 1.0
    
    # Check distribution structure
    dist = result['distribution']
    assert 'pos' in dist
    assert 'neu' in dist
    assert 'neg' in dist
    assert 'pos_pct' in dist
    assert 'neu_pct' in dist
    assert 'neg_pct' in dist
    
    # Check keywords
    assert isinstance(result['keywords'], list)
    if result['keywords']:
        assert 'word' in result['keywords'][0]
        assert 'frequency' in result['keywords'][0]


def test_analyze_sentiment_detailed_empty(sentiment_service):
    """Test detailed sentiment analysis with empty data"""
    result = sentiment_service.analyze_sentiment_detailed([])
    
    assert result['avg_compound'] == 0.0
    assert result['distribution']['pos'] == 0
    assert result['distribution']['neu'] == 0
    assert result['distribution']['neg'] == 0
    assert result['keywords'] == []
    assert result['positive_quotes'] == []
    assert result['negative_quotes'] == []


def test_extract_text_from_reddit_data(sentiment_service, sample_reddit_posts):
    """Test text extraction from Reddit posts"""
    texts = sentiment_service._extract_text_from_reddit_data(sample_reddit_posts)
    
    assert isinstance(texts, list)
    assert len(texts) > 0
    assert any('Lakers' in text for text in texts)
    assert any('amazing' in text for text in texts)


def test_calculate_keywords(sentiment_service):
    """Test keyword extraction"""
    texts = [
        'Lakers are playing amazing basketball this season!',
        'The team has been on fire lately. Great defense and offense.',
        'I totally agree! LeBron is incredible!',
        'Best team in the league right now.'
    ]
    
    keywords = sentiment_service._calculate_keywords(texts, top_n=5)
    
    assert isinstance(keywords, list)
    assert len(keywords) <= 5
    if keywords:
        assert isinstance(keywords[0], tuple)
        assert len(keywords[0]) == 2  # (word, frequency)


def test_get_sample_quotes_positive(sentiment_service):
    """Test getting positive sample quotes"""
    texts = [
        'This is amazing! Great performance!',
        'I love this team so much!',
        'Terrible game, worst performance ever.'
    ]
    
    sentiment_scores = [
        {'compound': 0.8},  # Very positive
        {'compound': 0.7},  # Positive
        {'compound': -0.9}  # Very negative
    ]
    
    quotes = sentiment_service._get_sample_quotes(texts, sentiment_scores, 'pos', max_quotes=2)
    
    assert isinstance(quotes, list)
    assert len(quotes) <= 2
    assert len(quotes) >= 1  # Should find at least one positive quote


def test_get_sample_quotes_negative(sentiment_service):
    """Test getting negative sample quotes"""
    texts = [
        'This is amazing! Great performance!',
        'I love this team so much!',
        'Terrible game, worst performance ever.',
        'Awful defense and bad coaching.'
    ]
    
    sentiment_scores = [
        {'compound': 0.8},  # Very positive
        {'compound': 0.7},  # Positive
        {'compound': -0.9},  # Very negative
        {'compound': -0.8}   # Very negative
    ]
    
    quotes = sentiment_service._get_sample_quotes(texts, sentiment_scores, 'neg', max_quotes=2)
    
    assert isinstance(quotes, list)
    assert len(quotes) <= 2
    assert len(quotes) >= 1  # Should find at least one negative quote


def test_get_sample_quotes_neutral(sentiment_service):
    """Test getting neutral sample quotes"""
    texts = [
        'The score is 100-95.',
        'Game starts at 8pm.',
        'This is amazing!'
    ]
    
    sentiment_scores = [
        {'compound': 0.0},   # Neutral
        {'compound': -0.05}, # Neutral (just below threshold)
        {'compound': 0.8}    # Positive
    ]
    
    quotes = sentiment_service._get_sample_quotes(texts, sentiment_scores, 'neu', max_quotes=2)
    
    assert isinstance(quotes, list)
    assert len(quotes) <= 2


def test_sentiment_analyzer_initialization(sentiment_service):
    """Test that sentiment analyzer is properly initialized"""
    assert sentiment_service.analyzer is not None
    # Test that it can analyze a simple sentence
    scores = sentiment_service.analyzer.polarity_scores("This is great!")
    assert 'compound' in scores
    assert 'pos' in scores
    assert 'neg' in scores
    assert 'neu' in scores
    assert scores['compound'] > 0  # Should be positive


def test_sentiment_with_only_titles(sentiment_service):
    """Test sentiment analysis with posts that only have titles"""
    posts = [
        {
            'title': 'Great game!',
            'text': '',
            'url': 'http://example.com',
            'score': 10,
            'comments': []
        }
    ]
    
    summary = sentiment_service.analyze_sentiment(posts)
    assert isinstance(summary, str)
    assert len(summary) > 0


def test_sentiment_with_only_comments(sentiment_service):
    """Test sentiment analysis with posts that only have comments"""
    posts = [
        {
            'title': '',
            'text': '',
            'url': 'http://example.com',
            'score': 10,
            'comments': [
                {
                    'text': 'Awesome performance!',
                    'score': 5,
                    'author': 'user1',
                    'url': 'http://example.com/comment'
                }
            ]
        }
    ]
    
    summary = sentiment_service.analyze_sentiment(posts)
    assert isinstance(summary, str)
    assert len(summary) > 0

