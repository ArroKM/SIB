#!/usr/bin/env python3
"""
Application entry point.
Run with: python run.py
"""
from app import create_app
from app.config import Config
from app.database import init_db


def main():
    """Initialize and run the application."""
    app = create_app()

    # Initialize database
    init_db()

    print(f"🚀 {Config.APP_NAME}")
    print("📄 Open http://localhost:8000")

    app.run(debug=True, host='0.0.0.0', port=8000)


if __name__ == '__main__':
    main()
