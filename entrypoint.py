#!/usr/bin/env python3
"""
Entry point for deployment (Render/Railway/Vercel-compatible)
"""
import os
import uvicorn
from main import app  # ← import from your backend/main.py

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
