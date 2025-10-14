#!/usr/bin/python3.10

import sys
import os

# Add your project directory to the sys.path
path = '/home/yourusername/lostnfound_ml'  # Update this path
if path not in sys.path:
    sys.path.append(path)

from src.api import app as application

if __name__ == "__main__":
    application.run()
