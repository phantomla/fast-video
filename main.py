# Entry-point shim — the real application lives in app/main.py
# Run with:  uvicorn app.main:app --reload
from app.main import app  # noqa: F401

