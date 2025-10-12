#!/usr/bin/env python3
"""
Sanity script: sync existing SQL rows (lost_items, found_items) into Chroma,
then run queries from images in query_images/ to verify end-to-end.

Assumptions:
- You placed lost_and_found.db in the project root (./lost_and_found.db)
- Your database package is importable as `database` and provides:
    from database import SessionLocal
    from database.models import LostItem, FoundItem
If the import fails, update the import path or add the project root to PYTHONPATH.
"""

import os
import sys
import glob
import uuid
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from tqdm import tqdm
import chromadb
from chromadb.config import Settings
import torch
import clip
import logging

# ----- Make script robust: set cwd to project root (parent of scripts/) -----
THIS_FILE = os.path.abspath(__file__)
PROJECT_ROOT = os.path.dirname(os.path.dirname(THIS_FILE))  # assumes script is in project/scripts/
os.chdir(PROJECT_ROOT)  # now relative paths like ./lost_and_found.db resolve to project root
sys.path.insert(0, PROJECT_ROOT)  # help Python find your `database` package if it's in project root

# ====== ADJUST PATHS / NAMES IF NEEDED ======
DB_FILENAME = "lost_and_found.db"
DB_PATH = os.path.join(PROJECT_ROOT, DB_FILENAME)
if not os.path.exists(DB_PATH):
    print(f"Warning: expected DB file at {DB_PATH} not found.")
    print("Place your lost_and_found.db in the project root (same folder as this script's parent).")
    # we don't exit immediately - you may still have DB configured elsewhere
else:
    print(f"Found DB at: {DB_PATH}")

# Try importing your database session and models
try:
    from database import SessionLocal
    from database.models import LostItem, FoundItem
except Exception as e:
    # Provide clear error for common misconfigurations
    raise ImportError(
        "Could not import database.SessionLocal or database.models (LostItem/FoundItem).\n"
        "Make sure your project root is on PYTHONPATH and that `database` package exists.\n"
        "If your module paths differ, edit the import lines at the top of this script.\n"
        f"Original error: {e}"
    ) from e

# ====== CONFIG ======
PERSIST_DIR = "chroma_db"                # where Chroma will persist its DB
COLLECTION_NAME_LOST = "lost_items_vecs"
COLLECTION_NAME_FOUND = "found_items_vecs"
QUERY_DIR = "data_1"
TOP_K = 5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chroma_sync")

# ====== Helpers ======
def get_image_paths(directory):
    exts = ("*.jpg","*.jpeg","*.png","*.bmp","*.webp")
    paths = []
    for e in exts:
        paths.extend(glob.glob(os.path.join(directory, e)))
    return sorted(paths)

def load_clip_model(device):
    logger.info("Loading CLIP model...")
    model, preprocess = clip.load("ViT-B/32", device=device)
    model.eval()
    return model, preprocess

def image_to_embedding(model, preprocess, path, device):
    img = Image.open(path).convert("RGB")
    inp = preprocess(img).unsqueeze(0).to(device)
    with torch.no_grad():
        emb = model.encode_image(inp)
    emb = emb / emb.norm(dim=-1, keepdim=True)
    return emb.cpu().numpy().squeeze()

def show_results_grid(query_path, match_paths, metadatas, scores):
    n = 1 + len(match_paths)
    cols = min(4, n)
    rows = (n + cols - 1) // cols
    plt.figure(figsize=(4*cols, 3*rows))
    ax = plt.subplot(rows, cols, 1)
    qimg = Image.open(query_path).convert("RGB")
    ax.imshow(qimg); ax.set_title("Query"); ax.axis("off")
    for i, (mp, meta, score) in enumerate(zip(match_paths, metadatas, scores), start=2):
        ax = plt.subplot(rows, cols, i)
        try:
            if mp and os.path.exists(mp):
                img = Image.open(mp).convert("RGB")
                ax.imshow(img)
            else:
                ax.text(0.5, 0.5, "Image not found", ha="center")
        except Exception:
            ax.text(0.5, 0.5, "Image error", ha="center")
        title = f"Rank {i-1}\n{meta.get('item_name','?')} @ {meta.get('location','?')}\nScore={score:.4f}"
        ax.set_title(title)
        ax.axis("off")
    plt.tight_layout()
    plt.show()

# ====== Main ======
def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, preprocess = load_clip_model(device)

    client = chromadb.Client(Settings(persist_directory=PERSIST_DIR))
    coll_lost = client.get_or_create_collection(name=COLLECTION_NAME_LOST)
    coll_found = client.get_or_create_collection(name=COLLECTION_NAME_FOUND)

    session = SessionLocal()

    # --- Sync LostItem rows into Chroma ---
    logger.info("Syncing lost_items from SQL -> Chroma")
    lost_rows = session.query(LostItem).all()
    for row in tqdm(lost_rows, desc="lost_items"):
        if not getattr(row, "image_path", None):
            logger.warning("Skipping row (no image_path): id=%s", getattr(row, "id", None))
            continue
        if not os.path.exists(row.image_path):
            logger.warning("Image file does not exist, skipping: %s (id=%s)", row.image_path, row.id)
            continue
        try:
            emb = image_to_embedding(model, preprocess, row.image_path, device)
        except Exception as e:
            logger.exception("Failed to embed image for id=%s path=%s: %s", row.id, row.image_path, e)
            continue

        chroma_id = str(row.id)  # keep as string
        meta = {
            "table": "lost_items",
            "db_id": chroma_id,
            "item_name": getattr(row, "item_name", None),
            "description": getattr(row, "description", None),
            "location": getattr(row, "location", None),
            "owner_name": getattr(row, "owner_name", None),
            "email": getattr(row, "email", None),
            "image_path": getattr(row, "image_path", None)
        }


        try:
            coll_lost.add(
                ids=[chroma_id],
                embeddings=[emb.tolist()],
                metadatas=[meta],
                documents=[meta.get("description") or ""]
            )
        except Exception as e:
            logger.warning("Could not add id %s to Chroma (maybe exists). Attempting update: %s", chroma_id, e)
            try:
                coll_lost.update(
                    ids=[chroma_id],
                    embeddings=[emb.tolist()],
                    metadatas=[meta],
                    documents=[meta.get("description") or ""]
                )
            except Exception as e2:
                logger.exception("Failed to update existing Chroma id %s: %s", chroma_id, e2)

    # --- Sync FoundItem rows into Chroma ---
    logger.info("Syncing found_items from SQL -> Chroma")
    found_rows = session.query(FoundItem).all()
    for row in tqdm(found_rows, desc="found_items"):
        if not getattr(row, "image_path", None):
            logger.warning("Skipping row (no image_path): id=%s", getattr(row, "id", None))
            continue
        if not os.path.exists(row.image_path):
            logger.warning("Image file does not exist, skipping: %s (id=%s)", row.image_path, row.id)
            continue
        try:
            emb = image_to_embedding(model, preprocess, row.image_path, device)
        except Exception as e:
            logger.exception("Failed to embed image for id=%s path=%s: %s", row.id, row.image_path, e)
            continue

        chroma_id = str(row.id)
        meta = {
            "table": "found_items",
            "db_id": chroma_id,
            "item_name": getattr(row, "item_name", None),
            "description": getattr(row, "description", None),
            "location": getattr(row, "location", None),
            "finder_name": getattr(row, "finder_name", None),
            "email": getattr(row, "email", None),
            "image_path": getattr(row, "image_path", None)
        }


        try:
            coll_found.add(
                ids=[chroma_id],
                embeddings=[emb.tolist()],
                metadatas=[meta],
                documents=[meta.get("description") or ""]
            )
        except Exception as e:
            logger.warning("Could not add id %s to Chroma (maybe exists). Attempting update: %s", chroma_id, e)
            try:
                coll_found.update(
                    ids=[chroma_id],
                    embeddings=[emb.tolist()],
                    metadatas=[meta],
                    documents=[meta.get("description") or ""]
                )
            except Exception as e2:
                logger.exception("Failed to update existing Chroma id %s: %s", chroma_id, e2)

    # Persist Chroma DB
   
    logger.info("Chroma persisted to %s", PERSIST_DIR)

    # --- Query step: run queries from QUERY_DIR and print+visualize results ---
    query_paths = get_image_paths(QUERY_DIR)
    if not query_paths:
        logger.info("No query images found in %s — skipping query step.", QUERY_DIR)
        return

    for qpath in query_paths:
        logger.info("Querying for image: %s", qpath)
        try:
            qemb = image_to_embedding(model, preprocess, qpath, device)
        except Exception as e:
            logger.exception("Failed to embed query image %s: %s", qpath, e)
            continue

        results_lost = coll_lost.query(
            query_embeddings=[qemb.tolist()],
            n_results=TOP_K,
            include=["metadatas", "embeddings", "distances"]
        )
        results_found = coll_found.query(
            query_embeddings=[qemb.tolist()],
            n_results=TOP_K,
            include=["metadatas", "embeddings", "distances"]
        )

        combined = []
        for kind, res in (("lost", results_lost), ("found", results_found)):
            ids = res.get("ids", [[]])[0]
            metadatas = res.get("metadatas", [[]])[0]
            emb_lists = res.get("embeddings", [[]])[0]
            for _id, meta, emb in zip(ids, metadatas, emb_lists):
                score = float(np.dot(qemb, np.array(emb)))
                combined.append((score, kind, str(_id), meta))

        combined.sort(key=lambda x: x[0], reverse=True)
        top = combined[:TOP_K]

        ids_lost = [cid for score, kind, cid, meta in top if kind == "lost"]
        ids_found = [cid for score, kind, cid, meta in top if kind == "found"]
        db_rows = {}
        if ids_lost:
            rows = session.query(LostItem).filter(LostItem.id.in_(ids_lost)).all()
            db_rows.update({str(r.id): r for r in rows})
        if ids_found:
            rows = session.query(FoundItem).filter(FoundItem.id.in_(ids_found)).all()
            db_rows.update({str(r.id): r for r in rows})

        match_paths = []
        match_metas = []
        match_scores = []
        for score, kind, cid, meta in top:
            row_obj = db_rows.get(cid)
            img_path = None
            if row_obj:
                img_path = getattr(row_obj, "image_path", None)
                meta_to_show = {
                    "item_name": getattr(row_obj, "item_name", None),
                    "location": getattr(row_obj, "location", None),
                    "owner_name": getattr(row_obj, "owner_name", None) or getattr(row_obj, "finder_name", None)
                }
            else:
                img_path = meta.get("image_path") or meta.get("filename")
                meta_to_show = meta
            match_paths.append(img_path or "")
            match_metas.append(meta_to_show)
            match_scores.append(score)

        logger.info("Top matches for query %s:", qpath)
        for idx, (score, kind, cid, meta) in enumerate(top, start=1):
            logger.info("%d) [%s] id=%s score=%.4f meta=%s", idx, kind, cid, score, meta)

        show_results_grid(qpath, match_paths, match_metas, match_scores)

if __name__ == "__main__":
    main()
