import logging
import re
from typing import List, Dict, Any, Tuple
from collections import Counter
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)


class SentimentService:
    """Service for analyzing sentiment in Reddit text using VADER"""
    
    def __init__(self):
        """Initialize the sentiment service"""
        self.logger = logging.getLogger(__name__)
        self.analyzer = SentimentIntensityAnalyzer()
        # Common stopwords to filter from keywords
        self.stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
            'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'me', 'him', 'her', 'us', 'them', 'what', 'which', 'who', 'whom',
            'whose', 'where', 'when', 'why', 'how', 'all', 'each', 'every', 'both',
            'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
            'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'now'
        }
    
    def _extract_text_from_reddit_data(self, reddit_posts: List[Dict[str, Any]]) -> List[str]:
        """
        Extract text content from Reddit posts and comments
        
        Args:
            reddit_posts: List of Reddit post dictionaries
            
        Returns:
            List of text strings
        """
        texts = []
        for post in reddit_posts:
            # Add post title and text
            if post.get('title'):
                texts.append(post['title'])
            if post.get('text'):
                texts.append(post['text'])
            
            # Add comments
            if post.get('comments'):
                for comment in post['comments']:
                    if comment.get('text'):
                        texts.append(comment['text'])
        
        return texts
    
    def _calculate_keywords(self, texts: List[str], top_n: int = 10) -> List[Tuple[str, int]]:
        """
        Extract top keywords using simple frequency analysis
        
        Args:
            texts: List of text strings
            top_n: Number of top keywords to return
            
        Returns:
            List of (keyword, frequency) tuples
        """
        # Combine all text
        all_text = ' '.join(texts).lower()
        
        # Extract words (alphanumeric + hyphens, at least 3 chars)
        words = re.findall(r'\b[a-z0-9-]{3,}\b', all_text)
        
        # Filter out stopwords and very short words
        words = [w for w in words if w not in self.stopwords and len(w) >= 3]
        
        # Count frequencies
        word_counts = Counter(words)
        
        # Return top N keywords
        return word_counts.most_common(top_n)
    
    def _get_sample_quotes(
        self,
        texts: List[str],
        sentiment_scores: List[Dict[str, float]],
        sentiment_type: str,
        max_quotes: int = 3
    ) -> List[str]:
        """
        Get sample quotes of a specific sentiment type
        
        Args:
            texts: List of text strings
            sentiment_scores: List of sentiment score dictionaries
            sentiment_type: 'pos', 'neg', or 'neu'
            max_quotes: Maximum number of quotes to return
            
        Returns:
            List of quote strings
        """
        quotes = []
        
        for text, scores in zip(texts, sentiment_scores):
            compound = scores['compound']
            
            # Determine if this text matches the sentiment type
            if sentiment_type == 'pos' and compound > 0.5:
                quotes.append(text[:200])  # Limit quote length
            elif sentiment_type == 'neg' and compound < -0.5:
                quotes.append(text[:200])
            elif sentiment_type == 'neu' and -0.1 <= compound <= 0.1:
                quotes.append(text[:200])
            
            if len(quotes) >= max_quotes:
                break
        
        return quotes
    
    def analyze_sentiment(self, reddit_posts: List[Dict[str, Any]]) -> str:
        """
        Analyze sentiment from Reddit posts and comments
        
        Args:
            reddit_posts: List of Reddit post dictionaries from RedditService
            
        Returns:
            Formatted sentiment summary string
        """
        if not reddit_posts:
            return "No Reddit data available for sentiment analysis."
        
        # Extract all text
        texts = self._extract_text_from_reddit_data(reddit_posts)
        
        if not texts:
            return "No text content found in Reddit data."
        
        # Analyze sentiment for each text
        sentiment_scores = []
        for text in texts:
            scores = self.analyzer.polarity_scores(text)
            sentiment_scores.append(scores)
        
        # Calculate average compound score
        avg_compound = sum(s['compound'] for s in sentiment_scores) / len(sentiment_scores)
        
        # Calculate distribution
        pos_count = sum(1 for s in sentiment_scores if s['compound'] > 0.05)
        neg_count = sum(1 for s in sentiment_scores if s['compound'] < -0.05)
        neu_count = len(sentiment_scores) - pos_count - neg_count
        total = len(sentiment_scores)
        
        pos_pct = (pos_count / total * 100) if total > 0 else 0
        neg_pct = (neg_count / total * 100) if total > 0 else 0
        neu_pct = (neu_count / total * 100) if total > 0 else 0
        
        # Get top keywords
        keywords = self._calculate_keywords(texts, top_n=5)
        keyword_list = [kw[0] for kw in keywords]
        
        # Get sample quotes
        positive_quotes = self._get_sample_quotes(texts, sentiment_scores, 'pos', max_quotes=2)
        negative_quotes = self._get_sample_quotes(texts, sentiment_scores, 'neg', max_quotes=2)
        
        # Build summary string
        summary_parts = []
        
        # Overall sentiment
        if avg_compound > 0.5:
            overall = "very positive"
        elif avg_compound > 0.1:
            overall = "positive"
        elif avg_compound > -0.1:
            overall = "neutral"
        elif avg_compound > -0.5:
            overall = "negative"
        else:
            overall = "very negative"
        
        summary_parts.append(
            f"Overall sentiment is {overall} (compound score: {avg_compound:.2f}). "
        )
        
        # Distribution
        summary_parts.append(
            f"Sentiment distribution: {pos_pct:.0f}% positive, {neu_pct:.0f}% neutral, "
            f"{neg_pct:.0f}% negative. "
        )
        
        # Keywords
        if keyword_list:
            summary_parts.append(f"Key topics: {', '.join(keyword_list[:5])}. ")
        
        # Sample quotes
        if positive_quotes:
            summary_parts.append(f"Sample positive sentiment: \"{positive_quotes[0][:100]}...\" ")
        if negative_quotes:
            summary_parts.append(f"Sample negative sentiment: \"{negative_quotes[0][:100]}...\"")
        
        return ''.join(summary_parts).strip()
    
    def analyze_sentiment_detailed(self, reddit_posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze sentiment and return detailed results
        
        Args:
            reddit_posts: List of Reddit post dictionaries from RedditService
            
        Returns:
            Dictionary with detailed sentiment analysis results
        """
        if not reddit_posts:
            return {
                'avg_compound': 0.0,
                'distribution': {'pos': 0, 'neu': 0, 'neg': 0},
                'keywords': [],
                'positive_quotes': [],
                'negative_quotes': []
            }
        
        texts = self._extract_text_from_reddit_data(reddit_posts)
        
        if not texts:
            return {
                'avg_compound': 0.0,
                'distribution': {'pos': 0, 'neu': 0, 'neg': 0},
                'keywords': [],
                'positive_quotes': [],
                'negative_quotes': []
            }
        
        sentiment_scores = [self.analyzer.polarity_scores(text) for text in texts]
        avg_compound = sum(s['compound'] for s in sentiment_scores) / len(sentiment_scores)
        
        pos_count = sum(1 for s in sentiment_scores if s['compound'] > 0.05)
        neg_count = sum(1 for s in sentiment_scores if s['compound'] < -0.05)
        neu_count = len(sentiment_scores) - pos_count - neg_count
        
        keywords = self._calculate_keywords(texts, top_n=10)
        positive_quotes = self._get_sample_quotes(texts, sentiment_scores, 'pos', max_quotes=3)
        negative_quotes = self._get_sample_quotes(texts, sentiment_scores, 'neg', max_quotes=3)
        
        return {
            'avg_compound': round(avg_compound, 3),
            'distribution': {
                'pos': pos_count,
                'neu': neu_count,
                'neg': neg_count,
                'pos_pct': round(pos_count / len(sentiment_scores) * 100, 1),
                'neu_pct': round(neu_count / len(sentiment_scores) * 100, 1),
                'neg_pct': round(neg_count / len(sentiment_scores) * 100, 1)
            },
            'keywords': [{'word': kw[0], 'frequency': kw[1]} for kw in keywords],
            'positive_quotes': positive_quotes,
            'negative_quotes': negative_quotes
        }

