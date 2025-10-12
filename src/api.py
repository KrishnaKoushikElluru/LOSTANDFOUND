import os
import shutil
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Request
from fastapi.responses import JSONResponse
from database.models import SessionLF, LostItem, FoundItem
from src import main

app = FastAPI(title="LostNFound-ML")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

IMAGES_DIR = Path("data")
if not IMAGES_DIR.exists():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")

from pathlib import Path

# helper to build image URL from metadata
def _image_url_from_meta(request_base_url, meta):
    if not meta:
        return None
    # look for image_path or filename
    path = meta.get("image_path") or meta.get("path") or meta.get("filename")
    if not path:
        return None
    p = str(path).replace("\\", "/")
    # if the metadata path contains '/data/' assume it is under mounted /images
    if "/data/" in p:
        rel = p.split("/data/", 1)[1]
        return str(request_base_url).rstrip("/") + "/images/" + rel
    # if path starts with uploads/ or file in uploads, use /uploads
    fname = Path(p).name
    # if file exists under uploads on server, return uploads URL
    if (UPLOAD_DIR / fname).exists():
        return str(request_base_url).rstrip("/") + "/uploads/" + fname
    # fallback: return uploads URL anyway (frontend will 404 if missing)
    return str(request_base_url).rstrip("/") + "/uploads/" + fname

def _format_chroma_response_for_frontend(chroma_res, request_base_url=None):
    """
    Accepts chroma_res (dict returned by src.main.query_image OR chroma client).
    Returns {"results": [ { id, collection, score, image_url, metadata, item_name, location, owner_name/finder_name, email } ] }
    """
    out = {"results": []}
    if not chroma_res:
        return out
    # chroma_res expected to be {"results": [ ... ]} from the updated src.main.query_image
    if "results" in chroma_res and isinstance(chroma_res["results"], list):
        for r in chroma_res["results"]:
            meta = r.get("metadata") or {}
            image_url = None
            if request_base_url:
                image_url = _image_url_from_meta(request_base_url, meta)
            out["results"].append({
                "id": r.get("id"),
                "collection": r.get("collection"),
                "item_name": r.get("item_name") or meta.get("item_name"),
                "location": r.get("location") or meta.get("location"),
                "image_path": r.get("image_path") or meta.get("image_path") or meta.get("path"),
                "image_url": image_url,
                "owner_name": r.get("owner_name") or meta.get("owner_name") or meta.get("finder_name") or meta.get("finder_name"),
                "finder_name": r.get("finder_name") or meta.get("finder_name") or meta.get("owner_name"),
                "email": r.get("email") or meta.get("email"),
                "score": r.get("score"),
                "metadata": meta,
            })
        return out

    # fallback: if chroma_res is raw chroma dict (ids/metadatas/distances)
    ids = chroma_res.get("ids", [[]])[0]
    metas = chroma_res.get("metadatas", [[]])[0]
    dists = chroma_res.get("distances", [[]])[0]
    for i, _id in enumerate(ids):
        meta = metas[i] if i < len(metas) else {}
        dist = dists[i] if i < len(dists) else None
        image_url = None
        if request_base_url:
            image_url = _image_url_from_meta(request_base_url, meta)
        score = float(1.0 / (1.0 + dist)) if dist is not None else None
        out["results"].append({
            "id": _id,
            "collection": meta.get("table") or "unknown",
            "item_name": meta.get("item_name"),
            "location": meta.get("location"),
            "image_path": meta.get("image_path") or meta.get("path") or meta.get("filename"),
            "image_url": image_url,
            "owner_name": meta.get("owner_name"),
            "finder_name": meta.get("finder_name"),
            "email": meta.get("email"),
            "score": score,
            "metadata": meta,
        })
    return out

@app.get("/health")
def health():
    return {"status": "ok"}
# in src/api.py
from fastapi import Request
from database import SessionLocal
from database.models import LostItem, FoundItem
import uuid

@app.post("/index/item")
async def index_item(
    request: Request,
    status: str = Form(...),
    item_name: str = Form(...),
    location: str = Form(""),
    owner_name: str = Form(""),
    email: str = Form(""),
    description: str = Form(""),
    file: UploadFile = File(...)
):
    saved = UPLOAD_DIR / file.filename
    with saved.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    session = SessionLocal()
    uid = f"{'lost' if status.lower()=='lost' else 'found'}_{uuid.uuid4().hex[:8]}"

    try:
        if status.lower() == "lost":
            new_item = LostItem(
                id=uid,
                item_name=item_name,
                description=description,
                location=location,
                owner_name=owner_name,
                email=email,
                image_path=str(saved)
            )
        else:
            new_item = FoundItem(
                id=uid,
                item_name=item_name,
                description=description,
                location=location,
                finder_name=owner_name,
                email=email,
                image_path=str(saved)
            )

        session.add(new_item)
        session.commit()

        meta = {
            "id": uid,
            "item_name": item_name,
            "description": description,
            "location": location,
            "owner_name": owner_name,
            "email": email,
            "image_path": str(saved)
        }

        from src import main
        target = "found" if status.lower() == "found" else "lost"
        main.index_single(str(saved), metadata=meta, target=target)

        image_url = f"{request.base_url}uploads/{file.filename}"

        return {
            "status": "indexed",
            "id": uid,
            "image_url": image_url,
            "message": f"{status.title()} item '{item_name}' added successfully!"
        }

    except Exception as e:
        session.rollback()
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        session.close()


# -------- INDEX NEW ITEM --------
@app.post("/index/image")
async def index_image(
    file: UploadFile = File(...),
    item_name: str = Form(...),
    description: str = Form(""),
    location: str = Form(...),
    person_name: str = Form(...),
    email: str = Form(...),
    lost_or_found: str = Form("lost"),
):
    saved_path = UPLOAD_DIR / file.filename
    with saved_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    session = SessionLF()

    try:
        if lost_or_found == "lost":
            new_item = LostItem(
                item_name=item_name,
                description=description,
                location=location,
                owner_name=person_name,
                email=email,
                image_path=str(saved_path)
            )
        else:
            new_item = FoundItem(
                item_name=item_name,
                description=description,
                location=location,
                finder_name=person_name,
                email=email,
                image_path=str(saved_path)
            )

        session.add(new_item)
        session.commit()

        # Index to Chroma
        meta = {
            "item_name": item_name,
            "description": description,
            "location": location,
            "person_name": person_name,
            "email": email,
            "image_path": str(saved_path),
        }
        main.index_single(str(saved_path), metadata=meta, target=lost_or_found)

        return {
            "status": "indexed",
            "id": new_item.id,
            "image_url": f"/uploads/{file.filename}",
            "type": lost_or_found,
        }

    except Exception as e:
        session.rollback()
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        session.close()


# -------- SEARCH BY IMAGE --------
@app.post("/search/image")
async def search_image(request: Request, file: UploadFile = File(...), k: int = Form(5)):
    saved = UPLOAD_DIR / file.filename
    with saved.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    raw = main.query_image(str(saved), k=k)
    res = _format_chroma_response_for_frontend(raw, request.base_url)
    return res

# -------- SEARCH BY TEXT --------
@app.post("/search/text")
async def search_text(request: Request, text: str = Form(...), k: int = Form(5)):
    raw = main.query_text(text, k=k)
    res = _format_chroma_response_for_frontend(raw, request.base_url)
    return res

