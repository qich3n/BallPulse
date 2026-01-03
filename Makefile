.PHONY: help install run test test-verbose clean

help:
	@echo "BallPulse - NBA Team Comparison API"
	@echo ""
	@echo "Available commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make run          - Run the application"
	@echo "  make test         - Run tests"
	@echo "  make test-verbose - Run tests with verbose output"
	@echo "  make clean        - Clean cache and pyc files"
	@echo "  make help         - Show this help message"

install:
	pip install -r requirements.txt

run:
	uvicorn src.app.main:app --reload

test:
	pytest

test-verbose:
	pytest -v

clean:
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -r {} + 2>/dev/null || true
	rm -rf .cache

