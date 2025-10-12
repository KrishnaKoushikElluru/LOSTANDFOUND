# src/main.py
import os
import uuid
from pathlib import Path
from typing import Optional
from PIL import Image
import numpy as np
import chromadb

# Use the same folder your sync script writes to
CHROMA_DIR = os.environ.get("CHROMA_DIR", "./chroma_db")
COLLECTION_LOST = "lost_items_vecs"
COLLECTION_FOUND = "found_items_vecs"

# Import your embedder (your clip_embedder that returns normalized lists)
from src.clip_embedder import CLIPEmbedder

# Create Chroma client always via PersistentClient so it reads the same on-disk db
try:
    from chromadb import PersistentClient as _PersistentClient
    client = _PersistentClient(path=CHROMA_DIR)
except Exception:
    # fallback for older/newer versions
    from chromadb.config import Settings
    client = chromadb.Client(Settings(persist_directory=CHROMA_DIR))

coll_lost = client.get_or_create_collection(COLLECTION_LOST)
coll_found = client.get_or_create_collection(COLLECTION_FOUND)

# create embedder instance (your SentenceTransformer wrapper)
embedder = CLIPEmbedder(model_name="ViT-B/32")

def safe_open_rgb(path: str):
    try:
        return Image.open(path).convert("RGB")
    except Exception as e:
        print("WARN: can't open", path, ":", e)
        return None

def _basename(path):
    return Path(path).name if path else None

def _normalize_meta(meta: dict, target: str):
    """
    Ensure metadata contains consistent keys:
      - table: 'lost_items' or 'found_items'
      - db_id: id in SQL or uuid
      - item_name, description, location
      - owner_name or finder_name
      - email
      - image_path (relative path like uploads/foo.jpg)
      - filename
    """
    meta = dict(meta or {})
    meta.setdefault("table", "found_items" if target == "found" else "lost_items")
    meta.setdefault("db_id", str(meta.get("id") or meta.get("db_id") or uuid.uuid4().hex))
    # make image_path relative if it's absolute Windows path
    imgp = meta.get("image_path") or meta.get("path") or meta.get("filename")
    if imgp:
        imgp = str(imgp).replace("\\", "/")
        fname = imgp.split("/")[-1]
        # prefer uploads/filename if present or keep as given
        if "uploads/" in imgp or imgp.startswith("uploads/"):
            meta["image_path"] = imgp if imgp.startswith("uploads/") else f"uploads/{fname}"
        else:
            # store as uploads/<filename> when image file was saved to uploads folder
            meta["image_path"] = meta.get("image_path") or f"uploads/{fname}"
        meta["filename"] = fname
    else:
        meta["image_path"] = None
        meta["filename"] = None
    # ensure owner/finder/email keys exist (may be None)
    meta["owner_name"] = meta.get("owner_name") or meta.get("finder_name") or meta.get("person_name") or None
    meta["finder_name"] = meta.get("finder_name") or meta.get("owner_name") or None
    meta["email"] = meta.get("email") or None
    return meta

def index_single(path: str, metadata: Optional[dict] = None, target: str = "lost"):
    """
    Index single image into the chosen collection. Provide metadata dict (will be normalized).
    `target` must be 'lost' or 'found'.
    """
    img = safe_open_rgb(path)
    if img is None:
        raise RuntimeError("cannot open image to index: " + str(path))

    emb = embedder.embed_image(img)
    meta = _normalize_meta(metadata or {}, target=target)
    # choose collection & id
    coll = coll_found if target == "found" else coll_lost
    # choose stable id: prefer db_id if present, else base filename
    chroma_id = str(meta.get("db_id") or _basename(path) or uuid.uuid4().hex)
    # embedder returns list-of-floats; ensure numpy -> list
    if hasattr(emb, "tolist"):
        emb_value = emb.tolist()
    else:
        emb_value = list(emb)

    coll.upsert(
        ids=[chroma_id],
        embeddings=[emb_value],
        metadatas=[meta],
        documents=[meta.get("description") or meta.get("item_name") or ""],
    )
    return {"status": "ok", "id": chroma_id, "meta": meta}

def _score_from_distance(d):
    # Chroma returns distances; convert to similarity-like score
    try:
        d = float(d)
        return 1.0 / (1.0 + d)
    except Exception:
        return None

def _extract_first(res, key):
    # chroma returns nested lists in many versions; normalize
    val = res.get(key)
    if val is None:
        return []
    if isinstance(val, list) and len(val) == 1 and isinstance(val[0], list):
        return val[0]
    return val

def query_image(path: str, k: int = 5):
    img = safe_open_rgb(path)
    if img is None:
        return {"results": []}
    q = embedder.embed_image(img)
    # try normal query; include metadatas and distances
    try:
        rl = coll_lost.query(query_embeddings=[q], n_results=k, include=["metadatas", "distances"])
        rf = coll_found.query(query_embeddings=[q], n_results=k, include=["metadatas", "distances"])
    except Exception as e:
        # fallback: try without include or brute force (not shown here)
        print("WARN: coll.query() raised:", e)
        return {"results": []}

    out = []
    for label, res in (("lost", rl), ("found", rf)):
        ids = _extract_first(res, "ids")
        metas = _extract_first(res, "metadatas")
        dists = _extract_first(res, "distances")
        # normalize lengths
        L = max(len(ids), len(metas), len(dists))
        for i in range(L):
            _id = ids[i] if i < len(ids) else None
            meta = metas[i] if i < len(metas) else {}
            dist = dists[i] if i < len(dists) else None
            score = _score_from_distance(dist) if dist is not None else None
            meta = _normalize_meta(meta or {}, target=("found" if label=="found" else "lost"))
            out.append({
                "collection": label,
                "id": _id,
                "item_name": meta.get("item_name"),
                "location": meta.get("location"),
                "owner_name": meta.get("owner_name"),
                "finder_name": meta.get("finder_name"),
                "email": meta.get("email"),
                "image_path": meta.get("image_path"),
                "filename": meta.get("filename"),
                "score": score,
                "metadata": meta,
            })
    # sort by score desc (None -> push to end)
    out = sorted(out, key=lambda x: (x["score"] is None, -(x["score"] or 0)))
    return {"results": out[:k]}

def query_text(text: str, k: int = 5):
    q = embedder.embed_text(text)
    try:
        rl = coll_lost.query(query_embeddings=[q], n_results=k, include=["metadatas", "distances"])
        rf = coll_found.query(query_embeddings=[q], n_results=k, include=["metadatas", "distances"])
    except Exception as e:
        print("WARN: coll.query() failed for text:", e)
        return {"results": []}
    # re-use parsing from query_image by writing minimal container
    def parse(res, label):
        out_local = []
        ids = _extract_first(res, "ids")
        metas = _extract_first(res, "metadatas")
        dists = _extract_first(res, "distances")
        L = max(len(ids), len(metas), len(dists))
        for i in range(L):
            _id = ids[i] if i < len(ids) else None
            meta = metas[i] if i < len(metas) else {}
            dist = dists[i] if i < len(dists) else None
            score = _score_from_distance(dist) if dist is not None else None
            meta = _normalize_meta(meta or {}, target=("found" if label=="found" else "lost"))
            out_local.append({
                "collection": label,
                "id": _id,
                "item_name": meta.get("item_name"),
                "location": meta.get("location"),
                "owner_name": meta.get("owner_name"),
                "finder_name": meta.get("finder_name"),
                "email": meta.get("email"),
                "image_path": meta.get("image_path"),
                "filename": meta.get("filename"),
                "score": score,
                "metadata": meta,
            })
        return out_local

    combined = parse(rl, "lost") + parse(rf, "found")
    combined = sorted(combined, key=lambda x: (x["score"] is None, -(x["score"] or 0)))
    return {"results": combined[:k]}
