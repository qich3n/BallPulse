# BallPulse 🏀

A FastAPI application for analyzing and comparing NBA teams using statistics, sentiment analysis, and Reddit data.

## Features

- **Team Statistics**: Fetch recent team stats (last 10 games) using NBA API
- **Sentiment Analysis**: Analyze Reddit posts and comments using VADER sentiment analysis
- **Team Comparison**: Compare two teams with detailed analysis including:
  - Pros and cons based on stats, injuries, and sentiment
  - Win probability predictions using sigmoid function
  - Score breakdowns and confidence levels
  - Sentiment summaries from Reddit data
- **Caching**: Disk-based caching with TTL support for improved performance
- **Frontend**: Modern web interface for easy team comparisons

## Quick Start

1. **Create virtual environment:**
   ```bash
   python3.11 -m venv venv
   ```

2. **Activate it:**
   ```bash
   source venv/bin/activate  # macOS/Linux
   # or
   venv\Scripts\activate  # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   uvicorn src.app.main:app --reload
   ```

5. **Visit:**
   - Frontend UI: http://localhost:8000/
   - API Docs: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

For detailed setup instructions, see [RUN_LOCALLY.md](RUN_LOCALLY.md).

## API Usage Examples

### Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{"status": "healthy"}
```

### Compare Teams (Basic)

```bash
curl -X POST "http://localhost:8000/compare" \
  -H "Content-Type: application/json" \
  -d '{
    "team1": "Lakers",
    "team2": "Warriors",
    "sport": "basketball"
  }'
```

### Compare Teams (With Context)

```bash
curl -X POST "http://localhost:8000/compare" \
  -H "Content-Type: application/json" \
  -d '{
    "team1": "Lakers",
    "team2": "Warriors",
    "sport": "basketball",
    "context": {
      "gameDate": "2024-01-15",
      "injuries": ["LeBron James - questionable", "Steph Curry - out"]
    }
  }'
```

### Example Response

```json
{
  "team1": {
    "pros": [
      "Excellent shooting efficiency",
      "Strong rebounding performance",
      "Positive fan and community sentiment"
    ],
    "cons": [
      "Turnover-prone in key situations",
      "Room for improvement in key areas"
    ],
    "stats_summary": "Averaging 44.5 rebounds per game, 46.5% field goal percentage, 13.2 turnovers per game, +4.2 point differential",
    "sentiment_summary": "Overall sentiment is positive (compound score: 0.45). Sentiment distribution: 60% positive, 25% neutral, 15% negative."
  },
  "team2": {
    "pros": [...],
    "cons": [...],
    "stats_summary": "...",
    "sentiment_summary": "..."
  },
  "matchup": {
    "predicted_winner": "Lakers",
    "win_probability": 0.625,
    "score_breakdown": "Predicted final score: Lakers 115-109 Warriors",
    "confidence_label": "High confidence"
  },
  "sources": {
    "reddit": ["https://www.reddit.com/r/lakers/...", "..."],
    "stats": ["NBA API stats for Lakers", "NBA API stats for Warriors"]
  }
}
```

## Using the Makefile

For convenience, use the Makefile:

```bash
# Run the application
make run

# Run tests
make test

# Run tests with verbose output
make test-verbose

# Install dependencies
make install
```

## Testing

Run the test suite:

```bash
pytest
```

Run with verbose output:

```bash
pytest -v
```

Run specific test file:

```bash
pytest tests/test_health.py
```

## Project Structure

```
BallPulse/
├── src/
│   └── app/
│       ├── __init__.py
│       ├── main.py              # FastAPI application
│       ├── routes/              # API endpoints
│       │   ├── health.py
│       │   └── compare.py
│       ├── services/            # Business logic services
│       │   ├── cache_service.py
│       │   ├── reddit_service.py
│       │   ├── sentiment_service.py
│       │   ├── scoring_service.py
│       │   └── proscons_service.py
│       ├── providers/           # Data providers
│       │   └── basketball_provider.py
│       └── models/              # Data models
├── static/                      # Frontend files
│   └── index.html
├── tests/                       # Test files
├── requirements.txt
├── pytest.ini
├── Makefile
├── .env.example
├── README.md
└── RUN_LOCALLY.md
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Optional environment variables:
- `REDDIT_CLIENT_ID`: Reddit API client ID (for PRAW authentication)
- `REDDIT_CLIENT_SECRET`: Reddit API client secret
- `REDDIT_USER_AGENT`: User agent for Reddit API requests
- `LOG_LEVEL`: Logging level (INFO, DEBUG, etc.)

## Troubleshooting

### Port Already in Use

If port 8000 is already in use:

```bash
uvicorn src.app.main:app --reload --port 8001
```

### Import Errors

If you see import errors:
1. Ensure virtual environment is activated: `source venv/bin/activate`
2. Verify dependencies are installed: `pip install -r requirements.txt`
3. Make sure you're in the project root directory

### NBA API Rate Limits

The NBA API may have rate limits. The application gracefully falls back to placeholder data if the API is unavailable.

### Reddit API Issues

Reddit's public JSON endpoints work without authentication. If you encounter issues:
- Check your internet connection
- Verify Reddit is accessible
- The service will continue to work but without Reddit data

### Cache Issues

If you experience stale data:
- Clear the cache directory: `rm -rf .cache`
- Reduce cache TTL in the code if needed

### Module Not Found Errors

Ensure you're using the correct Python version (3.11+) and all dependencies are installed:

```bash
python3.11 --version
pip install -r requirements.txt
```

## Disclaimer

**This application is for informational and entertainment purposes only.**

- The predictions, analyses, and recommendations provided by BallPulse are based on statistical models and data analysis algorithms
- **This is NOT betting or gambling advice**
- Predictions are estimates based on historical data and should not be used for actual betting or wagering
- Sports outcomes are inherently unpredictable and past performance does not guarantee future results
- Users should make their own informed decisions and consult with legal betting advisors if they choose to engage in sports betting
- The developers and contributors of BallPulse are not responsible for any losses or damages resulting from the use of this application

## Roadmap

### Current Features
- ✅ NBA team comparison
- ✅ Statistics analysis
- ✅ Reddit sentiment analysis
- ✅ Win probability predictions
- ✅ Web frontend

### Planned Features

#### SoccerProvider (Future)
- Support for major soccer leagues (Premier League, La Liga, Serie A, etc.)
- Team statistics from soccer APIs
- Match prediction based on form, head-to-head, and home/away records
- Integration with soccer subreddits for sentiment analysis

#### MLBProvider (Future)
- Major League Baseball team comparison
- Baseball-specific statistics (ERA, batting average, OPS, etc.)
- Pitcher vs. batter matchup analysis
- Integration with r/baseball and team subreddits

#### Additional Enhancements
- Real-time injury updates
- Historical matchup analysis
- Advanced machine learning models for predictions
- Support for more sports (NFL, NHL, etc.)
- User preferences and saved comparisons
- Export comparisons to PDF/CSV

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the MIT License.

## Support

For issues, questions, or suggestions, please open an issue on GitHub.
