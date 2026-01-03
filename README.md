# BallPulse

A FastAPI application for BallPulse.

## Setup

1. **Create a virtual environment:**
   ```bash
   python3.11 -m venv venv
   ```

2. **Activate the virtual environment:**
   ```bash
   source venv/bin/activate  # On macOS/Linux
   # or
   venv\Scripts\activate  # On Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration values
   ```

## Running the Application

Run the application with uvicorn:

```bash
uvicorn src.app.main:app --reload
```

The application will be available at:

- **Frontend UI:** http://localhost:8000/
- **API documentation:** http://localhost:8000/docs
- **Alternative docs:** http://localhost:8000/redoc

## Running Tests

Run tests with pytest:

```bash
pytest
```

## Project Structure

```
BallPulse/
├── src/
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── health.py
│       │   └── compare.py
│       ├── services/
│       │   └── __init__.py
│       ├── providers/
│       │   └── __init__.py
│       └── models/
│           └── __init__.py
├── tests/
│   ├── __init__.py
│   └── test_health.py
├── requirements.txt
├── pytest.ini
├── .env.example
└── README.md
```

## API Endpoints

- `GET /health` - Health check endpoint
- `POST /compare` - Compare teams endpoint with caching and stats

### Example Compare Request

```bash
curl -X POST "http://localhost:8000/compare" \
  -H "Content-Type: application/json" \
  -d '{
    "team1": "Lakers",
    "team2": "Warriors",
    "sport": "basketball",
    "context": {
      "gameDate": "2024-01-15",
      "injuries": ["Player X - out"]
    }
  }'
```

## Quick Start

1. Create virtual environment: `python3.11 -m venv venv`
2. Activate it: `source venv/bin/activate` (macOS/Linux) or `venv\Scripts\activate` (Windows)
3. Install dependencies: `pip install -r requirements.txt`
4. Run the app: `uvicorn src.app.main:app --reload`
5. Visit: http://localhost:8000/docs for interactive API documentation

For detailed setup instructions, see [RUN_LOCALLY.md](RUN_LOCALLY.md).
