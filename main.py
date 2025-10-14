#!/usr/bin/env python3
"""
Simple entry point for deployment services that might look for main.py
"""
import os
import uvicorn
from src.api import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
