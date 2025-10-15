#!/usr/bin/env python3
"""
Entry point for deployment (Render/Railway/Vercel-compatible)
"""
import os
import uvicorn
from src.api import app  

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
