# Running BallPulse Locally

This guide will walk you through setting up and running the BallPulse application on your local machine.

## Quick Start Options

You can run BallPulse in two ways:

| Method | Best For | Requirements |
|--------|----------|--------------|
| **Docker** | Quick setup, consistent environment | Docker & Docker Compose |
| **Python venv** | Development, customization | Python 3.11+, pip, venv |

**Recommendation:** Use Docker for the fastest setup. Use Python venv if you're actively developing.

---

## Option 1: Running with Docker (Recommended)

### Prerequisites

- Docker installed on your system
- Docker Compose (usually included with Docker Desktop)

**Verify Docker installation:**
```bash
docker --version
docker-compose --version
```

If not installed, download from [docker.com](https://www.docker.com/get-started)

### Step-by-Step Docker Setup

#### 1. Navigate to Project Directory

```bash
cd path/to/BallPulse
```

#### 2. Build and Run with Docker Compose

```bash
docker-compose up --build
```

This will:
- Build the Docker image from the `Dockerfile`
- Start the BallPulse service on port 8000
- Show logs in your terminal

#### 3. Access the Application

Once running, the application will be available at:
- **Frontend UI:** http://localhost:8000/
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

#### 4. Stop the Application

Press `Ctrl+C` in the terminal, or run:

```bash
docker-compose down
```

### Alternative: Using Docker Directly

If you prefer not to use docker-compose:

```bash
# Build the image
docker build -t ballpulse:latest .

# Run the container
docker run --rm -p 8000:8000 ballpulse:latest
```

### Docker Troubleshooting

**Port Already in Use:**
Edit `docker-compose.yml` and change the port mapping:
```yaml
ports:
  - "8001:8000"  # Use port 8001 on your host
```

**View Container Logs:**
```bash
docker-compose logs -f
```

**Rebuild After Code Changes:**
```bash
docker-compose up --build
```

**Run in Background (Detached Mode):**
```bash
docker-compose up -d
```

**Stop Background Container:**
```bash
docker-compose down
```

**Run Tests in Docker:**
```bash
docker-compose exec ballpulse pytest
```

---

## Option 2: Running with Python Virtual Environment

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Virtual environment support (venv)

### Step-by-Step Python Setup

### 1. Navigate to the Project Directory

Navigate to wherever you cloned or extracted the BallPulse project:

```bash
cd path/to/BallPulse
```

Replace `path/to/BallPulse` with the actual path to your project directory.

### 2. Create a Virtual Environment

Create an isolated Python environment for this project:

```bash
python3.11 -m venv venv
```

This creates a `venv` directory with a fresh Python environment.

### 3. Activate the Virtual Environment

**On macOS/Linux:**
```bash
source venv/bin/activate
```

**On Windows:**
```bash
venv\Scripts\activate
```

You should see `(venv)` in your terminal prompt, indicating the virtual environment is active.

### 4. Install Dependencies

Install all required Python packages:

**Option 1: Using pip (standard)**
```bash
pip install -r requirements.txt
```

**Option 2: Using Makefile (simpler)**
```bash
make install
```

Both methods will install the same dependencies.

This will install:
- FastAPI and Uvicorn (web framework and server)
- Pydantic (data validation)
- pytest (testing framework)
- diskcache (caching)
- nba-api (NBA statistics)
- requests, praw, feedparser (Reddit integration)

### 5. Set Up Environment Variables (Optional)

Copy the example environment file and edit if needed:

```bash
cp .env.example .env
```

The `.env` file is optional. The application will work without it, but you can configure:
- API host/port settings
- Reddit API credentials (for PRAW - optional)
- Logging level

**Note:** For Reddit API (PRAW), you only need credentials if you want to use authenticated access. The service works with public JSON endpoints by default.

### 6. Run the Application

Start the FastAPI development server. You have two options:

**Option 1: Run from project root (recommended)**
```bash
uvicorn src.app.main:app --reload
```

**Option 2: Add src to PYTHONPATH and run**
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
uvicorn app.main:app --reload
```

The `--reload` flag enables auto-reload on code changes, which is useful during development.

**Alternative: Using Makefile (Simpler)**
```bash
make run
```

This is equivalent to `uvicorn src.app.main:app --reload` and requires the virtual environment to be activated.

You should see output like:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

## Accessing the Application

Once running (via Docker or Python), the application will be available at:

- **Frontend UI:** http://localhost:8000/
- **API Base URL:** http://localhost:8000
- **Interactive API Documentation (Swagger UI):** http://localhost:8000/docs
- **Alternative API Documentation (ReDoc):** http://localhost:8000/redoc

### Available Endpoints

1. **Health Check:**
   ```bash
   curl http://localhost:8000/health
   ```
   Returns: `{"status": "healthy"}`

2. **Compare Teams:**
   ```bash
   curl -X POST "http://localhost:8000/compare" \
     -H "Content-Type: application/json" \
     -d '{
       "team1": "Lakers",
       "team2": "Warriors",
       "sport": "basketball"
     }'
   ```

   Or with context:
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

## Running Tests

**Using pytest directly:**
```bash
pytest              # Run all tests
pytest -v           # Verbose output
pytest tests/test_health.py  # Run specific test file
```

**Using Makefile (simpler):**
```bash
make test           # Run all tests
make test-verbose   # Run with verbose output
```

**Verify Installation:**
After installation, run a quick test to verify everything works:
```bash
pytest tests/test_health.py -v
```

You should see the health check test pass.

## Stopping the Application

Press `Ctrl+C` in the terminal where the server is running to stop the application.

## Deactivating the Virtual Environment

When you're done working, deactivate the virtual environment:

```bash
deactivate
```

## Common Commands Quick Reference

### Docker Commands
```bash
docker-compose up --build    # Build and start
docker-compose up -d         # Start in background
docker-compose down          # Stop
docker-compose logs -f       # View logs
docker-compose exec ballpulse pytest  # Run tests
```

### Python venv Commands
```bash
source venv/bin/activate     # Activate (macOS/Linux)
venv\Scripts\activate        # Activate (Windows)
make install                 # Install dependencies
make run                     # Run application
make test                    # Run tests
make clean                   # Clean cache
deactivate                   # Deactivate venv
```

## Troubleshooting

### Port Already in Use

If port 8000 is already in use, specify a different port:

```bash
uvicorn src.app.main:app --reload --port 8001
```

### Import Errors

If you see import errors, make sure:
1. The virtual environment is activated (you should see `(venv)` in your prompt)
2. All dependencies are installed: `pip install -r requirements.txt` or `make install`
3. You're in the project root directory
4. Python version is 3.11 or higher: `python3.11 --version`

**Quick fix:**
```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

### Cache Directory

The application creates a `.cache` directory for caching. This is normal and can be ignored or added to `.gitignore`.

### NBA API Rate Limits

The NBA API (nba-api library) may have rate limits. If you encounter issues, the provider will gracefully fall back to placeholder data.

### Reddit API

Reddit's public JSON endpoints work without authentication. If you want to use PRAW with authentication:
1. Create a Reddit app at https://www.reddit.com/prefs/apps
2. Get your client ID and secret
3. Add them to your `.env` file:
   ```
   REDDIT_CLIENT_ID=your_client_id
   REDDIT_CLIENT_SECRET=your_client_secret
   REDDIT_USER_AGENT=BallPulse/1.0
   ```

## Next Steps

- ✅ **Verify installation:** Run `pytest tests/test_health.py` to confirm everything works
- 📚 **Explore API docs:** Visit http://localhost:8000/docs for interactive API documentation
- 🏀 **Try team comparisons:** Use the frontend at http://localhost:8000/ or test the API directly
- 📊 **Check logs:** Monitor cache hits/misses and API calls in the terminal output
- 🧪 **Review tests:** Check `tests/` directory to understand expected API behavior
- 🔍 **Test endpoints:** Try the `/teams`, `/matchup`, and `/history` endpoints

## Additional Resources

- **Project README:** See `README.md` for API examples and project overview
- **Makefile commands:** Run `make help` to see all available commands
- **API Documentation:** Full Swagger UI available at http://localhost:8000/docs when running

