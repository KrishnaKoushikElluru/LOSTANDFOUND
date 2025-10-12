# LostNFound

## Setup
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

## Create DB from seed
sqlite3 lost_and_found.db < seed/seed_dump.sql

## Start API
uvicorn src.api:app --reload --host 127.0.0.1 --port 8000

## Open frontend
open frontend/index.html
