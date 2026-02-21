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
from .espn_provider import ESPNProvider

# Shared singletons — import these in routes instead of creating new instances,
# so the ESPN team-list and stats caches persist across all requests.
basketball_provider = BasketballProvider()

__all__ = [
    'BasketballProvider',
    'ESPNProvider',
    'basketball_provider',
]
