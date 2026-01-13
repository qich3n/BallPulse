"""
Data providers for fetching sports statistics and information.

Current providers:
- BasketballProvider: NBA statistics using nba_api

Future providers:
- ESPNProvider: ESPN unofficial API integration
- SoccerProvider: Soccer/football statistics
- MLBProvider: Major League Baseball statistics
"""

from .basketball_provider import BasketballProvider

# Future imports (commented until implemented):
# from .espn_provider import ESPNProvider

__all__ = [
    'BasketballProvider',
    # 'ESPNProvider',  # Future implementation
]
