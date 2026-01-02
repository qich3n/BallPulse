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

The API will be available at `http://localhost:8000`

- API documentation: `http://localhost:8000/docs`
- Alternative docs: `http://localhost:8000/redoc`

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
- `POST /compare` - Compare endpoint (stub)
